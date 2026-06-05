"""Machine Learning match prediction pipeline.

A gradient-boosted ensemble model for match outcome prediction that goes
beyond the existing Poisson/Dixon-Coles approach by learning complex
feature interactions from historical match data.

Pipeline stages:
1. Feature engineering — derive 25+ features per match from event data
2. Training — gradient boosting classifier (XGBoost or LightGBM)
3. Calibration — Platt scaling for well-calibrated probabilities
4. Evaluation — cross-validated Brier score, log-loss, ROC-AUC
5. Inference — predict upcoming matches with confidence intervals
6. Persistence — save/load trained models with version tracking

Features engineered per team (home/away):
- Offensive: xG/90, shots/90, shot quality (avg xG per shot), big chances
- Creative: key passes/90, xA/90, progressive passes, final third entries
- Defensive: xGA/90, pressures/90, PPDA, tackles won %, interceptions/90
- Possession: possession %, pass accuracy, build-up directness
- Form: rolling 5-match xG trend, points per game, goal difference
- Context: rest days, home/away record, head-to-head history
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.config import config
from football_analytics.db import get_engine

logger = logging.getLogger(__name__)

# Current ML model version
ML_MODEL_VERSION = "2.0.0"


def _get_models_dir() -> Path:
    """Lazily resolve models directory to avoid triggering config at import time."""
    return config.processed_dir / "models"


@dataclass
class MLModelMetrics:
    """Evaluation metrics for the ML prediction model."""

    brier_score: float
    log_loss: float
    roc_auc_home: float
    roc_auc_draw: float
    roc_auc_away: float
    accuracy: float
    n_matches: int
    calibration_error: float
    feature_importance: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"ML Match Prediction Model v{ML_MODEL_VERSION}\n"
            f"{'─' * 50}\n"
            f"  Brier Score:       {self.brier_score:.4f} (lower = better)\n"
            f"  Log Loss:          {self.log_loss:.4f}\n"
            f"  ROC-AUC (Home):    {self.roc_auc_home:.4f}\n"
            f"  ROC-AUC (Draw):    {self.roc_auc_draw:.4f}\n"
            f"  ROC-AUC (Away):    {self.roc_auc_away:.4f}\n"
            f"  Accuracy:          {self.accuracy:.3f}\n"
            f"  Calibration Error: {self.calibration_error:.4f}\n"
            f"  Training Matches:  {self.n_matches}\n"
        )


@dataclass
class MLPrediction:
    """ML model prediction output for a single match."""

    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_outcome: str  # "home_win", "draw", "away_win"
    confidence: float  # Max probability (how decisive the prediction is)
    model_version: str = ML_MODEL_VERSION
    feature_contributions: dict[str, float] = field(default_factory=dict)
    # Integrated Poisson simulation
    expected_home_goals: float = 0.0
    expected_away_goals: float = 0.0
    most_likely_score: tuple[int, int] = (0, 0)
    over_2_5_prob: float = 0.0
    btts_prob: float = 0.0


class MatchFeatureEngine:
    """Engineers features from raw event data for ML prediction.

    Computes rolling aggregates per team using the most recent N matches,
    capturing form, strength, and style metrics.
    """

    ROLLING_WINDOW = 6  # Matches to look back for rolling features

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def compute_team_features(
        self,
        team_id: int,
        before_date: date | None = None,
        season_id: int | None = None,
        n_matches: int | None = None,
    ) -> dict[str, float]:
        """Compute feature vector for a team based on recent match history.

        Returns a dict of 15+ features representing team strength and style.
        """
        n = n_matches or self.ROLLING_WINDOW

        date_filter = ""
        params: dict[str, Any] = {"team_id": team_id, "limit": n}

        if before_date:
            date_filter = "AND m.match_date < :before_date"
            params["before_date"] = before_date
        if season_id:
            date_filter += " AND m.season_id = :season_id"
            params["season_id"] = season_id

        query = text(f"""
            WITH team_matches AS (
                SELECT m.match_id, m.match_date,
                       m.home_team_id, m.away_team_id,
                       m.home_score, m.away_score,
                       CASE WHEN m.home_team_id = :team_id THEN 'home' ELSE 'away' END AS venue
                FROM matches m
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  {date_filter}
                ORDER BY m.match_date DESC
                LIMIT :limit
            ),
            match_events AS (
                SELECT e.match_id, e.team_id, e.event_type, e.xg, e.xa,
                       e.key_pass, e.pass_outcome, e.location_x,
                       e.under_pressure, e.shot_outcome
                FROM events e
                WHERE e.match_id IN (SELECT match_id FROM team_matches)
            )
            SELECT
                COUNT(DISTINCT tm.match_id) AS matches_played,
                -- Offensive
                COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Shot'), 0) AS total_xg,
                COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Shot') AS total_shots,
                COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.shot_outcome = 'Goal') AS goals_scored,
                COALESCE(SUM(e.xg) FILTER (
                    WHERE e.team_id = :team_id AND e.event_type = 'Shot' AND e.xg > 0.2
                ), 0) AS big_chance_xg,
                -- Creative
                COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.key_pass) AS key_passes,
                COALESCE(SUM(e.xa) FILTER (WHERE e.team_id = :team_id AND e.xa IS NOT NULL), 0) AS total_xa,
                COUNT(*) FILTER (
                    WHERE e.team_id = :team_id AND e.event_type = 'Pass'
                    AND e.pass_outcome IS NULL AND e.location_x > 80
                ) AS final_third_passes,
                -- Defensive (events against this team)
                COALESCE(SUM(e.xg) FILTER (WHERE e.team_id != :team_id AND e.event_type = 'Shot'), 0) AS xg_conceded,
                COUNT(*) FILTER (WHERE e.team_id != :team_id AND e.event_type = 'Shot') AS shots_conceded,
                COUNT(*) FILTER (WHERE e.team_id != :team_id AND e.shot_outcome = 'Goal') AS goals_conceded,
                -- Pressing
                COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Pressure') AS pressures,
                COUNT(*) FILTER (
                    WHERE e.team_id = :team_id AND e.event_type = 'Pressure'
                    AND e.location_x > 60
                ) AS high_pressures,
                -- Possession proxy
                COUNT(*) FILTER (
                    WHERE e.team_id = :team_id AND e.event_type = 'Pass' AND e.pass_outcome IS NULL
                ) AS passes_completed,
                COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Pass') AS passes_attempted,
                -- Results
                SUM(CASE
                    WHEN tm.venue = 'home' AND tm.home_score > tm.away_score THEN 3
                    WHEN tm.venue = 'away' AND tm.away_score > tm.home_score THEN 3
                    WHEN tm.home_score = tm.away_score THEN 1
                    ELSE 0
                END) AS points
            FROM team_matches tm
            LEFT JOIN match_events e ON e.match_id = tm.match_id
        """)

        with self._engine.connect() as conn:
            row = conn.execute(query, params).fetchone()

        if not row or row.matches_played == 0:
            return self._empty_features()

        n_matches_actual = row.matches_played

        def per_match(val: float) -> float:
            return float(val) / n_matches_actual

        # Avoid division by zero
        shots = max(row.total_shots, 1)
        passes_att = max(row.passes_attempted, 1)

        return {
            # Offensive metrics (per match)
            "xg_per_match": per_match(row.total_xg),
            "shots_per_match": per_match(row.total_shots),
            "shot_quality": float(row.total_xg) / shots,  # avg xG per shot
            "goals_per_match": per_match(row.goals_scored),
            "big_chance_xg_per_match": per_match(row.big_chance_xg),
            "conversion_rate": float(row.goals_scored) / shots,
            # Creative
            "xa_per_match": per_match(row.total_xa),
            "key_passes_per_match": per_match(row.key_passes),
            "final_third_passes_per_match": per_match(row.final_third_passes),
            # Defensive
            "xg_conceded_per_match": per_match(row.xg_conceded),
            "shots_conceded_per_match": per_match(row.shots_conceded),
            "goals_conceded_per_match": per_match(row.goals_conceded),
            # Pressing
            "pressures_per_match": per_match(row.pressures),
            "high_press_ratio": float(row.high_pressures) / max(row.pressures, 1),
            # Possession
            "pass_accuracy": float(row.passes_completed) / passes_att,
            "passes_per_match": per_match(row.passes_completed),
            # Form
            "points_per_match": per_match(row.points),
            "goal_difference_per_match": per_match(row.goals_scored - row.goals_conceded),
            # Derived
            "net_xg_per_match": per_match(row.total_xg) - per_match(row.xg_conceded),
            "xg_overperformance": per_match(row.goals_scored) - per_match(row.total_xg),
        }

    def _empty_features(self) -> dict[str, float]:
        """Return zeroed feature vector when no data is available."""
        return {
            "xg_per_match": 0.0,
            "shots_per_match": 0.0,
            "shot_quality": 0.0,
            "goals_per_match": 0.0,
            "big_chance_xg_per_match": 0.0,
            "conversion_rate": 0.0,
            "xa_per_match": 0.0,
            "key_passes_per_match": 0.0,
            "final_third_passes_per_match": 0.0,
            "xg_conceded_per_match": 0.0,
            "shots_conceded_per_match": 0.0,
            "goals_conceded_per_match": 0.0,
            "pressures_per_match": 0.0,
            "high_press_ratio": 0.0,
            "pass_accuracy": 0.0,
            "passes_per_match": 0.0,
            "points_per_match": 0.0,
            "goal_difference_per_match": 0.0,
            "net_xg_per_match": 0.0,
            "xg_overperformance": 0.0,
        }

    def build_training_dataset(
        self,
        season_ids: list[int] | None = None,
        min_matches_per_team: int = 4,
    ) -> pd.DataFrame:
        """Build the full training dataset from historical matches.

        For each match, computes features for both home and away teams
        using only data available BEFORE that match (no look-ahead bias).

        Returns DataFrame with columns: home_* features, away_* features,
        feature differences, and target outcome label.
        """
        # Get all matches with results
        filter_clause = ""
        params: dict[str, Any] = {}
        if season_ids:
            filter_clause = "WHERE m.season_id = ANY(:season_ids)"
            params["season_ids"] = season_ids

        query = text(f"""
            SELECT m.match_id, m.match_date, m.season_id,
                   m.home_team_id, m.away_team_id,
                   m.home_score, m.away_score,
                   ht.team_name AS home_team_name,
                   at.team_name AS away_team_name
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            {filter_clause}
            ORDER BY m.match_date
        """)

        with self._engine.connect() as conn:
            matches_df = pd.read_sql(query, conn, params=params)

        if matches_df.empty:
            logger.warning("No matches found for training dataset")
            return pd.DataFrame()

        logger.info("Building training dataset from %d matches...", len(matches_df))

        rows = []
        for _, match in matches_df.iterrows():
            home_features = self.compute_team_features(
                team_id=match["home_team_id"],
                before_date=match["match_date"],
            )
            away_features = self.compute_team_features(
                team_id=match["away_team_id"],
                before_date=match["match_date"],
            )

            # Skip if either team has insufficient history
            if home_features["xg_per_match"] == 0 and away_features["xg_per_match"] == 0:
                continue

            # Determine outcome
            if match["home_score"] > match["away_score"]:
                outcome = "home_win"
            elif match["home_score"] == match["away_score"]:
                outcome = "draw"
            else:
                outcome = "away_win"

            # Combine features
            row: dict[str, Any] = {"match_id": match["match_id"], "match_date": match["match_date"]}

            for key, val in home_features.items():
                row[f"home_{key}"] = val
            for key, val in away_features.items():
                row[f"away_{key}"] = val

            # Difference features (home - away)
            for key in home_features:
                row[f"diff_{key}"] = home_features[key] - away_features[key]

            row["outcome"] = outcome
            row["home_score"] = match["home_score"]
            row["away_score"] = match["away_score"]
            rows.append(row)

        df = pd.DataFrame(rows)
        logger.info("Training dataset built: %d samples, %d features", len(df), len(df.columns) - 4)
        return df


class MLMatchPredictor:
    """Gradient-boosted match outcome prediction model.

    Uses an ensemble of gradient boosting trees trained on engineered
    features from historical match data. Produces calibrated probability
    estimates for home win, draw, and away win.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        self._feature_engine = MatchFeatureEngine(self._engine)
        self._model = None
        self._feature_columns: list[str] = []
        self._label_encoder = LabelEncoder()
        self._metrics: MLModelMetrics | None = None
        self._model_path = _get_models_dir() / f"ml_predictor_v{ML_MODEL_VERSION}.pkl"

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def train(
        self,
        season_ids: list[int] | None = None,
        n_splits: int = 5,
    ) -> MLModelMetrics:
        """Train the prediction model with time-series cross-validation.

        Uses TimeSeriesSplit to respect temporal ordering — never trains
        on future data when evaluating past predictions.
        """
        try:
            from sklearn.ensemble import GradientBoostingClassifier
        except ImportError:
            raise RuntimeError("scikit-learn is required: pip install scikit-learn")

        # Build dataset
        df = self._feature_engine.build_training_dataset(season_ids=season_ids)
        if df.empty or len(df) < 20:
            raise ValueError(f"Insufficient training data ({len(df)} matches). Need at least 20.")

        # Prepare features and labels
        feature_cols = [c for c in df.columns if c.startswith(("home_", "away_", "diff_"))]
        X = df[feature_cols].fillna(0).values
        y_labels = df["outcome"].values

        self._feature_columns = feature_cols
        self._label_encoder.fit(["away_win", "draw", "home_win"])
        y = self._label_encoder.transform(y_labels)

        # Train with time-series cross-validation
        tscv = TimeSeriesSplit(n_splits=min(n_splits, len(df) // 10))

        # Collect out-of-fold predictions for evaluation
        oof_probs = np.zeros((len(X), 3))
        oof_mask = np.zeros(len(X), dtype=bool)

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=5,
                random_state=42,
            )
            model.fit(X_train, y_train)

            probs = model.predict_proba(X_val)
            oof_probs[val_idx] = probs
            oof_mask[val_idx] = True

            logger.info("Fold %d: accuracy=%.3f", fold + 1, model.score(X_val, y_val))

        # Train final model on all data with calibration
        base_model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=42,
        )
        self._model = CalibratedClassifierCV(base_model, cv=3, method="isotonic")
        self._model.fit(X, y)

        # Evaluate on out-of-fold predictions
        eval_probs = oof_probs[oof_mask]
        eval_y = y[oof_mask]
        eval_preds = eval_probs.argmax(axis=1)

        # Brier score (multi-class average)
        brier_scores = []
        for cls in range(3):
            y_binary = (eval_y == cls).astype(int)
            brier_scores.append(brier_score_loss(y_binary, eval_probs[:, cls]))
        avg_brier = np.mean(brier_scores)

        # ROC-AUC per class
        roc_aucs = []
        for cls in range(3):
            y_binary = (eval_y == cls).astype(int)
            if len(np.unique(y_binary)) > 1:
                roc_aucs.append(roc_auc_score(y_binary, eval_probs[:, cls]))
            else:
                roc_aucs.append(0.5)

        # Calibration error
        cal_error = self._compute_calibration_error(eval_probs, eval_y)

        # Feature importance from base model
        importance = dict(zip(feature_cols, base_model.feature_importances_, strict=False))
        top_features = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15])

        self._metrics = MLModelMetrics(
            brier_score=float(avg_brier),
            log_loss=float(log_loss(eval_y, eval_probs)),
            roc_auc_home=roc_aucs[2],  # "home_win" is class 2
            roc_auc_draw=roc_aucs[1],
            roc_auc_away=roc_aucs[0],
            accuracy=float((eval_preds == eval_y).mean()),
            n_matches=len(df),
            calibration_error=cal_error,
            feature_importance=top_features,
        )

        logger.info("Model trained:\n%s", self._metrics.summary())
        return self._metrics

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        season_id: int | None = None,
    ) -> MLPrediction:
        """Predict match outcome for two teams.

        If model is not trained, falls back to feature-based heuristic.
        """
        home_features = self._feature_engine.compute_team_features(
            team_id=home_team_id,
            season_id=season_id,
        )
        away_features = self._feature_engine.compute_team_features(
            team_id=away_team_id,
            season_id=season_id,
        )

        # Get team names
        with self._engine.connect() as conn:
            home_row = conn.execute(
                text("SELECT team_name FROM teams WHERE team_id = :tid"),
                {"tid": home_team_id},
            ).fetchone()
            away_row = conn.execute(
                text("SELECT team_name FROM teams WHERE team_id = :tid"),
                {"tid": away_team_id},
            ).fetchone()

        home_name = home_row[0] if home_row else f"Team {home_team_id}"
        away_name = away_row[0] if away_row else f"Team {away_team_id}"

        if self._model is not None and self._feature_columns:
            # ML model prediction
            feature_row: dict[str, float] = {}
            for key, val in home_features.items():
                feature_row[f"home_{key}"] = val
            for key, val in away_features.items():
                feature_row[f"away_{key}"] = val
            for key in home_features:
                feature_row[f"diff_{key}"] = home_features[key] - away_features[key]

            X = np.array([[feature_row.get(c, 0.0) for c in self._feature_columns]])
            probs = self._model.predict_proba(X)[0]

            # Classes are ordered: away_win=0, draw=1, home_win=2
            away_prob, draw_prob, home_prob = probs[0], probs[1], probs[2]

            # Feature contributions (approximate via difference features)
            contributions = {
                k.replace("diff_", ""): v for k, v in feature_row.items() if k.startswith("diff_") and abs(v) > 0.01
            }
        else:
            # Heuristic fallback using features directly
            home_xg = home_features["xg_per_match"]
            away_xg = away_features["xg_per_match"]
            home_def = home_features["xg_conceded_per_match"]
            away_def = away_features["xg_conceded_per_match"]

            # Simple strength estimate
            home_strength = (home_xg + away_def) / 2 * 1.05  # slight home advantage
            away_strength = (away_xg + home_def) / 2

            total = home_strength + away_strength + 0.5  # draw baseline
            home_prob = home_strength / total
            away_prob = away_strength / total
            draw_prob = 1.0 - home_prob - away_prob
            draw_prob = max(draw_prob, 0.15)  # floor draw probability

            # Re-normalize
            total_prob = home_prob + draw_prob + away_prob
            home_prob /= total_prob
            draw_prob /= total_prob
            away_prob /= total_prob

            contributions = {
                "xg_per_match": home_features["xg_per_match"] - away_features["xg_per_match"],
                "xg_conceded": home_features["xg_conceded_per_match"] - away_features["xg_conceded_per_match"],
            }

        # Determine predicted outcome
        if home_prob >= draw_prob and home_prob >= away_prob:
            predicted = "home_win"
        elif away_prob >= home_prob and away_prob >= draw_prob:
            predicted = "away_win"
        else:
            predicted = "draw"

        # Estimate expected goals for scoreline prediction
        exp_home = home_features["xg_per_match"] * 1.05  # home advantage
        exp_away = away_features["xg_per_match"]

        # Simulate scoreline
        from football_analytics.analysis.simulation import simulate_match

        sim_result = simulate_match(
            home_xg=max(exp_home, 0.3),
            away_xg=max(exp_away, 0.3),
            home_team=home_name,
            away_team=away_name,
            n_simulations=5000,
        )

        return MLPrediction(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team_name=home_name,
            away_team_name=away_name,
            home_win_prob=round(float(home_prob), 4),
            draw_prob=round(float(draw_prob), 4),
            away_win_prob=round(float(away_prob), 4),
            predicted_outcome=predicted,
            confidence=round(float(max(home_prob, draw_prob, away_prob)), 4),
            feature_contributions=contributions,
            expected_home_goals=round(sim_result.expected_home_goals, 2),
            expected_away_goals=round(sim_result.expected_away_goals, 2),
            most_likely_score=sim_result.most_likely_score,
            over_2_5_prob=round(sim_result.over_2_5_prob, 4),
            btts_prob=round(sim_result.btts_prob, 4),
        )

    def save(self) -> Path:
        """Persist trained model to disk."""
        _get_models_dir().mkdir(parents=True, exist_ok=True)
        artifact = {
            "model": self._model,
            "feature_columns": self._feature_columns,
            "label_encoder": self._label_encoder,
            "metrics": self._metrics,
            "version": ML_MODEL_VERSION,
            "trained_at": datetime.now().isoformat(),
        }
        with open(self._model_path, "wb") as f:
            pickle.dump(artifact, f)
        logger.info("Model saved to %s", self._model_path)
        return self._model_path

    def load(self) -> bool:
        """Load a previously trained model from disk."""
        if not self._model_path.exists():
            logger.info("No saved model found at %s", self._model_path)
            return False
        with open(self._model_path, "rb") as f:
            artifact = pickle.load(f)
        self._model = artifact["model"]
        self._feature_columns = artifact["feature_columns"]
        self._label_encoder = artifact["label_encoder"]
        self._metrics = artifact.get("metrics")
        logger.info("Model loaded (v%s)", artifact.get("version", "unknown"))
        return True

    def get_metrics(self) -> MLModelMetrics | None:
        """Return metrics from last training run."""
        return self._metrics

    def _compute_calibration_error(self, probs: np.ndarray, y_true: np.ndarray) -> float:
        """Compute expected calibration error (ECE) across probability bins."""
        n_bins = 10
        ece = 0.0
        for cls in range(3):
            cls_probs = probs[:, cls]
            cls_true = (y_true == cls).astype(float)
            bin_edges = np.linspace(0, 1, n_bins + 1)
            for i in range(n_bins):
                mask = (cls_probs >= bin_edges[i]) & (cls_probs < bin_edges[i + 1])
                if mask.sum() > 0:
                    avg_prob = cls_probs[mask].mean()
                    avg_true = cls_true[mask].mean()
                    ece += abs(avg_prob - avg_true) * mask.sum()
        return ece / (len(y_true) * 3)
