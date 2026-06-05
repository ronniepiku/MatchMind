"""Configuration and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")


def _get_password() -> str:
    """Get database password from environment, failing clearly if unset."""
    # Railway provides DATABASE_URL — if set, password is embedded there
    if os.getenv("DATABASE_URL"):
        return ""
    pw = os.getenv("POSTGRES_PASSWORD")
    if not pw:
        raise RuntimeError(
            "POSTGRES_PASSWORD environment variable is required. Set it in your .env file or export it before running."
        )
    return pw


def normalise_database_url(url: str) -> str:
    """Normalise a DATABASE_URL to a SQLAlchemy-compatible connection string.

    Railway/Heroku use postgres:// but SQLAlchemy requires postgresql+psycopg2://.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection parameters."""

    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "MatchMind"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "analyst"))
    password: str = field(default_factory=_get_password)

    @property
    def url(self) -> str:
        """SQLAlchemy connection URL.

        Prefers DATABASE_URL (Railway/Heroku style) over individual components.
        """
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return normalise_database_url(database_url)
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class AppConfig:
    """Application-wide settings."""

    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data")
    raw_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data" / "processed")


class _LazyConfig:
    """Lazy config wrapper — only instantiates AppConfig when first accessed."""

    _instance: AppConfig | None = None

    def __getattr__(self, name: str) -> Any:
        if _LazyConfig._instance is None:
            _LazyConfig._instance = AppConfig()
        return getattr(_LazyConfig._instance, name)


config: Any = _LazyConfig()
