"""Opt-in real PostgreSQL checks in an isolated, disposable schema.

Run with CODEGUARDIAN_TEST_POSTGRES=1. No production tables are modified.
"""
import os
import json
import subprocess
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.db.models import Review, ReviewAgentRun, Finding, ReviewProgress
from backend.services.review_service import create_review, _execute_graph_and_persist
from backend import worker

pytestmark = pytest.mark.skipif(os.getenv("CODEGUARDIAN_TEST_POSTGRES") != "1", reason="Enable isolated PostgreSQL integration with CODEGUARDIAN_TEST_POSTGRES=1")


@pytest.fixture
def pg(monkeypatch):
    schema = "cg_test_" + uuid.uuid4().hex
    admin = create_engine(get_settings().database_url, connect_args={"connect_timeout": 5})
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(get_settings().database_url, connect_args={"options": f"-c search_path={schema} -c statement_timeout=10000"})
    factory = sessionmaker(bind=engine)
    cfg = Config("alembic.ini")
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        monkeypatch.setattr("backend.db.database.get_engine", lambda: engine)
        monkeypatch.setattr("backend.db.database.get_sessionmaker", lambda: factory)
        yield engine, factory, cfg
    finally:
        engine.dispose()
        assert schema.startswith("cg_test_") and len(schema) == 40
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_migrations_roundtrip_and_running_constraint(pg):
    engine, factory, cfg = pg
    with factory() as db:
        first = create_review(db, repo_full_name="test/repo", pr_number=1, head_sha="a")
        first.status = "running"
        db.commit()
        second = create_review(db, repo_full_name="test/repo", pr_number=1, head_sha="b")
        second.status = "running"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "f1e2d3c4b5a6")
        command.upgrade(cfg, "head")
        assert conn.execute(text("SELECT count(*) FROM reviews")).scalar() == 2


def test_worker_lock_recovery_and_newest_pending(pg):
    engine, factory, _ = pg
    with factory() as db:
        first = create_review(db, repo_full_name="test/repo", pr_number=1, head_sha="a")
        second = create_review(db, repo_full_name="test/repo", pr_number=1, head_sha="b")
        first_id, second_id = first.id, second.id
    with engine.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:id)"), {"id": worker.LOCK_ID})
        with patch("backend.services.review_service.run_review") as execute:
            worker.run_next()
            execute.assert_not_called()
        lock.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": worker.LOCK_ID})
    with patch("backend.services.review_service.run_review") as execute:
        worker.run_next()
        assert execute.call_args.args[1] == second_id
    with factory() as db:
        assert db.get(Review, first_id).status == "skipped"
        second = db.get(Review, second_id)
        second.status = "running"
        second.attempt = get_settings().max_review_attempts
        db.commit()
    worker.run_next()
    with factory() as db:
        assert db.get(Review, second_id).status == "failed"
        assert db.get(Review, second_id).completed_at


def test_atomic_report_and_delivery_failure(pg, tmp_path):
    _, factory, _ = pg
    with factory() as db:
        review = create_review(db, repo_full_name="test/repo", pr_number=2, head_sha="a")
        state = {"agent_outcomes": {name: "ok" for name in ["security", "quality", "test_gap", "documentation"]}}
        with patch("backend.services.review_service._get_changed_files", return_value=[]), patch("backend.services.review_service._get_diff", return_value=""), patch("backend.services.review_service.build_supervisor_graph") as graph, patch("backend.services.review_service._post_pr_comment", side_effect=RuntimeError("delivery down")):
            graph.return_value.invoke.return_value = state
            _execute_graph_and_persist(db, review, str(tmp_path))
        db.refresh(review)
        assert review.status == "completed" and review.delivery_status == "failed"
        assert "No issues found" in review.report_markdown
        assert db.query(ReviewAgentRun).filter_by(review_id=review.id).count() == 4
        snapshot = review.report_markdown
        with patch("backend.services.review_service._post_pr_comment"):
            worker.run_next()
        db.refresh(review)
        assert review.delivery_status == "posted" and review.report_markdown == snapshot


@pytest.mark.skipif(os.getenv("CODEGUARDIAN_TEST_RUNTIME") != "1", reason="Requires installed scanners")
def test_real_agents_git_rag_and_saved_report(pg, tmp_path, monkeypatch):
    """Real Git/scanners/RAG/graph/DB; LLM responses and GitHub posting are mocked."""
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True, timeout=20).strip()

    git("init")
    git("config", "user.email", "integration@example.invalid")
    git("config", "user.name", "Integration Test")
    source = tmp_path / "app.py"
    source.write_text("# Initial revision\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    source.write_text("def evaluate(value):\n    assert value\n    return eval(value)\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-m", "change")
    head = git("rev-parse", "HEAD")

    class FakeLLM:
        def complete(self, *, system_prompt, user_prompt, **kwargs):
            if "triaged_severity" in system_prompt:
                return json.dumps({"findings": [dict(fingerprint=item["fingerprint"], triaged_severity=item["severity"], explanation="Mock explanation of scanner evidence.", priority=1) for item in json.loads(user_prompt)]})
            if "test_code" in system_prompt:
                return json.dumps({"test_code": "from app import evaluate\n\ndef test_evaluate():\n    assert evaluate('1') == 1\n", "imports": ["app"]})
            if "docstring" in system_prompt:
                return json.dumps({"docstring": "Evaluate an expression.\n\nArgs:\n    value: Expression to evaluate.\n\nReturns:\n    Evaluated value."})
            return '{"findings": []}'

    for module in ["security_agent", "quality_agent", "test_gap_agent", "documentation_agent"]:
        monkeypatch.setattr(f"backend.agents.{module}.LLMClient", FakeLLM)
    from backend.rag.ingest import resolve_active_collection
    _, factory, _ = pg
    with factory() as db:
        review = create_review(db, repo_full_name="test/repo", pr_number=3, head_sha=head, base_sha=base)
        review.standards_version = resolve_active_collection()
        with patch("backend.services.review_service._post_pr_comment") as post:
            _execute_graph_and_persist(db, review, str(tmp_path))
            post.assert_called_once()
        db.refresh(review)
        runs = db.query(ReviewAgentRun).filter_by(review_id=review.id).all()
        assert len(runs) == 4
        assert all(run.outcome == "ok" for run in runs), [(run.agent, run.outcome, run.notes) for run in runs]
        security = next(run for run in runs if run.agent == "security")
        assert "B307" in security.raw_findings
        findings = db.query(Finding).filter_by(review_id=review.id).all()
        assert {"security", "test_gap", "documentation"} <= {finding.agent for finding in findings}
        assert sum(bool(finding.fix_data) for finding in findings) >= 2
        assert review.status == "completed" and review.delivery_status == "posted"
        events = db.query(ReviewProgress).filter_by(review_id=review.id).order_by(ReviewProgress.id).all()
        assert events[-1].stage == 'aggregation' and events[-1].status == 'ok'
        assert len([event for event in events if event.stage == 'agent' and event.status == 'ok']) == 4
        assert "evaluate" in review.report_markdown
        assert "No issues found" not in review.report_markdown
