"""Custom Expected Goals (xG) model — logistic regression baseline.

Provides a trainable xG model as an educational alternative to StatsBomb's
pre-computed values. Useful for:
- Understanding what drives shot quality
- Custom feature engineering (e.g., adding game-state features)
- Comparing model performance against StatsBomb benchmark

Model features:
- Distance to goal centre
- Angle to goal
- Body part (head/foot)
- Shot type (open play / set piece / penalty)
- Whether shot was under pressure
- Number of defenders in shot cone (if available)

Evaluation metrics:
- Brier Score (calibration): Mean squared error of probabilities
- Log Loss: Penalises confident wrong predictions
- ROC-AUC: Discrimination ability
- Calibration curve: Visual check of predicted vs actual
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Goal coordinates on StatsBomb pitch (120×80)
_GOAL_CENTRE = np.array([120.0, 40.0])
_GOAL_LEFT_POST = np.array([120.0, 36.0])
_GOAL_RIGHT_POST = np.array([120.0, 44.0])


@dataclass
class XGModelMetrics:
    """Evaluation metrics for the xG model."""

    brier_score: float
    log_loss: float
    roc_auc: float
    n_shots: int
    goal_rate: float
    mean_predicted_xg: float

    def summary(self) -> str:
        """Human-readable metrics summary."""
        return (
            f"xG Model Evaluation (n={self.n_shots} shots)\n"
            f"{'─' * 40}\n"
            f"  Brier Score:     {self.brier_score:.4f} (lower = better calibration)\n"
            f"  Log Loss:        {self.log_loss:.4f} (lower = better)\n"
            f"  ROC-AUC:         {self.roc_auc:.4f} (higher = better discrimination)\n"
            f"  Actual goal rate: {self.goal_rate:.3f}\n"
            f"  Mean predicted:   {self.mean_predicted_xg:.3f}\n"
            f"  Calibration gap:  {abs(self.goal_rate - self.mean_predicted_xg):.4f}\n"
        )


def engineer_features(shots_df: pd.DataFrame) -> pd.DataFrame:
    """Engineer shot features for xG model.

    Features are designed to capture the key drivers of shot quality:
    - Distance: Further shots are harder to score
    - Angle: Tighter angles reduce goal probability
    - Body part: Headers are less accurate than feet
    - Pressure: Affects composure and technique

    Args:
        shots_df: Must contain: location_x, location_y, and optionally
                  shot_body_part, under_pressure, play_pattern.

    Returns:
        DataFrame with engineered feature columns.
    """
    df = shots_df.copy()

    # Distance to goal centre
    df["distance_to_goal"] = np.sqrt(
        (df["location_x"] - _GOAL_CENTRE[0]) ** 2 +
        (df["location_y"] - _GOAL_CENTRE[1]) ** 2
    )

    # Angle to goal (radians) — wider angle = easier shot
    # Use the angle subtended by the two posts from the shot location
    def _goal_angle(row: pd.Series) -> float:
        if pd.isna(row["location_x"]) or pd.isna(row["location_y"]):
            return 0.0
        shot_pos = np.array([row["location_x"], row["location_y"]])
        vec_left = _GOAL_LEFT_POST - shot_pos
        vec_right = _GOAL_RIGHT_POST - shot_pos

        cos_angle = np.dot(vec_left, vec_right) / (
            np.linalg.norm(vec_left) * np.linalg.norm(vec_right) + 1e-8
        )
        return float(np.arccos(np.clip(cos_angle, -1, 1)))

    df["goal_angle"] = df.apply(_goal_angle, axis=1)

    # Is header (binary)
    if "shot_body_part" in df.columns:
        df["is_header"] = (df["shot_body_part"] == "Head").astype(int)
    else:
        df["is_header"] = 0

    # Under pressure (binary)
    if "under_pressure" in df.columns:
        df["under_pressure_flag"] = df["under_pressure"].fillna(False).astype(int)
    else:
        df["under_pressure_flag"] = 0

    # Is penalty (binary) — trivially high xG
    if "shot_type" in df.columns:
        df["is_penalty"] = (df["shot_type"] == "Penalty").astype(int)
    elif "play_pattern" in df.columns:
        df["is_penalty"] = (df["play_pattern"] == "From Penalty").astype(int)
    else:
        df["is_penalty"] = 0

    # Is direct free kick
    if "shot_type" in df.columns:
        df["is_free_kick"] = (df["shot_type"] == "Free Kick").astype(int)
    else:
        df["is_free_kick"] = 0

    # Location features (zone-based)
    df["in_box"] = ((df["location_x"] >= 102) & (df["location_y"] >= 18) & (df["location_y"] <= 62)).astype(int)
    df["central"] = ((df["location_y"] >= 30) & (df["location_y"] <= 50)).astype(int)

    return df


def get_feature_columns() -> list[str]:
    """Return the list of feature columns used by the model."""
    return [
        "distance_to_goal",
        "goal_angle",
        "is_header",
        "under_pressure_flag",
        "is_penalty",
        "is_free_kick",
        "in_box",
        "central",
    ]


def prepare_training_data(shots_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare feature matrix X and target y from shot data.

    Args:
        shots_df: Raw shots with location and metadata.

    Returns:
        (X, y) where X is the feature matrix and y is binary goal indicator.
    """
    df = engineer_features(shots_df)

    # Target: did the shot result in a goal?
    if "shot_outcome" in df.columns:
        y = (df["shot_outcome"] == "Goal").astype(int)
    else:
        raise ValueError("shots_df must contain 'shot_outcome' column")

    feature_cols = get_feature_columns()
    X = df[feature_cols].fillna(0)

    return X, y


def train_xg_model(
    shots_df: pd.DataFrame,
    cv_folds: int = 5,
) -> tuple[Pipeline, XGModelMetrics, np.ndarray]:
    """Train a logistic regression xG model with cross-validated evaluation.

    Uses stratified K-fold CV to produce out-of-sample predictions for
    honest evaluation, then fits the final model on all data.

    Args:
        shots_df: Shot-level DataFrame with locations and outcomes.
        cv_folds: Number of cross-validation folds.

    Returns:
        (model, metrics, cv_predictions)
        - model: Fitted sklearn Pipeline
        - metrics: XGModelMetrics with calibration and discrimination scores
        - cv_predictions: Out-of-fold xG predictions for each shot
    """
    X, y = prepare_training_data(shots_df)

    logger.info("Training xG model: %d shots, %.1f%% goals", len(X), y.mean() * 100)

    # Pipeline: scale features → logistic regression
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            C=1.0,           # Regularisation strength
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )),
    ])

    # Cross-validated predictions (out-of-fold for honest evaluation)
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    cv_probs = cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]

    # Evaluation metrics
    metrics = XGModelMetrics(
        brier_score=brier_score_loss(y, cv_probs),
        log_loss=log_loss(y, cv_probs),
        roc_auc=roc_auc_score(y, cv_probs),
        n_shots=len(y),
        goal_rate=y.mean(),
        mean_predicted_xg=cv_probs.mean(),
    )

    logger.info("\n%s", metrics.summary())

    # Fit final model on all data
    pipeline.fit(X, y)

    return pipeline, metrics, cv_probs


def predict_xg(model: Pipeline, shots_df: pd.DataFrame) -> np.ndarray:
    """Predict xG for new shots using a trained model.

    Args:
        model: Trained Pipeline from train_xg_model.
        shots_df: New shot data with location features.

    Returns:
        Array of xG probabilities.
    """
    df = engineer_features(shots_df)
    X = df[get_feature_columns()].fillna(0)
    return model.predict_proba(X)[:, 1]


def compare_with_statsbomb(
    shots_df: pd.DataFrame,
    custom_xg: np.ndarray,
) -> pd.DataFrame:
    """Compare custom xG predictions with StatsBomb pre-computed values.

    Returns a comparison DataFrame showing both models' predictions alongside
    actual outcomes for calibration assessment.
    """
    comparison = pd.DataFrame({
        "player": shots_df.get("player_name", shots_df.get("player", "Unknown")),
        "minute": shots_df["minute"],
        "statsbomb_xg": shots_df.get("xg", shots_df.get("shot_statsbomb_xg", None)),
        "custom_xg": custom_xg,
        "actual_goal": (shots_df["shot_outcome"] == "Goal").astype(int),
    })

    # Calculate errors
    if comparison["statsbomb_xg"].notna().any():
        comparison["sb_error"] = comparison["actual_goal"] - comparison["statsbomb_xg"]
        comparison["custom_error"] = comparison["actual_goal"] - comparison["custom_xg"]

    return comparison


def get_feature_importance(model: Pipeline) -> pd.DataFrame:
    """Extract feature importance (coefficients) from the logistic regression.

    Positive coefficients increase goal probability; negative decrease it.
    """
    lr = model.named_steps["model"]
    scaler = model.named_steps["scaler"]
    feature_names = get_feature_columns()

    # Scale-adjusted coefficients for interpretability
    coefs = lr.coef_[0]

    importance = pd.DataFrame({
        "feature": feature_names,
        "coefficient": coefs,
        "abs_importance": np.abs(coefs),
    }).sort_values("abs_importance", ascending=False)

    return importance
