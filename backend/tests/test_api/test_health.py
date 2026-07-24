"""Tests for the health endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient


def test_liveness_returns_200(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


def test_readiness_reports_checks(client: TestClient) -> None:
    """Readiness never raises; it reports per-dependency status.

    In the test environment PostgreSQL/ChromaDB are not running, so the endpoint
    should return 503 with a structured body rather than erroring out.
    """
    resp = client.get("/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert set(body["checks"]) == {"database", "chromadb"}
