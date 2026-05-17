"""Configuration and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection parameters."""

    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    db: str = os.getenv("POSTGRES_DB", "football_analytics")
    user: str = os.getenv("POSTGRES_USER", "analyst")
    password: str = os.getenv("POSTGRES_PASSWORD", "changeme")

    @property
    def url(self) -> str:
        """SQLAlchemy connection URL."""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class AppConfig:
    """Application-wide settings."""

    db: DatabaseConfig = DatabaseConfig()
    data_dir: Path = _PROJECT_ROOT / "data"
    raw_dir: Path = _PROJECT_ROOT / "data" / "raw"
    processed_dir: Path = _PROJECT_ROOT / "data" / "processed"
    dash_debug: bool = os.getenv("DASH_DEBUG", "false").lower() == "true"
    dash_port: int = int(os.getenv("DASH_PORT", "8050"))


config = AppConfig()
