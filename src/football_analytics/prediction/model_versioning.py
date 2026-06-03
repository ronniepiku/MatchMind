"""Prediction model versioning and accuracy tracking.

Provides:
- Model version tracking for prediction algorithm changes
- Storage of predictions with version metadata
- Retrospective accuracy analysis (Brier score, calibration)
- Accuracy dashboard data for monitoring model performance over time

Every prediction is stored with:
- model_version: semantic version of the prediction algorithm
- model_params: configuration hash for reproducibility
- actual outcome (backfilled after match completion)
- accuracy metrics (brier_score, prediction_correct)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)

# Current model version — bump when algorithm changes
MODEL_VERSION = "1.0.0"


@dataclass
class ModelVersion:
    """Metadata about a prediction model version."""

    version: str
    description: str
    algorithm: str
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def params_hash(self) -> str:
        """Deterministic hash of model parameters for comparison."""
        serialised = json.dumps(self.parameters, sort_keys=True)
        return hashlib.sha256(serialised.encode()).hexdigest()[:12]


@dataclass
class PredictionRecord:
    """A stored prediction with accountability fields."""

    prediction_id: int | None = None
    fixture_id: int | None = None
    match_id: int | None = None
    model_version: str = MODEL_VERSION
    params_hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    # Prediction outputs
    predicted_home_win: float = 0.0
    predicted_draw: float = 0.0
    predicted_away_win: float = 0.0
    predicted_score_home: int = 0
    predicted_score_away: int = 0
    predicted_xg_home: float = 0.0
    predicted_xg_away: float = 0.0
    confidence: str = ""

    # Actuals (backfilled)
    actual_home_score: int | None = None
    actual_away_score: int | None = None
    prediction_correct: bool | None = None
    brier_score: float | None = None


@dataclass
class AccuracyReport:
    """Model accuracy report over a period."""

    model_version: str
    period_start: date
    period_end: date
    total_predictions: int
    predictions_correct: int
    accuracy_pct: float
    average_brier_score: float
    calibration: list[dict[str, float]]  # bins of predicted prob vs actual frequency
    by_confidence: dict[str, dict[str, float]] = field(default_factory=dict)


class PredictionVersionManager:
    """Manages prediction storage, versioning, and accuracy tracking.

    Usage:
        manager = PredictionVersionManager(engine)
        manager.store_prediction(fixture_id=1, prediction=...)
        manager.backfill_actuals(match_id=100, home_score=2, away_score=1)
        report = manager.accuracy_report(from_date=..., to_date=...)
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def store_prediction(
        self,
        fixture_id: int | None = None,
        match_id: int | None = None,
        home_win_prob: float = 0.0,
        draw_prob: float = 0.0,
        away_win_prob: float = 0.0,
        predicted_score: tuple[int, int] = (0, 0),
        predicted_xg: tuple[float, float] = (0.0, 0.0),
        confidence: str = "medium",
        model_params: dict[str, Any] | None = None,
    ) -> int:
        """Store a prediction for later accuracy tracking.

        Returns:
            The generated prediction_id.
        """
        params_hash = ""
        if model_params:
            serialised = json.dumps(model_params, sort_keys=True)
            params_hash = hashlib.sha256(serialised.encode()).hexdigest()[:12]

        query = text("""
            INSERT INTO predictions
                (fixture_id, match_id, model_version, params_hash,
                 predicted_home_win, predicted_draw, predicted_away_win,
                 predicted_score_home, predicted_score_away,
                 predicted_xg_home, predicted_xg_away, confidence)
            VALUES (:fid, :mid, :version, :hash,
                    :hw, :d, :aw, :sh, :sa, :xgh, :xga, :conf)
            RETURNING prediction_id
        """)

        with self._engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "fid": fixture_id,
                    "mid": match_id,
                    "version": MODEL_VERSION,
                    "hash": params_hash,
                    "hw": home_win_prob,
                    "d": draw_prob,
                    "aw": away_win_prob,
                    "sh": predicted_score[0],
                    "sa": predicted_score[1],
                    "xgh": predicted_xg[0],
                    "xga": predicted_xg[1],
                    "conf": confidence,
                },
            )
            pred_id = result.scalar_one()

        logger.info(f"Stored prediction {pred_id} (model v{MODEL_VERSION})")
        return pred_id

    def backfill_actuals(
        self,
        prediction_id: int | None = None,
        fixture_id: int | None = None,
        match_id: int | None = None,
        home_score: int = 0,
        away_score: int = 0,
    ) -> None:
        """Backfill actual results for accuracy calculation.

        Can identify prediction by prediction_id, fixture_id, or match_id.
        """
        # Find the prediction
        if prediction_id:
            condition = "prediction_id = :pid"
            params: dict[str, Any] = {"pid": prediction_id}
        elif fixture_id:
            condition = "fixture_id = :fid"
            params = {"fid": fixture_id}
        elif match_id:
            condition = "match_id = :mid"
            params = {"mid": match_id}
        else:
            raise ValueError("Must provide prediction_id, fixture_id, or match_id")

        # Get prediction to compute accuracy
        fetch_query = text(f"""
            SELECT prediction_id, predicted_home_win, predicted_draw, predicted_away_win
            FROM predictions WHERE {condition}
            ORDER BY created_at DESC LIMIT 1
        """)

        with self._engine.connect() as conn:
            row = conn.execute(fetch_query, params).mappings().fetchone()

        if not row:
            logger.warning(f"No prediction found for {condition}")
            return

        pred_id = row["prediction_id"]
        p_hw = float(row["predicted_home_win"])
        p_d = float(row["predicted_draw"])
        p_aw = float(row["predicted_away_win"])

        # Determine actual outcome
        if home_score > away_score:
            actual_outcome = "home"
        elif away_score > home_score:
            actual_outcome = "away"
        else:
            actual_outcome = "draw"

        # Determine predicted outcome
        probs = {"home": p_hw, "draw": p_d, "away": p_aw}
        predicted_outcome = max(probs, key=probs.get)  # type: ignore

        correct = predicted_outcome == actual_outcome

        # Brier score: mean squared error of probability vector
        actual_vec = [
            1.0 if actual_outcome == "home" else 0.0,
            1.0 if actual_outcome == "draw" else 0.0,
            1.0 if actual_outcome == "away" else 0.0,
        ]
        pred_vec = [p_hw, p_d, p_aw]
        brier = sum((p - a) ** 2 for p, a in zip(pred_vec, actual_vec, strict=False)) / 3

        # Update
        update_query = text("""
            UPDATE predictions
            SET actual_score = :score,
                prediction_correct = :correct,
                brier_score = :brier
            WHERE prediction_id = :pid
        """)

        with self._engine.begin() as conn:
            conn.execute(
                update_query,
                {
                    "score": f"{home_score}-{away_score}",
                    "correct": correct,
                    "brier": round(brier, 4),
                    "pid": pred_id,
                },
            )

        logger.info(f"Backfilled prediction {pred_id}: {'✓' if correct else '✗'} (Brier: {brier:.3f})")

    def accuracy_report(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        model_version: str | None = None,
        competition_id: int | None = None,
    ) -> AccuracyReport:
        """Generate model accuracy report.

        Args:
            from_date: Start of reporting period.
            to_date: End of reporting period.
            model_version: Filter to specific model version.
            competition_id: Filter to specific competition.

        Returns:
            AccuracyReport with metrics and calibration data.
        """
        conditions = ["prediction_correct IS NOT NULL"]
        params: dict[str, Any] = {}

        if from_date:
            conditions.append("p.created_at >= :from_date")
            params["from_date"] = from_date
        if to_date:
            conditions.append("p.created_at <= :to_date")
            params["to_date"] = to_date
        if model_version:
            conditions.append("p.model_version = :version")
            params["version"] = model_version
        if competition_id:
            conditions.append("f.competition_id = :cid")
            params["cid"] = competition_id

        where = " AND ".join(conditions)

        query = text(f"""
            SELECT p.prediction_id, p.model_version, p.confidence,
                   p.predicted_home_win, p.predicted_draw, p.predicted_away_win,
                   p.prediction_correct, p.brier_score, p.created_at
            FROM predictions p
            LEFT JOIN fixtures f ON p.fixture_id = f.fixture_id
            WHERE {where}
            ORDER BY p.created_at ASC
        """)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params=params)
        except Exception:
            df = pd.DataFrame()

        total = len(df)
        correct = int(df["prediction_correct"].sum()) if total > 0 else 0
        accuracy = round(correct / max(total, 1) * 100, 1)
        avg_brier = round(float(df["brier_score"].mean()), 4) if total > 0 else 0.0

        # Calibration: bin by max predicted probability
        calibration = self._compute_calibration(df)

        # By confidence level
        by_confidence = {}
        if total > 0:
            for conf in df["confidence"].unique():
                subset = df[df["confidence"] == conf]
                by_confidence[conf] = {
                    "total": len(subset),
                    "correct": int(subset["prediction_correct"].sum()),
                    "accuracy_pct": round(
                        int(subset["prediction_correct"].sum()) / max(len(subset), 1) * 100,
                        1,
                    ),
                    "avg_brier": round(float(subset["brier_score"].mean()), 4),
                }

        return AccuracyReport(
            model_version=model_version or MODEL_VERSION,
            period_start=from_date or date.today(),
            period_end=to_date or date.today(),
            total_predictions=total,
            predictions_correct=correct,
            accuracy_pct=accuracy,
            average_brier_score=avg_brier,
            calibration=calibration,
            by_confidence=by_confidence,
        )

    def get_accuracy_over_time(self, window: int = 20, model_version: str | None = None) -> list[dict[str, Any]]:
        """Get rolling accuracy over time for dashboard visualisation.

        Args:
            window: Rolling window size (number of predictions).
            model_version: Filter to specific version.

        Returns:
            List of data points with rolling accuracy and brier score.
        """
        conditions = ["prediction_correct IS NOT NULL"]
        params: dict[str, Any] = {}
        if model_version:
            conditions.append("model_version = :version")
            params["version"] = model_version

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT created_at::date AS prediction_date,
                   prediction_correct, brier_score
            FROM predictions
            WHERE {where}
            ORDER BY created_at ASC
        """)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params=params)
        except Exception:
            return []

        if df.empty:
            return []

        # Compute rolling metrics
        df["rolling_accuracy"] = df["prediction_correct"].rolling(window=window, min_periods=5).mean() * 100
        df["rolling_brier"] = df["brier_score"].rolling(window=window, min_periods=5).mean()

        results = []
        for _, row in df.dropna(subset=["rolling_accuracy"]).iterrows():
            results.append(
                {
                    "date": str(row["prediction_date"]),
                    "rolling_accuracy_pct": round(float(row["rolling_accuracy"]), 1),
                    "rolling_brier_score": round(float(row["rolling_brier"]), 4),
                }
            )

        return results

    def _compute_calibration(self, df: pd.DataFrame) -> list[dict[str, float]]:
        """Compute calibration data (predicted probability vs actual frequency)."""
        if df.empty:
            return []

        # Get max predicted probability for each prediction
        df = df.copy()
        df["max_prob"] = df[["predicted_home_win", "predicted_draw", "predicted_away_win"]].max(axis=1)

        # Bin into deciles
        bins = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        calibration = []
        for i in range(len(bins) - 1):
            mask = (df["max_prob"] >= bins[i]) & (df["max_prob"] < bins[i + 1])
            subset = df[mask]
            if len(subset) > 0:
                calibration.append(
                    {
                        "bin_start": bins[i],
                        "bin_end": bins[i + 1],
                        "predicted_avg": round(float(subset["max_prob"].mean()), 3),
                        "actual_frequency": round(float(subset["prediction_correct"].mean()), 3),
                        "count": len(subset),
                    }
                )

        return calibration
