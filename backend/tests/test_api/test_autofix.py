"""Tests for the Auto-Fix API endpoints."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from backend.db.models import Finding, Review


def _create_completed_review_via_db(client: TestClient):
    """Insert a completed review directly via the test DB."""
    from backend.tests.conftest import _TestSessionLocal

    session = _TestSessionLocal()
    review = Review(
        repo_full_name="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        status="completed",
        is_fork=False,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    review_id = review.id

    fix_data = json.dumps({
        "target_function": "process_data",
        "target_file": "src/app.py",
        "test_code": "def test_process_data():\n    pass\n",
    })
    finding = Finding(
        review_id=review_id,
        agent="test_gap",
        severity="high",
        title="Untested: process_data",
        detail="Risk 8/10",
        file_path="src/app.py",
        line=10,
        fix_data=fix_data,
    )
    session.add(finding)
    session.commit()
    session.close()
    return review_id


class TestCreateAutofixEndpoint:
    def test_404_for_nonexistent_review(self, client: TestClient):
        resp = client.post("/reviews/9999/autofix")
        assert resp.status_code == 404

    def test_400_for_no_fixable_findings(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=1,
            commit_sha="sha1",
            status="completed",
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        session.close()

        resp = client.post(f"/reviews/{review.id}/autofix")
        assert resp.status_code == 400

    def test_422_for_fork_pr(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=2,
            commit_sha="sha2",
            status="completed",
            is_fork=True,
        )
        session.add(review)
        session.commit()
        session.refresh(review)

        finding = Finding(
            review_id=review.id,
            agent="test_gap",
            severity="high",
            title="test",
            fix_data=json.dumps({"target_function": "f", "target_file": "a.py", "test_code": "x"}),
        )
        session.add(finding)
        session.commit()
        review_id = review.id
        session.close()

        resp = client.post(f"/reviews/{review_id}/autofix")
        assert resp.status_code == 422
        assert "fork" in resp.json()["detail"].lower()

    def test_409_for_already_pending(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=3,
            commit_sha="sha3",
            status="completed",
            autofix_status="pending_approval",
            autofix_branch="codeguardian/autofix/1",
        )
        session.add(review)
        session.commit()
        session.refresh(review)

        finding = Finding(
            review_id=review.id,
            agent="test_gap",
            severity="high",
            title="test",
            fix_data=json.dumps({"target_function": "f", "target_file": "a.py", "test_code": "x"}),
        )
        session.add(finding)
        session.commit()
        review_id = review.id
        session.close()

        resp = client.post(f"/reviews/{review_id}/autofix")
        assert resp.status_code == 409

    @patch("backend.services.autofix_service._apply_fixes_and_push")
    @patch("backend.services.autofix_service.get_settings")
    def test_201_on_success(self, mock_settings, mock_apply, client: TestClient):
        from backend.services.autofix_service import AutofixResult, AppliedFix

        mock_settings.return_value.require.return_value = "fake-token"
        mock_apply.return_value = AutofixResult(
            branch="codeguardian/autofix/1",
            applied_fixes=[AppliedFix("process_data", "src/app.py", "test")],
            skipped_fixes=[],
        )

        review_id = _create_completed_review_via_db(client)
        resp = client.post(f"/reviews/{review_id}/autofix")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["applied_fixes"] == 1
        assert "codeguardian/autofix" in data["branch"]


class TestApproveAutofixEndpoint:
    def test_404_for_nonexistent(self, client: TestClient):
        resp = client.post(
            "/reviews/9999/autofix/approve",
            json={"approved_by": "user"},
        )
        assert resp.status_code == 404

    def test_409_for_non_pending(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=5,
            commit_sha="sha5",
            status="completed",
            autofix_status=None,
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        review_id = review.id
        session.close()

        resp = client.post(
            f"/reviews/{review_id}/autofix/approve",
            json={"approved_by": "user"},
        )
        assert resp.status_code == 409

    def test_200_on_success(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=6,
            commit_sha="sha6",
            status="completed",
            autofix_status="pending_approval",
            autofix_branch="codeguardian/autofix/1",
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        review_id = review.id
        session.close()

        resp = client.post(
            f"/reviews/{review_id}/autofix/approve",
            json={"approved_by": "dhyan"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


class TestRejectAutofixEndpoint:
    def test_200_on_success(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=7,
            commit_sha="sha7",
            status="completed",
            autofix_status="pending_approval",
            autofix_branch="codeguardian/autofix/7",
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        review_id = review.id
        session.close()

        resp = client.post(f"/reviews/{review_id}/autofix/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_409_for_already_approved(self, client: TestClient):
        from backend.tests.conftest import _TestSessionLocal

        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=8,
            commit_sha="sha8",
            status="completed",
            autofix_status="approved",
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        review_id = review.id
        session.close()

        resp = client.post(f"/reviews/{review_id}/autofix/reject")
        assert resp.status_code == 409
