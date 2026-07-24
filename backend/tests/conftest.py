"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os

import pytest
from starlette.testclient import TestClient

# A deterministic secret used to sign test webhook payloads.
TEST_WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture(scope="session", autouse=True)
def _configure_env() -> None:
    """Set required environment before the app settings are first read.

    Clears the cached settings so the test secret is picked up.
    """
    os.environ["GITHUB_WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET

    from backend.config import get_settings

    get_settings.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient bound to the FastAPI app."""
    from backend.main import app

    return TestClient(app)
