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
        "pull_request": {
            "number": 42,
            "head": {"sha": "abc123", "repo": {"full_name": "acme/widgets"}},
        },
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
    assert data["pull_request"] == 42
    assert "review_id" in data


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


def test_installation_created_persists_row(client: TestClient) -> None:
    from backend.db.models import Installation
    from backend.tests.conftest import _TestSessionLocal

    payload = {
        "action": "created",
        "installation": {
            "id": 999111,
            "account": {"login": "octocat", "type": "User"},
            "app_slug": "codeguardian",
            "repository_selection": "selected",
            "permissions": {"pull_requests": "write"},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "installation",
            "X-Hub-Signature-256": _sign(body),
        },
        content=body,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "processed"
    assert data["installation_id"] == 999111

    with _TestSessionLocal() as session:
        inst = session.get(Installation, 999111)
        assert inst is not None
        assert inst.account_login == "octocat"
        assert inst.account_type == "User"
        assert inst.target_type == "selected"
        assert inst.suspended_at is None
        assert inst.uninstalled_at is None


def test_installation_deleted_soft_deletes_row(client: TestClient) -> None:
    from backend.db.models import Installation
    from backend.tests.conftest import _TestSessionLocal

    with _TestSessionLocal() as session:
        inst = Installation(id=999222, account_login="octocat", account_type="User")
        session.add(inst)
        session.commit()

    payload = {
        "action": "deleted",
        "installation": {"id": 999222, "account": {"login": "octocat"}},
    }
    body = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "installation",
            "X-Hub-Signature-256": _sign(body),
        },
        content=body,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "processed"

    with _TestSessionLocal() as session:
        inst = session.get(Installation, 999222)
        assert inst is not None
        assert inst.uninstalled_at is not None


def test_installation_suspend_and_unsuspend(client: TestClient) -> None:
    from backend.db.models import Installation
    from backend.tests.conftest import _TestSessionLocal

    with _TestSessionLocal() as session:
        inst = Installation(id=999333, account_login="octocat", account_type="User")
        session.add(inst)
        session.commit()

    # Suspend
    suspend_body = json.dumps({
        "action": "suspend",
        "installation": {"id": 999333, "account": {"login": "octocat"}},
    }).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "installation",
            "X-Hub-Signature-256": _sign(suspend_body),
        },
        content=suspend_body,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "processed"

    with _TestSessionLocal() as session:
        inst = session.get(Installation, 999333)
        assert inst is not None
        assert inst.suspended_at is not None

    # Unsuspend
    unsuspend_body = json.dumps({
        "action": "unsuspend",
        "installation": {"id": 999333, "account": {"login": "octocat"}},
    }).encode("utf-8")
    resp = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "installation",
            "X-Hub-Signature-256": _sign(unsuspend_body),
        },
        content=unsuspend_body,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "processed"

    with _TestSessionLocal() as session:
        inst = session.get(Installation, 999333)
        assert inst is not None
        assert inst.suspended_at is None


def test_pull_request_with_installation_auto_creates_and_links(client: TestClient) -> None:
    from unittest.mock import patch
    from backend.db.models import Installation, Review
    from backend.tests.conftest import _TestSessionLocal

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 10,
            "head": {"sha": "def456", "repo": {"full_name": "org/repo"}},
        },
        "repository": {"full_name": "org/repo"},
        "installation": {
            "id": 888777,
            "account": {"login": "org", "type": "Organization"},
        },
    }
    body = json.dumps(payload).encode("utf-8")

    with patch("backend.services.review_service.run_review") as mock_run_review:
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
        review_id = data["review_id"]

        mock_run_review.assert_not_called()

    with _TestSessionLocal() as session:
        inst = session.get(Installation, 888777)
        assert inst is not None
        assert inst.account_login == "org"

        review = session.get(Review, review_id)
        assert review is not None
        assert review.installation_id == 888777


def test_pull_request_with_suspended_installation_is_rejected(client: TestClient) -> None:
    from datetime import datetime, timezone
    from backend.db.models import Installation
    from backend.tests.conftest import _TestSessionLocal

    with _TestSessionLocal() as session:
        inst = Installation(
            id=777666,
            account_login="suspended-org",
            suspended_at=datetime.now(timezone.utc),
        )
        session.add(inst)
        session.commit()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 11,
            "head": {"sha": "def456", "repo": {"full_name": "suspended-org/repo"}},
        },
        "repository": {"full_name": "suspended-org/repo"},
        "installation": {
            "id": 777666,
            "account": {"login": "suspended-org"},
        },
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
    assert resp.json()["status"] == "rejected"
    assert "suspended" in resp.json()["reason"]


def test_pull_request_with_manual_review_mode_is_ignored(client: TestClient) -> None:
    from unittest.mock import patch
    from backend.db.models import Installation, Review
    from backend.tests.conftest import _TestSessionLocal

    with _TestSessionLocal() as session:
        inst = Installation(
            id=555444,
            account_login="manual-org",
            review_mode="manual",
        )
        session.add(inst)
        session.commit()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 22,
            "head": {"sha": "def456", "repo": {"full_name": "manual-org/repo"}},
        },
        "repository": {"full_name": "manual-org/repo"},
        "installation": {
            "id": 555444,
            "account": {"login": "manual-org"},
        },
    }
    body = json.dumps(payload).encode("utf-8")

    with patch("backend.services.review_service.run_review") as mock_run_review:
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
        assert data["status"] == "ignored"
        assert data["reason"] == "installation review_mode is manual"
        assert data["installation_id"] == 555444

        mock_run_review.assert_not_called()

    with _TestSessionLocal() as session:
        reviews = session.query(Review).filter_by(installation_id=555444).all()
        assert len(reviews) == 0


def test_pull_request_with_auto_review_mode_proceeds(client: TestClient) -> None:
    from unittest.mock import patch
    from backend.db.models import Installation, Review
    from backend.tests.conftest import _TestSessionLocal

    with _TestSessionLocal() as session:
        inst = Installation(
            id=666555,
            account_login="auto-org",
            review_mode="auto",
        )
        session.add(inst)
        session.commit()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 33,
            "head": {"sha": "aaa111", "repo": {"full_name": "auto-org/repo"}},
        },
        "repository": {"full_name": "auto-org/repo"},
        "installation": {
            "id": 666555,
            "account": {"login": "auto-org"},
        },
    }
    body = json.dumps(payload).encode("utf-8")

    with patch("backend.services.review_service.run_review") as mock_run_review:
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
        assert "review_id" in data
        mock_run_review.assert_not_called()

