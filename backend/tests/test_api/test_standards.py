"""Tests for the Coding Standards endpoints (/installations/{id}/standards)."""

from __future__ import annotations

from unittest.mock import patch

import jwt
from starlette.testclient import TestClient

from backend.db.models import Installation, User, UserInstallation
from backend.tests.conftest import _TestSessionLocal

_TEST_SECRET = "test-secret-for-standards-tests-12345"


def _create_user_and_installation(
    linked: bool = True,
    suspended: bool = False,
    role: str = "admin",
    inst_id: int = 441122,
    login: str = "adminuser",
    user_id_offset: int = 0,
):
    with _TestSessionLocal() as session:
        user = User(
            github_user_id=80808 + (inst_id % 1000) * 10 + user_id_offset,
            github_login=login,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        from datetime import datetime, timezone

        inst = session.get(Installation, inst_id)
        if inst is None:
            inst = Installation(
                id=inst_id,
                account_login="adminuser",
                account_type="Organization",
                app_slug="codeguardian",
                target_type="selected",
                suspended_at=datetime.now(timezone.utc) if suspended else None,
                review_mode="auto",
            )
            session.add(inst)
            session.commit()
            session.refresh(inst)

        if linked:
            link = UserInstallation(user_id=user.id, installation_id=inst.id, role=role)
            session.add(link)
            session.commit()

        return user.id, inst.id


def _get_auth_cookies(user_id: int, login: str = "adminuser") -> dict[str, str]:
    token = jwt.encode(
        {"user_id": user_id, "github_login": login, "exp": 9999999999},
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"session_jwt": token}


def test_upload_standards_admin_success(client: TestClient, tmp_path) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="admin", inst_id=5001)
    cookies = _get_auth_cookies(user_id)

    md_content = (
        "## Function Naming Rule\n\n"
        "All functions must be named with prefix acme_ and use snake_case.\n"
    ).encode("utf-8")

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("acme_rules.md", md_content, "text/markdown")},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["installation_id"] == inst_id
        assert data["filename"] == "acme_rules.md"
        assert data["chunks"] >= 1
        assert data["uploaded_at"] is not None

    with _TestSessionLocal() as session:
        inst = session.get(Installation, inst_id)
        assert inst is not None
        assert inst.standards_filename == "acme_rules.md"
        assert inst.standards_chunks >= 1
        assert inst.standards_uploaded_at is not None
        assert inst.standards_content == md_content.decode("utf-8")


def test_upload_standards_member_forbidden(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="member", inst_id=5002)
    cookies = _get_auth_cookies(user_id)

    md_content = b"## Rule A\n\nSome standard rule here.\n"

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("rules.md", md_content, "text/markdown")},
            cookies=cookies,
        )
        assert resp.status_code == 403
        assert "Operation requires 'admin' role" in resp.json()["detail"]


def test_upload_standards_non_md_rejected(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="admin", inst_id=5003)
    cookies = _get_auth_cookies(user_id)

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("rules.txt", b"plain text rules", "text/plain")},
            cookies=cookies,
        )
        assert resp.status_code == 400
        assert "Only Markdown (.md) files are supported" in resp.json()["detail"]


def test_upload_standards_oversized_rejected(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="admin", inst_id=5004)
    cookies = _get_auth_cookies(user_id)

    large_content = b"## Rule\n\n" + b"x" * (512 * 1024 + 10)

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("huge_rules.md", large_content, "text/markdown")},
            cookies=cookies,
        )
        assert resp.status_code == 400
        assert "File size exceeds maximum allowed limit" in resp.json()["detail"]


def test_get_standards_status(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="member", inst_id=5005)
    cookies = _get_auth_cookies(user_id)

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        # Initially no custom standards
        resp = client.get(f"/installations/{inst_id}/standards", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["installation_id"] == inst_id
        assert data["has_custom_standards"] is False
        assert data["filename"] is None

    # Now upload custom standards as admin
    admin_id, _ = _create_user_and_installation(
        linked=True, role="admin", inst_id=inst_id, login="adminuser_2", user_id_offset=1
    )
    admin_cookies = _get_auth_cookies(admin_id, login="adminuser_2")

    md_content = b"## Custom Rule\n\nMust use double quotes.\n"
    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        upload_resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("custom.md", md_content, "text/markdown")},
            cookies=admin_cookies,
        )
        assert upload_resp.status_code == 200

        # Check status again as member
        resp2 = client.get(f"/installations/{inst_id}/standards", cookies=cookies)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["has_custom_standards"] is True
        assert data2["filename"] == "custom.md"
        assert data2["chunks"] >= 1
        assert data2["uploaded_at"] is not None


def test_delete_standards_admin_success_and_member_forbidden(client: TestClient) -> None:
    user_id, inst_id = _create_user_and_installation(linked=True, role="admin", inst_id=5006)
    cookies = _get_auth_cookies(user_id)

    # 1. Upload custom standards
    md_content = b"## Rule\n\nCustom rule for deletion test.\n"
    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        resp = client.post(
            f"/installations/{inst_id}/standards",
            files={"file": ("to_delete.md", md_content, "text/markdown")},
            cookies=cookies,
        )
        assert resp.status_code == 200

    # 2. Member tries to delete -> 403
    member_id, _ = _create_user_and_installation(
        linked=True, role="member", inst_id=inst_id, login="memberuser_2", user_id_offset=2
    )
    member_cookies = _get_auth_cookies(member_id, login="memberuser_2")

    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        del_resp_member = client.delete(f"/installations/{inst_id}/standards", cookies=member_cookies)
        assert del_resp_member.status_code == 403

    # 3. Admin deletes -> 200
    with patch("backend.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.require.return_value = _TEST_SECRET
        del_resp_admin = client.delete(f"/installations/{inst_id}/standards", cookies=cookies)
        assert del_resp_admin.status_code == 200
        assert del_resp_admin.json()["status"] == "deleted"

    # Verify DB cleared
    with _TestSessionLocal() as session:
        inst = session.get(Installation, inst_id)
        assert inst is not None
        assert inst.standards_filename is None
        assert inst.standards_chunks is None
        assert inst.standards_uploaded_at is None
        assert inst.standards_content is None
