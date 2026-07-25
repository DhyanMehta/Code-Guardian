"""Tests for the Review Service (orchestration, persistence, stale sweep, concurrency)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Finding, Review
from backend.services.review_service import (
    STALE_REVIEW_THRESHOLD_MINUTES,
    create_review,
    run_review,
    start_review,
    sweep_stale_reviews,
    _build_summary,
    _persist_findings,
)
from backend.services.report_builder import AggregatedReport, AgentStatus, UnifiedFinding
from backend.tools.results import Severity


@pytest.fixture
def db_session():
    """Create an in-memory SQLite DB for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


class TestCreateReview:
    def test_creates_pending_review(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=42,
            head_sha="abc123",
            is_fork=False,
        )
        assert review.id is not None
        assert review.status == "pending"
        assert review.repo_full_name == "owner/repo"
        assert review.pr_number == 42
        assert review.commit_sha == "abc123"
        assert review.is_fork is False

    def test_creates_fork_review(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=10,
            head_sha="def456",
            is_fork=True,
        )
        assert review.is_fork is True


class TestStartReview:
    def test_transitions_to_running(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="sha1",
        )
        result = start_review(db_session, review)
        assert result is True
        assert review.status == "running"

    def test_concurrent_review_guard_sqlite_fallback(self, db_session):
        """Without Postgres partial index, test the basic state transition logic."""
        review1 = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="sha1",
        )
        start_review(db_session, review1)
        assert review1.status == "running"

        # Second review for same PR — in real Postgres this raises IntegrityError
        # In SQLite we can't test the partial index, but we test the logic paths
        review2 = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="sha2",
        )
        # Simulate what happens when IntegrityError is raised
        from sqlalchemy.exc import IntegrityError

        original_commit = db_session.commit
        call_count = [0]

        def mock_commit():
            call_count[0] += 1
            if call_count[0] == 1:
                raise IntegrityError("", {}, None)
            return original_commit()

        with patch.object(db_session, 'commit', side_effect=mock_commit):
            with patch.object(db_session, 'rollback'):
                with patch.object(db_session, 'merge', return_value=review2):
                    result = start_review(db_session, review2)

        assert result is False
        assert review2.status == "skipped"
        assert "Another review is already running" in review2.summary


class TestPersistFindings:
    def test_persists_all_findings(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="sha1",
        )

        report = AggregatedReport(
            findings=[
                UnifiedFinding(
                    agent="security",
                    severity=Severity.HIGH,
                    title="SQL Injection",
                    detail="Unsafe query",
                    file_path="src/db.py",
                    line=42,
                ),
                UnifiedFinding(
                    agent="test_gap",
                    severity=Severity.MEDIUM,
                    title="Untested: process",
                    detail="Risk 7/10",
                    file_path="src/app.py",
                    line=10,
                    fixable=True,
                    fix_data={"test_code": "def test_process(): pass"},
                ),
            ],
            agent_statuses=[],
        )

        _persist_findings(db_session, review, report)

        findings = db_session.query(Finding).filter_by(review_id=review.id).all()
        assert len(findings) == 2

        sec_finding = next(f for f in findings if f.agent == "security")
        assert sec_finding.severity == "high"
        assert sec_finding.title == "SQL Injection"
        assert sec_finding.fix_data is None

        tg_finding = next(f for f in findings if f.agent == "test_gap")
        assert tg_finding.severity == "medium"
        assert tg_finding.fix_data is not None
        assert json.loads(tg_finding.fix_data)["test_code"] == "def test_process(): pass"


class TestBuildSummary:
    def test_no_findings(self):
        report = AggregatedReport(findings=[], agent_statuses=[])
        assert _build_summary(report) == "No issues found."

    def test_with_findings(self):
        report = AggregatedReport(
            findings=[
                UnifiedFinding(agent="security", severity=Severity.HIGH, title="a", detail=""),
                UnifiedFinding(agent="quality", severity=Severity.MEDIUM, title="b", detail=""),
                UnifiedFinding(agent="quality", severity=Severity.MEDIUM, title="c", detail=""),
            ],
            agent_statuses=[
                AgentStatus(name="security", succeeded=True),
                AgentStatus(name="quality", succeeded=True),
                AgentStatus(name="test_gap", succeeded=False),
                AgentStatus(name="documentation", succeeded=True),
            ],
        )
        summary = _build_summary(report)
        assert "3 findings" in summary
        assert "3/4 agents succeeded" in summary


class TestSweepStaleReviews:
    def test_sweeps_stuck_reviews(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=1,
            head_sha="sha1",
        )
        review.status = "running"
        # Simulate old created_at
        review.created_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        db_session.commit()

        swept = sweep_stale_reviews(db_session)
        assert swept == 1

        db_session.refresh(review)
        assert review.status == "failed"
        assert "timed out" in review.summary

    def test_does_not_sweep_recent_running(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=2,
            head_sha="sha2",
        )
        review.status = "running"
        review.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        swept = sweep_stale_reviews(db_session)
        assert swept == 0

        db_session.refresh(review)
        assert review.status == "running"

    def test_does_not_sweep_completed(self, db_session):
        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=3,
            head_sha="sha3",
        )
        review.status = "completed"
        review.created_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        db_session.commit()

        swept = sweep_stale_reviews(db_session)
        assert swept == 0

    def test_sweeps_multiple(self, db_session):
        for i in range(3):
            r = create_review(
                db_session,
                repo_full_name=f"owner/repo{i}",
                pr_number=i,
                head_sha=f"sha{i}",
            )
            r.status = "running"
            r.created_at = datetime.now(timezone.utc) - timedelta(minutes=12)
        db_session.commit()

        swept = sweep_stale_reviews(db_session)
        assert swept == 3


class TestRunReview:
    @patch("backend.services.review_service._post_pr_comment")
    @patch("backend.services.review_service.build_supervisor_graph")
    @patch("backend.services.review_service.checkout_pr")
    @patch("backend.services.review_service.get_settings")
    def test_successful_run(self, mock_settings, mock_checkout, mock_graph, mock_comment, db_session):
        mock_settings.return_value.require.return_value = "fake-token"

        # Mock workspace context manager
        mock_ctx = MagicMock()
        mock_ctx.path = "/tmp/workspace"
        mock_checkout.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_checkout.return_value.__exit__ = MagicMock(return_value=False)

        # Mock graph to return state with findings
        mock_graph.return_value.invoke.return_value = {
            "review_id": 1,
            "agent_notes": {
                "security": ["done"],
                "quality": ["done"],
                "test_gap": ["done"],
                "documentation": ["done"],
            },
            "triaged_findings": {
                "security": [],
            },
            "scanner_statuses": {},
            "quality_result": {},
            "test_gap_result": {},
            "doc_result": {},
            "raw_findings": {},
        }

        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=42,
            head_sha="abc123",
        )

        with patch("backend.services.review_service._get_changed_files", return_value=["app.py"]):
            with patch("backend.services.review_service._get_diff", return_value="diff content"):
                run_review(db_session, review.id)

        db_session.refresh(review)
        assert review.status == "completed"
        assert review.summary is not None
        mock_comment.assert_called_once()

    @patch("backend.services.review_service.checkout_pr")
    @patch("backend.services.review_service.get_settings")
    def test_failed_run_on_checkout_error(self, mock_settings, mock_checkout, db_session):
        mock_settings.return_value.require.return_value = "fake-token"
        mock_checkout.side_effect = RuntimeError("clone failed")

        review = create_review(
            db_session,
            repo_full_name="owner/repo",
            pr_number=42,
            head_sha="abc123",
        )

        run_review(db_session, review.id)

        db_session.refresh(review)
        assert review.status == "failed"
        assert "clone failed" in review.summary

    def test_nonexistent_review(self, db_session):
        # Should not raise, just log
        run_review(db_session, 9999)


class TestReviewStateTransitions:
    @patch("backend.services.review_service._post_pr_comment")
    @patch("backend.services.review_service.build_supervisor_graph")
    @patch("backend.services.review_service.checkout_pr")
    @patch("backend.services.review_service.get_settings")
    def test_pending_to_running_to_completed(self, mock_settings, mock_checkout, mock_graph, mock_comment, db_session):
        mock_settings.return_value.require.return_value = "fake-token"
        mock_ctx = MagicMock()
        mock_ctx.path = "/tmp/ws"
        mock_checkout.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_checkout.return_value.__exit__ = MagicMock(return_value=False)
        mock_graph.return_value.invoke.return_value = {
            "review_id": 1,
            "agent_notes": {},
            "triaged_findings": {},
            "scanner_statuses": {},
            "quality_result": {},
            "test_gap_result": {},
            "doc_result": {},
            "raw_findings": {},
        }

        review = create_review(db_session, repo_full_name="o/r", pr_number=1, head_sha="s")
        assert review.status == "pending"

        with patch("backend.services.review_service._get_changed_files", return_value=[]):
            with patch("backend.services.review_service._get_diff", return_value=""):
                run_review(db_session, review.id)

        db_session.refresh(review)
        assert review.status == "completed"

    @patch("backend.services.review_service.checkout_pr")
    @patch("backend.services.review_service.get_settings")
    def test_pending_to_running_to_failed(self, mock_settings, mock_checkout, db_session):
        mock_settings.return_value.require.return_value = "fake-token"
        mock_checkout.side_effect = Exception("timeout")

        review = create_review(db_session, repo_full_name="o/r", pr_number=1, head_sha="s")
        run_review(db_session, review.id)

        db_session.refresh(review)
        assert review.status == "failed"
