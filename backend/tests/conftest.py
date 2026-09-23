"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.db.models import Base

# A deterministic secret used to sign test webhook payloads.
TEST_WEBHOOK_SECRET = "test-webhook-secret"

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(bind=_test_engine)


def _get_test_db():
    """Yield a test DB session (in-memory SQLite)."""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session", autouse=True)
def _configure_env() -> None:
    """Set required environment before the app settings are first read."""
    os.environ["GITHUB_WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET
    os.environ["GITHUB_TOKEN"] = "fake-token-for-tests"
    # Disable LLM call pacing under test: the throttle exists to protect a real
    # provider's rate limit, and real-time sleeps would only slow the suite down.
    os.environ["LLM_MIN_CALL_INTERVAL_SECONDS"] = "0"

    from backend.config import get_settings

    get_settings.cache_clear()

    from backend.tools.llm_client import reset_throttle

    reset_throttle()


@pytest.fixture(autouse=True)
def _setup_test_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(_test_engine)
    yield
    Base.metadata.drop_all(_test_engine)


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient bound to the FastAPI app with DB overridden."""
    from unittest.mock import patch

    from backend.db.database import get_db
    from backend.main import app

    app.dependency_overrides[get_db] = _get_test_db

    with patch("backend.db.database.get_sessionmaker", return_value=_TestSessionLocal):
        yield TestClient(app)

    app.dependency_overrides.clear()
