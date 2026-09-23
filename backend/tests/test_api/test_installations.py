"""Tests for Installations and repository discovery endpoints (/installations/*)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt
from starlette.testclient import TestClient

from backend.db.models import Installation, User, UserInstallation
from backend.tests.conftest import _TestSessionLocal

_TEST_SECRET = "test-secret-for-installations-tests-12345"


def _create_user_and_installation(linked: bool = True, suspended: bool = False):
    with _TestSessionLocal() as session:
        user = User(github_user_id=10101, github_login="devuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        from datetime import datetime, timezone
        inst = Installation(
            id=123123,
            account_login="devuser",
            account_type="User",
            app_slug="codeguardian",
            target_type="selected",
            suspended_at=datetime.now(timezone.utc) if suspended else None,
        )
        session.add(inst)
        if linked:
            link = UserInstallation(user_id=user.id, installation_id=inst.id, role="admin")
            session.add(link)
        session.commit()
        return user.id, inst.id


def _get_auth_headers(user_id: int) -> dict[str, str]:
    token = jwt.encode(
        {"user_id": user_id, "github_login": "devuser", "exp": 9999999999},
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_list_installations_unauthenticated_is_401(client: TestClient) -> None:
    resp = client.get("/installations")
    assert resp.status_code == 401


def test_list_installations_returns_linked_installations(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True)
    headers = _get_auth_headers(user_id)

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.get("/installations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == inst_id
        assert data[0]["account_login"] == "devuser"
        assert data[0]["role"] == "admin"


def test_list_repos_checks_access(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=False)
    headers = _get_auth_headers(user_id)

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.get(f"/installations/{inst_id}/repos", headers=headers)
        assert resp.status_code == 403


def test_list_repos_live_query_success(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True)
    headers = _get_auth_headers(user_id)

    fake_gh_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "total_count": 1,
            "repositories": [
                {
                    "id": 555,
                    "name": "httpx",
                    "full_name": "devuser/httpx",
                    "private": False,
                    "html_url": "https://github.com/devuser/httpx",
                    "default_branch": "master",
                    "open_issues_count": 2,
                }
            ],
        },
    )

    mock_client = MagicMock()
    mock_client.get.return_value = fake_gh_resp

    with patch("backend.api.auth.get_settings") as mock_settings, \
         patch("backend.api.installations.get_installation_token", return_value="fake-inst-tok"), \
         patch("backend.api.installations.httpx.Client") as mock_httpx:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        mock_httpx.return_value.__enter__.return_value = mock_client

        resp = client.get(f"/installations/{inst_id}/repos", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "devuser/httpx"
        assert data[0]["default_branch"] == "master"


def test_list_pulls_success(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True)
    headers = _get_auth_headers(user_id)

    fake_pr = MagicMock()
    fake_pr.number = 42
    fake_pr.title = "Add cool feature"
    fake_pr.state = "open"
    fake_pr.head.sha = "abcdef123"
    fake_pr.user.login = "contributor"
    fake_pr.created_at = None
    fake_pr.html_url = "https://github.com/devuser/httpx/pull/42"

    mock_repo = MagicMock()
    mock_repo.get_pulls.return_value = [fake_pr]
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    with patch("backend.api.auth.get_settings") as mock_settings, \
         patch("backend.api.installations.get_installation_github", return_value=mock_gh):
        mock_settings.return_value.require.return_value = _TEST_SECRET

        resp = client.get(
            f"/installations/{inst_id}/repos/devuser/httpx/pulls",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["number"] == 42
        assert data[0]["title"] == "Add cool feature"
        assert data[0]["head_sha"] == "abcdef123"
