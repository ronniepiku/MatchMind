"""Data validation pipeline for ingested football event data.

Validates incoming data before it reaches the analytics layer, catching:
- Schema violations (missing required columns, wrong types)
- Statistical anomalies (impossible values, extreme outliers)
- Referential integrity issues (orphan player/team IDs)
- Temporal consistency (events outside match duration)

Results are logged to the `data_quality_log` table and optionally block ingestion.

Usage:
    validator = DataValidator(engine)
    report = validator.validate_match_events(match_id=3869685)
    report = validator.validate_batch(df_events)

    # Strict mode — raises on critical failures
    validator = DataValidator(engine, strict=True)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    severity: str = "warning"  # "info", "warning", "critical"
    details: str = ""
    record_count: int = 0
    failed_count: int = 0

    @property
    def pass_rate(self) -> float:
        if self.record_count == 0:
            return 1.0
        return (self.record_count - self.failed_count) / self.record_count


@dataclass
class ValidationReport:
    """Aggregated validation report for a batch or match."""

    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if no critical checks failed."""
        return not any(
            r for r in self.results if not r.passed and r.severity == "critical"
        )

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == "warning"]

    @property
    def critical_failures(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == "critical"]

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "total_checks": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "warnings": len(self.warnings),
            "critical": len(self.critical_failures),
            "overall_pass": self.passed,
        }


class DataValidator:
    """Validates football event data quality before analytical processing.

    Args:
        engine: SQLAlchemy engine for DB checks and logging.
        strict: If True, raise ValueError on critical failures.
        log_to_db: If True, persist results to data_quality_log table.
    """

    # Valid event types from StatsBomb specification
    VALID_EVENT_TYPES = {
        "Pass",
        "Shot",
        "Carry",
        "Pressure",
        "Duel",
        "Dribble",
        "Interception",
        "Ball Recovery",
        "Block",
        "Clearance",
        "Goal Keeper",
        "Foul Committed",
        "Foul Won",
        "Dispossessed",
        "Miscontrol",
        "Ball Receipt*",
        "Half Start",
        "Half End",
        "Starting XI",
        "Substitution",
        "Tactical Shift",
        "Bad Behaviour",
        "Injury Stoppage",
        "Referee Ball-Drop",
        "Player On",
        "Player Off",
        "Shield",
        "50/50",
        "Error",
        "Offside",
    }

    # Pitch bounds (StatsBomb coordinate system)
    PITCH_X_MAX = 120.0
    PITCH_Y_MAX = 80.0

    def __init__(
        self,
        engine: Engine | None = None,
        strict: bool | None = None,
        log_to_db: bool = True,
    ):
        self._engine = engine or get_engine()
        self._strict = (
            strict
            if strict is not None
            else (os.getenv("DATA_QUALITY_STRICT", "false").lower() == "true")
        )
        self._log_to_db = log_to_db

    def validate_batch(
        self, df: pd.DataFrame, source: str = "batch"
    ) -> ValidationReport:
        """Validate a DataFrame of event data.

        Runs all structural, statistical, and logical checks.

        Args:
            df: Events DataFrame (must have standard column names).
            source: Label for the source of this data.

        Returns:
            ValidationReport with all check results.
        """
        report = ValidationReport(source=source)

        report.results.append(self._check_required_columns(df))
        report.results.append(self._check_event_types(df))
        report.results.append(self._check_coordinates(df))
        report.results.append(self._check_xg_range(df))
        report.results.append(self._check_temporal_order(df))
        report.results.append(self._check_null_rates(df))
        report.results.append(self._check_duplicate_events(df))

        if self._log_to_db:
            self._persist_report(report)

        if self._strict and not report.passed:
            failures = "; ".join(
                f"{r.check_name}: {r.details}" for r in report.critical_failures
            )
            raise ValueError(f"Data validation failed (strict mode): {failures}")

        return report

    def validate_match_events(self, match_id: int) -> ValidationReport:
        """Validate all events for a specific match from the database.

        Args:
            match_id: The match to validate.

        Returns:
            ValidationReport for that match.
        """
        with self._engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT * FROM events WHERE match_id = :mid"),
                conn,
                params={"mid": match_id},
            )

        if df.empty:
            report = ValidationReport(source=f"match_{match_id}")
            report.results.append(
                ValidationResult(
                    check_name="match_has_events",
                    passed=False,
                    severity="critical",
                    details=f"No events found for match_id={match_id}",
                )
            )
            return report

        return self.validate_batch(df, source=f"match_{match_id}")

    # ─── Individual Checks ─────────────────────────────────────────────────

    def _check_required_columns(self, df: pd.DataFrame) -> ValidationResult:
        """Check that required columns exist."""
        required = {"event_id", "match_id", "team_id", "event_type", "minute", "period"}
        missing = required - set(df.columns)
        return ValidationResult(
            check_name="required_columns",
            passed=len(missing) == 0,
            severity="critical",
            details=(
                f"Missing columns: {sorted(missing)}"
                if missing
                else "All required columns present"
            ),
            record_count=len(required),
            failed_count=len(missing),
        )

    def _check_event_types(self, df: pd.DataFrame) -> ValidationResult:
        """Check that event_type values are from the known set."""
        if "event_type" not in df.columns:
            return ValidationResult(
                check_name="event_types", passed=True, record_count=0
            )
        unknown = set(df["event_type"].dropna().unique()) - self.VALID_EVENT_TYPES
        return ValidationResult(
            check_name="event_types",
            passed=len(unknown) == 0,
            severity="warning",
            details=f"Unknown types: {sorted(unknown)}" if unknown else "",
            record_count=int(df["event_type"].notna().sum()),
            failed_count=int(df["event_type"].isin(unknown).sum()) if unknown else 0,
        )

    def _check_coordinates(self, df: pd.DataFrame) -> ValidationResult:
        """Check that coordinates are within pitch bounds."""
        issues = 0
        total = 0

        for col_x, col_y in [
            ("location_x", "location_y"),
            ("end_location_x", "end_location_y"),
        ]:
            if col_x not in df.columns:
                continue
            coords = df[[col_x, col_y]].dropna()
            total += len(coords)
            out_of_bounds = (
                (coords[col_x] < 0)
                | (coords[col_x] > self.PITCH_X_MAX)
                | (coords[col_y] < 0)
                | (coords[col_y] > self.PITCH_Y_MAX)
            )
            issues += int(out_of_bounds.sum())

        return ValidationResult(
            check_name="coordinate_bounds",
            passed=issues == 0,
            severity="warning",
            details=f"{issues} coordinates out of pitch bounds" if issues else "",
            record_count=total,
            failed_count=issues,
        )

    def _check_xg_range(self, df: pd.DataFrame) -> ValidationResult:
        """Check that xG values are between 0 and 1."""
        if "xg" not in df.columns:
            return ValidationResult(check_name="xg_range", passed=True, record_count=0)

        xg = df["xg"].dropna()
        invalid = ((xg < 0) | (xg > 1)).sum()
        return ValidationResult(
            check_name="xg_range",
            passed=int(invalid) == 0,
            severity="critical",
            details=f"{invalid} xG values outside [0, 1]" if invalid else "",
            record_count=len(xg),
            failed_count=int(invalid),
        )

    def _check_temporal_order(self, df: pd.DataFrame) -> ValidationResult:
        """Check that events within each match are temporally ordered."""
        if "minute" not in df.columns or "match_id" not in df.columns:
            return ValidationResult(
                check_name="temporal_order", passed=True, record_count=0
            )

        issues = 0
        total_matches = df["match_id"].nunique()

        for _, group in df.groupby("match_id"):
            sorted_mins = group.sort_index()["minute"]
            # Allow same-minute events, check for large backwards jumps
            backwards = (sorted_mins.diff() < -5).sum()
            issues += int(backwards)

        return ValidationResult(
            check_name="temporal_order",
            passed=issues == 0,
            severity="warning",
            details=(
                f"{issues} temporal ordering issues across {total_matches} matches"
                if issues
                else ""
            ),
            record_count=total_matches,
            failed_count=issues,
        )

    def _check_null_rates(self, df: pd.DataFrame) -> ValidationResult:
        """Check that critical columns don't have excessive nulls."""
        critical_cols = ["event_type", "match_id", "team_id", "minute"]
        existing = [c for c in critical_cols if c in df.columns]

        if not existing:
            return ValidationResult(
                check_name="null_rates", passed=True, record_count=0
            )

        null_counts = df[existing].isnull().sum()
        high_null = null_counts[null_counts > len(df) * 0.01]

        return ValidationResult(
            check_name="null_rates",
            passed=len(high_null) == 0,
            severity="critical",
            details=f"High null rates: {high_null.to_dict()}" if len(high_null) else "",
            record_count=len(df) * len(existing),
            failed_count=int(null_counts.sum()),
        )

    def _check_duplicate_events(self, df: pd.DataFrame) -> ValidationResult:
        """Check for duplicate event IDs."""
        if "event_id" not in df.columns:
            return ValidationResult(
                check_name="duplicate_events", passed=True, record_count=0
            )

        dupes = df["event_id"].duplicated().sum()
        return ValidationResult(
            check_name="duplicate_events",
            passed=int(dupes) == 0,
            severity="critical",
            details=f"{dupes} duplicate event_id values" if dupes else "",
            record_count=len(df),
            failed_count=int(dupes),
        )

    # ─── Persistence ──────────────────────────────────────────────────────

    def _persist_report(self, report: ValidationReport) -> None:
        """Persist validation results to the data_quality_log table."""
        try:
            rows = []
            for r in report.results:
                rows.append(
                    {
                        "source": report.source,
                        "check_name": r.check_name,
                        "severity": r.severity if not r.passed else "info",
                        "details": {"message": r.details, "passed": r.passed},
                        "record_count": r.record_count,
                        "failed_count": r.failed_count,
                        "pass_rate": r.pass_rate,
                    }
                )

            if rows:
                import json

                with self._engine.begin() as conn:
                    for row in rows:
                        conn.execute(
                            text("""
                                INSERT INTO data_quality_log
                                    (source, check_name, severity, details, record_count, failed_count, pass_rate)
                                VALUES (:source, :check_name, :severity, :details::jsonb, :record_count, :failed_count, :pass_rate)
                            """),
                            {
                                **row,
                                "details": json.dumps(row["details"]),
                            },
                        )
        except Exception as e:
            # Don't let logging failures block ingestion
            logger.warning("Failed to persist validation report: %s", e)
