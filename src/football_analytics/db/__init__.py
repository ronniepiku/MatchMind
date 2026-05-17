"""Database package — schema management and connection utilities."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from football_analytics.config import config


def get_engine(echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine with connection pooling.

    Uses pool_size=5 with overflow=10 for concurrent analytical queries.
    """
    return create_engine(
        config.db.url,
        echo=echo,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def get_session(engine: Engine | None = None) -> Session:
    """Get a new database session."""
    if engine is None:
        engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()
