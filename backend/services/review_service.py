"""Review service — orchestrates a full review run.

Owns the lifecycle: DB row creation → workspace checkout → graph invocation →
finding persistence → PR comment posting → cleanup. Handles timeouts, partial
failures, and the concurrent-review guard (via Postgres partial unique index).

Session 6 additions: per-agent run outcomes and the terminal-state timestamp are
persisted, so the dashboard can report honest agent status after the fact rather
than re-deriving it (badly) from which agents happen to have findings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.agents.state import AgentOutcome, PRMetadata, ReviewState
from backend.agents.supervisor import AGENT_NAMES, build_supervisor_graph
from backend.config import get_settings
from backend.db.models import Finding, Review, ReviewAgentRun
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

# Global lock to serialize AI token quota usage.
_review_run_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_review(
    db: Session,
    *,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    is_fork: bool = False,
    installation_id: int | None = None,
) -> Review:
    """Create a new Review row in 'pending' state."""
    review = Review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        commit_sha=head_sha,
        status="pending",
        is_fork=is_fork,
        installation_id=installation_id,
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
        # 'skipped' is terminal: this row will never run.
        review.completed_at = _utcnow()
        db.merge(review)
        db.commit()
        return False


def run_review(db: Session, review_id: int, *, installation_id: int | None = None) -> None:
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

    # Resolve the GitHub token: prefer installation token, fall back to legacy PAT.
    if installation_id is not None:
        from backend.tools.github_app import get_installation_token
        github_token = get_installation_token(installation_id)
    else:
        settings = get_settings()
        github_token = settings.require("github_token")

    try:
        with checkout_pr(
            review.repo_full_name,
            review.commit_sha or "",
            github_token,
        ) as workspace_ctx:
            logger.info("Review %d waiting for global review lock", review_id)
            with _review_run_lock:
                logger.info("Review %d acquired global review lock", review_id)
                _execute_graph_and_persist(
                    db, review, workspace_ctx.path,
                    installation_id=installation_id,
                )
    except Exception as exc:
        logger.exception("Review %d failed: %s", review_id, exc)
        review.status = "failed"
        review.summary = f"Review failed: {exc}"
        review.completed_at = _utcnow()
        db.commit()


def _execute_graph_and_persist(
    db: Session,
    review: Review,
    workspace_path: str,
    *,
    installation_id: int | None = None,
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
        "agent_outcomes": {},
    }

    graph = build_supervisor_graph()
    final_state = graph.invoke(initial_state)

    report = aggregate(final_state)
    _persist_findings(db, review, report)
    _persist_agent_runs(db, review, final_state, report)

    comment_md = format_pr_comment(
        report,
        pr_number=review.pr_number,
        commit_sha=review.commit_sha or "",
    )
    _post_pr_comment(review, comment_md, installation_id=installation_id)

    review.status = "completed"
    review.summary = _build_summary(report)
    review.completed_at = _utcnow()
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


def _serialize_scanner_statuses(statuses: object) -> str | None:
    """JSON-encode per-scanner outcomes, tolerating dataclasses or plain dicts."""
    from dataclasses import asdict, is_dataclass

    if not statuses:
        return None
    encoded = []
    for status in statuses:  # type: ignore[union-attr]
        encoded.append(asdict(status) if is_dataclass(status) else dict(status))
    return json.dumps(encoded)


def _persist_agent_runs(
    db: Session,
    review: Review,
    state: ReviewState,
    report: AggregatedReport,
) -> None:
    """Persist one row per specialist agent describing how its run went.

    The outcome comes from the graph's structured ``agent_outcomes`` slice, which is
    the single source of truth for whether an agent ran (never inferred from note
    text or from a finding count, both of which are ambiguous).
    """
    outcomes = state.get("agent_outcomes", {}) or {}
    notes_by_agent = state.get("agent_notes", {}) or {}
    scanners_by_agent = state.get("scanner_statuses", {}) or {}
    status_by_agent = {s.name: s for s in report.agent_statuses}

    # Idempotent: a re-run of the same Review row replaces its previous records.
    # The delete must be flushed before the new inserts, otherwise both land in one
    # flush and the (review_id, agent) unique constraint rejects the second write.
    db.query(ReviewAgentRun).filter(ReviewAgentRun.review_id == review.id).delete(
        synchronize_session=False
    )
    db.flush()

    for agent_name in AGENT_NAMES:
        outcome = AgentOutcome.coerce(outcomes.get(agent_name, AgentOutcome.OK.value))
        status = status_by_agent.get(agent_name)
        notes = notes_by_agent.get(agent_name) or []
        db.add(
            ReviewAgentRun(
                review_id=review.id,
                agent=agent_name,
                outcome=outcome.value,
                finding_count=(
                    status.finding_count
                    if status is not None
                    else sum(1 for f in report.findings if f.agent == agent_name)
                ),
                failure_reason=(
                    status.error_message
                    if status is not None and outcome is not AgentOutcome.OK
                    else None
                ),
                notes=json.dumps(list(notes)) if notes else None,
                scanner_statuses=_serialize_scanner_statuses(
                    scanners_by_agent.get(agent_name)
                ),
            )
        )

    db.commit()
    logger.info(
        "Persisted %d agent run record(s) for review %d: %s",
        len(AGENT_NAMES),
        review.id,
        {
            name: AgentOutcome.coerce(
                outcomes.get(name, AgentOutcome.OK.value)
            ).value
            for name in AGENT_NAMES
        },
    )


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


def _post_pr_comment(
    review: Review,
    comment_md: str,
    *,
    installation_id: int | None = None,
) -> None:
    """Post the review comment to the GitHub PR."""
    try:
        if installation_id is not None:
            from backend.tools.github_app import get_installation_github
            gh = get_installation_github(installation_id)
        else:
            from github import Github
            settings = get_settings()
            token = settings.require("github_token")
            gh = Github(token)

        repo = gh.get_repo(review.repo_full_name)
        pr = repo.get_pull(review.pr_number)
        pr.create_issue_comment(comment_md)
        logger.info("Posted PR comment to %s#%d", review.repo_full_name, review.pr_number)
    except Exception as exc:
        logger.error(
            "Failed to post PR comment for review %d: %s",
            review.id,
            exc,
        )


def _run_git_diff(workspace_path: str, args: list[str], what: str) -> str | None:
    """Run a git command in the workspace, returning stdout or ``None`` on failure.

    A non-zero exit is logged at error level rather than swallowed: an empty diff
    starves the Quality / Test-Gap / Documentation agents, so it must never look
    like a legitimately empty result (see ``RULES.md`` #9).
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced below, never silent
        logger.error("Could not get %s (git %s): %s", what, " ".join(args), exc)
        return None

    if result.returncode != 0:
        logger.error(
            "Could not get %s: `git %s` exited %d: %s",
            what,
            " ".join(args),
            result.returncode,
            (result.stderr or "").strip()[:300],
        )
        return None

    return result.stdout


def _get_changed_files(workspace_path: str) -> list[str]:
    """Get list of changed files from the workspace (via git diff --name-only)."""
    out = _run_git_diff(
        workspace_path, ["diff", "--name-only", "HEAD~1"], "changed files"
    )
    if out is None:
        return []
    return [f for f in out.strip().split("\n") if f]


def _get_diff(workspace_path: str) -> str:
    """Get unified diff from the workspace."""
    out = _run_git_diff(workspace_path, ["diff", "HEAD~1"], "diff")
    return out or ""


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
        review.completed_at = _utcnow()
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
