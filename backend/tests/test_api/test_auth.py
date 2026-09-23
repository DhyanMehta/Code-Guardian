"""Tests for GitHub OAuth login and session auth endpoints (/auth/*)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import jwt
from starlette.testclient import TestClient

from backend.db.models import Installation, User, UserInstallation
from backend.tests.conftest import _TestSessionLocal


def test_github_login_returns_url_and_state(client: TestClient) -> None:
    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.github_app_client_id = "test-client-id"
        resp = client.get("/auth/github/login")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert "state" in data
        assert "client_id=test-client-id" in data["url"]
        assert f"state={data['state']}" in data["url"]


def test_github_callback_exchanges_code_and_creates_user_without_token_storage(client: TestClient) -> None:
    fake_token_resp = MagicMock(
        status_code=200,
        json=lambda: {"access_token": "gho_fake_user_token_12345"},
    )
    fake_user_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "id": 1234567,
            "login": "testuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/1234567",
        },
    )
    fake_inst_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "installations": [
                {
                    "id": 998877,
                    "account": {"login": "testuser", "type": "User"},
                    "app_slug": "codeguardian",
                    "repository_selection": "selected",
                    "permissions": {"administration": "write"},
                }
            ]
        },
    )

    mock_client = MagicMock()
    mock_client.post.return_value = fake_token_resp
    mock_client.get.side_effect = [fake_user_resp, fake_inst_resp]

    with patch("backend.api.auth.get_settings") as mock_settings, \
         patch("backend.api.auth.httpx.Client") as mock_httpx_cls:
        mock_settings.return_value.require.side_effect = lambda key: {
            "github_app_client_id": "test-client-id",
            "github_app_client_secret": "test-client-secret",
            "session_secret": "test-session-secret-1234567890123456",
        }[key]
        mock_httpx_cls.return_value.__enter__.return_value = mock_client

        resp = client.post(
            "/auth/github/callback",
            json={"code": "auth-code-xyz", "state": "test-state"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["github_login"] == "testuser"
        assert data["user"]["github_user_id"] == 1234567

        # Decode session JWT to verify payload
        payload = jwt.decode(
            data["token"],
            "test-session-secret-1234567890123456",
            algorithms=["HS256"],
        )
        assert payload["user_id"] == data["user"]["id"]
        assert payload["github_login"] == "testuser"

    # Verify DB state: User exists, has NO access_token_enc attribute, and is linked to installation
    with _TestSessionLocal() as session:
        db_user = session.query(User).filter(User.github_user_id == 1234567).first()
        assert db_user is not None
        assert db_user.github_login == "testuser"
        assert not hasattr(db_user, "access_token_enc")

        link = session.query(UserInstallation).filter(
            UserInstallation.user_id == db_user.id,
            UserInstallation.installation_id == 998877,
        ).first()
        assert link is not None
        assert link.role == "admin"


def test_auth_me_requires_valid_bearer_token(client: TestClient) -> None:
    # 1. Missing header
    resp = client.get("/auth/me")
    assert resp.status_code == 401

    # 2. Invalid token
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401

    # 3. Valid token
    with _TestSessionLocal() as session:
        user = User(github_user_id=7654321, github_login="autheduser")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

        inst = Installation(id=554433, account_login="autheduser", account_type="User")
        session.add(inst)
        link = UserInstallation(user_id=user_id, installation_id=554433, role="admin")
        session.add(link)
        session.commit()

    token = jwt.encode(
        {"user_id": user_id, "github_login": "autheduser", "exp": 9999999999},
        "test-session-secret-1234567890123456",
        algorithm="HS256",
    )

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = "test-session-secret-1234567890123456"
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["github_login"] == "autheduser"
        assert len(data["installations"]) == 1
        assert data["installations"][0]["id"] == 554433


def test_logout_endpoint(client: TestClient) -> None:
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
