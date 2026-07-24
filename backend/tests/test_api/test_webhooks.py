"""Tests for the GitHub webhook receiver signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json

from starlette.testclient import TestClient

from backend.tests.conftest import TEST_WEBHOOK_SECRET


def _sign(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Return a GitHub-style ``sha256=<hexdigest>`` signature for ``body``."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_missing_signature_is_rejected(client: TestClient) -> None:
    resp = client.post(
        "/webhooks/github",
        headers={"X-GitHub-Event": "pull_request"},
        content=b"{}",
    )
    assert resp.status_code == 401


def test_invalid_signature_is_rejected(client: TestClient) -> None:
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
        content=b"{}",
    )
    assert resp.status_code == 401


def test_valid_signature_pull_request_opened_is_accepted(client: TestClient) -> None:
    payload = {
        "action": "opened",
        "pull_request": {"number": 42},
        "repository": {"full_name": "acme/widgets"},
    }
    body = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
        content=body,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["repository"] == "acme/widgets"
    assert data["pull_request"] == "42"


def test_valid_signature_non_pull_request_event_is_ignored(client: TestClient) -> None:
    body = json.dumps({"zen": "ping"}).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": _sign(body),
        },
        content=body,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


def test_valid_signature_unreviewable_action_is_ignored(client: TestClient) -> None:
    body = json.dumps({"action": "labeled", "pull_request": {"number": 1}}).encode()
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
        },
        content=body,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
