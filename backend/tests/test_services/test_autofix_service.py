"""Tests for the Auto-Fix Service."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Finding, Review
from backend.services.autofix_service import (
    AutofixError,
    AutofixResult,
    approve_autofix,
    create_autofix,
    reject_autofix,
    _apply_single_fix,
    _insert_docstring,
    _format_docstring,
    AppliedFix,
    SkippedFix,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


def _create_completed_review(db, *, is_fork=False, with_fixable=True):
    """Helper to create a completed review with optional fixable findings."""
    review = Review(
        repo_full_name="owner/repo",
        pr_number=42,
        commit_sha="abc123",
        status="completed",
        is_fork=is_fork,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    if with_fixable:
        fix_data = json.dumps({
            "target_function": "process_data",
            "target_file": "src/app.py",
            "test_code": "import pytest\nfrom src.app import process_data\n\ndef test_process_data():\n    assert process_data() is not None\n",
        })
        finding = Finding(
            review_id=review.id,
            agent="test_gap",
            severity="high",
            title="Untested: process_data",
            detail="Risk 8/10",
            file_path="src/app.py",
            line=10,
            fix_data=fix_data,
        )
        db.add(finding)

        doc_fix_data = json.dumps({
            "target_function": "calculate",
            "target_file": "src/utils.py",
            "docstring": "Calculate the sum of x and y.\n\nArgs:\n    x: First number.\n    y: Second number.",
        })
        finding2 = Finding(
            review_id=review.id,
            agent="documentation",
            severity="medium",
            title="Docstring missing: calculate",
            detail="",
            file_path="src/utils.py",
            line=5,
            fix_data=doc_fix_data,
        )
        db.add(finding2)
        db.commit()

    return review


class TestCreateAutofix:
    def test_raises_on_nonexistent_review(self, db_session):
        with pytest.raises(AutofixError, match="not found"):
            create_autofix(db_session, 9999)

    def test_raises_on_non_completed_review(self, db_session):
        review = Review(
            repo_full_name="owner/repo",
            pr_number=1,
            commit_sha="sha1",
            status="running",
        )
        db_session.add(review)
        db_session.commit()

        with pytest.raises(AutofixError, match="running"):
            create_autofix(db_session, review.id)

    def test_raises_on_fork_pr(self, db_session):
        review = _create_completed_review(db_session, is_fork=True)

        with pytest.raises(AutofixError, match="unavailable for fork"):
            create_autofix(db_session, review.id)

    def test_raises_on_already_pending(self, db_session):
        review = _create_completed_review(db_session)
        review.autofix_status = "pending_approval"
        review.autofix_branch = "codeguardian/autofix/1"
        db_session.commit()

        with pytest.raises(AutofixError, match="already exists"):
            create_autofix(db_session, review.id)

    def test_raises_on_no_fixable_findings(self, db_session):
        review = _create_completed_review(db_session, with_fixable=False)

        with pytest.raises(AutofixError, match="no fixable findings"):
            create_autofix(db_session, review.id)

    @patch("backend.services.autofix_service._apply_fixes_and_push")
    @patch("backend.services.autofix_service.get_settings")
    def test_success_sets_pending_approval(self, mock_settings, mock_apply, db_session):
        mock_settings.return_value.require.return_value = "fake-token"
        mock_apply.return_value = AutofixResult(
            branch="codeguardian/autofix/1",
            applied_fixes=[AppliedFix("process_data", "src/app.py", "test")],
            skipped_fixes=[],
        )

        review = _create_completed_review(db_session)
        result = create_autofix(db_session, review.id)

        assert result.branch == f"codeguardian/autofix/{review.id}"
        assert len(result.applied_fixes) == 1
        db_session.refresh(review)
        assert review.autofix_status == "pending_approval"
        assert review.autofix_branch == f"codeguardian/autofix/{review.id}"

    @patch("backend.services.autofix_service._apply_fixes_and_push")
    @patch("backend.services.autofix_service.get_settings")
    def test_raises_when_all_fixes_fail_validation(self, mock_settings, mock_apply, db_session):
        mock_settings.return_value.require.return_value = "fake-token"
        mock_apply.return_value = AutofixResult(
            applied_fixes=[],
            skipped_fixes=[SkippedFix("func", "file.py", "function removed")],
        )

        review = _create_completed_review(db_session)
        with pytest.raises(AutofixError, match="All fixes failed"):
            create_autofix(db_session, review.id)


class TestApproveAutofix:
    def test_success(self, db_session):
        review = _create_completed_review(db_session)
        review.autofix_status = "pending_approval"
        review.autofix_branch = "codeguardian/autofix/1"
        db_session.commit()

        approve_autofix(db_session, review.id, approved_by="dhyan")

        db_session.refresh(review)
        assert review.autofix_status == "approved"
        assert review.autofix_approved_by == "dhyan"
        assert review.autofix_approved_at is not None

    def test_raises_on_nonexistent(self, db_session):
        with pytest.raises(AutofixError, match="not found"):
            approve_autofix(db_session, 9999, approved_by="user")

    def test_raises_on_non_pending(self, db_session):
        review = _create_completed_review(db_session)
        review.autofix_status = "approved"
        db_session.commit()

        with pytest.raises(AutofixError, match="approved"):
            approve_autofix(db_session, review.id, approved_by="user")

    def test_raises_on_no_autofix_status(self, db_session):
        review = _create_completed_review(db_session)
        # autofix_status is None

        with pytest.raises(AutofixError, match="None"):
            approve_autofix(db_session, review.id, approved_by="user")


class TestRejectAutofix:
    def test_success(self, db_session):
        review = _create_completed_review(db_session)
        review.autofix_status = "pending_approval"
        db_session.commit()

        reject_autofix(db_session, review.id)

        db_session.refresh(review)
        assert review.autofix_status == "rejected"

    def test_raises_on_non_pending(self, db_session):
        review = _create_completed_review(db_session)
        review.autofix_status = "approved"
        db_session.commit()

        with pytest.raises(AutofixError, match="approved"):
            reject_autofix(db_session, review.id)


class TestInsertDocstring:
    def test_inserts_into_function_without_docstring(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def calculate(x, y):\n    return x + y\n")
            f.flush()
            path = f.name

        try:
            success = _insert_docstring(path, "calculate", "Calculate sum of x and y.")
            assert success is True

            with open(path) as f:
                content = f.read()
            assert '"""Calculate sum of x and y."""' in content
            assert "return x + y" in content
        finally:
            os.unlink(path)

    def test_replaces_existing_docstring(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('def calculate(x, y):\n    """Old doc."""\n    return x + y\n')
            f.flush()
            path = f.name

        try:
            success = _insert_docstring(path, "calculate", "New docstring.")
            assert success is True

            with open(path) as f:
                content = f.read()
            assert "New docstring" in content
            assert "Old doc" not in content
        finally:
            os.unlink(path)

    def test_returns_false_for_nonexistent_function(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def other():\n    pass\n")
            f.flush()
            path = f.name

        try:
            success = _insert_docstring(path, "nonexistent", "Doc.")
            assert success is False
        finally:
            os.unlink(path)


class TestFormatDocstring:
    def test_single_line(self):
        lines = _format_docstring("Short doc.", "    ")
        assert lines == ['    """Short doc."""\n']

    def test_multi_line(self):
        doc = "Summary line.\n\nDetailed description."
        lines = _format_docstring(doc, "    ")
        assert lines[0] == '    """Summary line.\n'
        assert lines[-1] == '    """\n'


class TestAutofixOutcomePersistence:
    """The applied/skipped split must outlive the HTTP response that reported it.

    It is the evidence that apply-time re-validation rejected unusable fixes, so the
    dashboard has to still have it after a page refresh.
    """

    def _patched_result(self, db, monkeypatch, result: AutofixResult):
        review = _create_completed_review(db)
        monkeypatch.setattr(
            "backend.services.autofix_service._apply_fixes_and_push",
            lambda **kwargs: result,
        )
        monkeypatch.setattr(
            "backend.services.autofix_service.get_settings",
            lambda: MagicMock(require=lambda _field: "fake-token"),
        )
        return review

    def test_applied_count_and_skipped_fixes_are_persisted(self, db_session, monkeypatch):
        result = AutofixResult(
            applied_fixes=[
                AppliedFix(target_function="calculate", target_file="src/utils.py",
                           fix_type="docstring"),
            ],
            skipped_fixes=[
                SkippedFix(target_function="process_data", target_file="src/app.py",
                           reason="Import references non-existent module 'src'"),
            ],
        )
        review = self._patched_result(db_session, monkeypatch, result)

        create_autofix(db_session, review.id)

        db_session.refresh(review)
        assert review.autofix_status == "pending_approval"
        assert review.autofix_applied_count == 1

        stored = json.loads(review.autofix_skipped_fixes)
        assert len(stored) == 1
        assert stored[0]["target"] == "src/app.py:process_data"
        assert stored[0]["target_function"] == "process_data"
        assert "non-existent module" in stored[0]["reason"]

    def test_no_skips_persists_an_empty_list_not_null(self, db_session, monkeypatch):
        """An empty list means "nothing was rejected"; null would mean "unknown"."""
        result = AutofixResult(
            applied_fixes=[
                AppliedFix(target_function="calculate", target_file="src/utils.py",
                           fix_type="docstring"),
            ],
            skipped_fixes=[],
        )
        review = self._patched_result(db_session, monkeypatch, result)

        create_autofix(db_session, review.id)

        db_session.refresh(review)
        assert review.autofix_applied_count == 1
        assert json.loads(review.autofix_skipped_fixes) == []

    def test_create_autofix_uses_installation_token(self, db_session, monkeypatch):
        review = _create_completed_review(db_session)
        review.installation_id = 998877
        db_session.commit()

        captured_token = {}

        def mock_apply(review, findings, branch_name, token):
            captured_token["token"] = token
            return AutofixResult(applied_fixes=[AppliedFix("fn", "file.py", "docstring")])

        monkeypatch.setattr("backend.services.autofix_service._apply_fixes_and_push", mock_apply)
        with patch("backend.tools.github_app.get_installation_token", return_value="inst-tok-456") as mock_git_token:
            create_autofix(db_session, review.id)
            mock_git_token.assert_called_once_with(998877)
            assert captured_token["token"] == "inst-tok-456"

