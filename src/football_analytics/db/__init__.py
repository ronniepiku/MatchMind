"""Database package — schema management and connection utilities."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from football_analytics.config import config

# Module-level singleton engine for connection reuse
_engine: Engine | None = None


def get_engine(echo: bool = False) -> Engine:
    """Create or return a SQLAlchemy engine with optimised connection pooling.

    Uses a module-level singleton to avoid creating multiple pools.
    Pool settings are tuned for concurrent API workloads.
    """
    global _engine
    if _engine is not None:
        return _engine

    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))

    _engine = create_engine(
        config.db.url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=20,
        connect_args={"options": "-c statement_timeout=30000"},
    )
    return _engine


def reset_engine() -> None:
    """Dispose the current engine and clear the singleton.

    Useful for test teardown or reconnecting after a database restart.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def check_connectivity() -> bool:
    """Check if the database is reachable. Returns True if healthy."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_session(engine: Engine | None = None) -> Session:
    """Get a new database session."""
    if engine is None:
        engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()
