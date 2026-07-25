"""Review service — orchestrates a full review run.

Owns the lifecycle: DB row creation → workspace checkout → graph invocation →
finding persistence → PR comment posting → cleanup. Handles timeouts, partial
failures, and the concurrent-review guard (via Postgres partial unique index).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.agents.state import PRMetadata, ReviewState
from backend.agents.supervisor import build_supervisor_graph
from backend.config import get_settings
from backend.db.models import Finding, Review
from backend.services.report_builder import (
    AggregatedReport,
    UnifiedFinding,
    aggregate,
    format_pr_comment,
)
from backend.tools.workspace import checkout_pr

logger = logging.getLogger(__name__)

REVIEW_TIMEOUT_SECONDS = 300
STALE_REVIEW_THRESHOLD_MINUTES = 10
STALE_REVIEW_CHECK_INTERVAL_SECONDS = 120


def create_review(
    db: Session,
    *,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    is_fork: bool = False,
) -> Review:
    """Create a new Review row in 'pending' state."""
    review = Review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        commit_sha=head_sha,
        status="pending",
        is_fork=is_fork,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def start_review(db: Session, review: Review) -> bool:
    """Transition review to 'running'. Returns False if another is already running.

    The partial unique index on (repo_full_name, pr_number) WHERE status='running'
    guarantees atomicity — IntegrityError means another review is already running.
    """
    review.status = "running"
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        review.status = "skipped"
        review.summary = "Another review is already running for this PR."
        db.merge(review)
        db.commit()
        return False


def run_review(db: Session, review_id: int) -> None:
    """Execute a full review run (blocking). Called from a background task."""
    review = db.get(Review, review_id)
    if review is None:
        logger.error("Review %d not found in DB", review_id)
        return

    if not start_review(db, review):
        logger.info(
            "Review %d skipped: another review is running for %s#%d",
            review_id,
            review.repo_full_name,
            review.pr_number,
        )
        return

    settings = get_settings()
    github_token = settings.require("github_token")

    try:
        with checkout_pr(
            review.repo_full_name,
            review.commit_sha or "",
            github_token,
        ) as workspace_ctx:
            _execute_graph_and_persist(db, review, workspace_ctx.path)
    except Exception as exc:
        logger.exception("Review %d failed: %s", review_id, exc)
        review.status = "failed"
        review.summary = f"Review failed: {exc}"
        db.commit()


def _execute_graph_and_persist(
    db: Session,
    review: Review,
    workspace_path: str,
) -> None:
    """Invoke the supervisor graph and persist results."""
    pr_metadata = PRMetadata(
        repo_full_name=review.repo_full_name,
        pr_number=review.pr_number,
        head_sha=review.commit_sha or "",
        changed_files=_get_changed_files(workspace_path),
    )

    diff = _get_diff(workspace_path)

    initial_state: ReviewState = {
        "review_id": review.id,
        "pr": pr_metadata,
        "diff": diff,
        "workspace_path": workspace_path,
        "raw_findings": {},
        "triaged_findings": {},
        "scanner_statuses": {},
        "agent_notes": {},
        "quality_result": {},
        "test_gap_result": {},
        "doc_result": {},
    }

    graph = build_supervisor_graph()
    final_state = graph.invoke(initial_state)

    report = aggregate(final_state)
    _persist_findings(db, review, report)

    comment_md = format_pr_comment(
        report,
        pr_number=review.pr_number,
        commit_sha=review.commit_sha or "",
    )
    _post_pr_comment(review, comment_md)

    review.status = "completed"
    review.summary = _build_summary(report)
    db.commit()


def _persist_findings(db: Session, review: Review, report: AggregatedReport) -> None:
    """Batch-insert Finding rows for all unified findings."""
    for uf in report.findings:
        finding = Finding(
            review_id=review.id,
            agent=uf.agent,
            severity=uf.severity.value,
            title=uf.title,
            detail=uf.detail,
            file_path=uf.file_path,
            line=uf.line,
            fix_data=json.dumps(uf.fix_data) if uf.fix_data else None,
        )
        db.add(finding)
    db.commit()


def _build_summary(report: AggregatedReport) -> str:
    """Short text summary for the Review.summary column."""
    total = len(report.findings)
    if total == 0:
        return "No issues found."
    by_sev: dict[str, int] = {}
    for f in report.findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
    parts = [f"{c} {s}" for s, c in by_sev.items()]
    succeeded = sum(1 for s in report.agent_statuses if s.succeeded)
    return f"{total} findings ({', '.join(parts)}). {succeeded}/{len(report.agent_statuses)} agents succeeded."


def _post_pr_comment(review: Review, comment_md: str) -> None:
    """Post the review comment to the GitHub PR."""
    try:
        from github import Github

        settings = get_settings()
        token = settings.require("github_token")
        gh = Github(token)
        repo = gh.get_repo(review.repo_full_name)
        pr = repo.get_pull(review.pr_number)
        pr.create_issue_comment(comment_md)
        logger.info("Posted PR comment to %s#%d", review.repo_full_name, review.pr_number)
    except Exception as exc:
        logger.error("Failed to post PR comment for review %d: %s", review.id, exc)


def _get_changed_files(workspace_path: str) -> list[str]:
    """Get list of changed files from the workspace (via git diff --name-only)."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
    except Exception as exc:
        logger.warning("Could not get changed files: %s", exc)
    return []


def _get_diff(workspace_path: str) -> str:
    """Get unified diff from the workspace."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as exc:
        logger.warning("Could not get diff: %s", exc)
    return ""


def sweep_stale_reviews(db: Session) -> int:
    """Mark reviews stuck in 'running' past the threshold as 'failed'.

    Returns the number of reviews swept.
    """
    threshold = datetime.now(timezone.utc) - timedelta(minutes=STALE_REVIEW_THRESHOLD_MINUTES)
    stale_reviews = (
        db.query(Review)
        .filter(Review.status == "running", Review.created_at < threshold)
        .all()
    )

    count = 0
    for review in stale_reviews:
        logger.warning(
            "Sweeping stale review %d (%s#%d) — stuck in 'running' since %s",
            review.id,
            review.repo_full_name,
            review.pr_number,
            review.created_at,
        )
        review.status = "failed"
        review.summary = (
            "Review timed out (stuck in running state for "
            f">{STALE_REVIEW_THRESHOLD_MINUTES} minutes). This may indicate the "
            "process crashed mid-review. Re-trigger by pushing a new commit."
        )
        count += 1

    if count:
        db.commit()
    return count


async def periodic_stale_review_sweep(get_db_session) -> None:
    """Async background loop that sweeps stale reviews every N seconds.

    Started on FastAPI lifespan startup. Runs until cancelled.
    """
    logger.info("Stale review sweep started (interval=%ds)", STALE_REVIEW_CHECK_INTERVAL_SECONDS)
    while True:
        try:
            db = get_db_session()
            try:
                swept = sweep_stale_reviews(db)
                if swept:
                    logger.info("Stale review sweep: marked %d reviews as failed", swept)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Stale review sweep error: %s", exc)

        await asyncio.sleep(STALE_REVIEW_CHECK_INTERVAL_SECONDS)
