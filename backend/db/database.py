"""Database engine / session setup (SQLAlchemy 2.0).

The engine is created lazily so the application and test suite can import this module
without a live PostgreSQL connection. Connections are only opened when a session or the
readiness probe actually uses the engine.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use."""
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, future=True
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the configured session factory, initializing the engine if needed."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None  # for type-checkers
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session and closing it afterwards."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
