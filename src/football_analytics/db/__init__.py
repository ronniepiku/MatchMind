"""Database package — schema management and connection utilities."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
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

    pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    _engine = create_engine(
        config.db.url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return _engine


def get_session(engine: Engine | None = None) -> Session:
    """Get a new database session."""
    if engine is None:
        engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()
