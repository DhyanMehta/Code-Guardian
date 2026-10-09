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
from backend.db.models import Finding, Review, ReviewAgentRun, Installation, User
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
    base_sha: str | None = None,
    base_ref: str | None = None,
    delivery_id: str | None = None,
    requested_by: int | None = None,
) -> Review:
    """Create a new Review row in 'pending' state."""
    review = Review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        commit_sha=head_sha,
        base_sha=base_sha,
        base_ref=base_ref,
        status="pending",
        is_fork=is_fork,
        installation_id=installation_id,
        delivery_id=delivery_id,
        requested_by=requested_by,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if delivery_id:
            existing = db.query(Review).filter_by(delivery_id=delivery_id).first()
            if existing:
                return existing
        raise
    db.refresh(review)
    return review


def start_review(db: Session, review: Review) -> bool:
    """Transition review to 'running'. Returns False if another is already running.

    The partial unique index on (repo_full_name, pr_number) WHERE status='running'
    guarantees atomicity — IntegrityError means another review is already running.
    """
    review.status = "running"
    review.started_at = _utcnow()
    review.heartbeat_at = _utcnow()
    review.attempt = (review.attempt or 0) + 1
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        review.status = "pending"
        review.summary = "Waiting for the running review of this PR."
        # Retain the queued request for a later worker attempt.
        review.completed_at = None
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

    try:
        _run_review_body(db, review, installation_id=installation_id or review.installation_id)
    except Exception as exc:
        logger.exception("Review %d failed", review_id)
        db.rollback()
        review = db.get(Review, review_id)
        review.status = "failed"
        review.summary = f"Review failed ({type(exc).__name__}). See server logs."
        review.completed_at = _utcnow()
        db.commit()


def _run_review_body(db, review, *, installation_id=None):
    review_id = review.id
    if installation_id:
        inst = db.get(Installation, installation_id)
        if inst and (inst.suspended_at or inst.uninstalled_at):
            raise RuntimeError("Installation is inactive.")
        if not review.standards_version:
            review.standards_version = inst.standards_version if inst else None
    from backend.rag.ingest import resolve_active_collection
    if not review.standards_version:
        review.standards_version = resolve_active_collection()
    db.commit()
    # Manual work is authorized as the requesting user, automated work as the app.
    if review.requested_by:
        from backend.services.authorization import user_token, require_repo
        user = db.get(User, review.requested_by)
        if user is None:
            raise RuntimeError("Requesting user no longer exists.")
        require_repo(user, installation_id, review.repo_full_name, write=True)
        github_token = user_token(user)
    if installation_id is not None:
        from backend.tools.github_app import get_installation_token
        if not review.requested_by:
            github_token = get_installation_token(installation_id)
    elif not review.requested_by:
        settings = get_settings()
        if not settings.legacy_pat_enabled:
            raise RuntimeError("Legacy PAT reviews are disabled.")
        github_token = settings.require("github_token")

    checkout_kwargs: dict[str, Any] = {}
    if review.base_sha:
        checkout_kwargs["base_sha"] = review.base_sha
    if review.base_ref:
        checkout_kwargs["base_ref"] = review.base_ref

    try:
        from backend.services.progress import recorder
        progress = recorder(db.get_bind(), review.id, review.attempt)
        progress("checkout", "started")
        with checkout_pr(
            review.repo_full_name,
            review.commit_sha or "",
            github_token,
            **checkout_kwargs,
        ) as workspace_ctx:
            progress("checkout", "ok")
            logger.info("Review %d waiting for global review lock", review_id)
            with _review_run_lock:
                logger.info("Review %d acquired global review lock", review_id)
                _execute_graph_and_persist(
                    db, review, workspace_ctx.path,
                    installation_id=installation_id,
                )
    except Exception as exc:
        logger.exception("Review %d failed: %s", review_id, exc)
        db.rollback()
        review.status = "failed"
        review.summary = f"Review failed ({type(exc).__name__}). See server logs."
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
    changed_files = _get_changed_files(
        workspace_path,
        base_sha=review.base_sha,
        base_ref=review.base_ref,
    )
    pr_metadata = PRMetadata(
        repo_full_name=review.repo_full_name,
        pr_number=review.pr_number,
        head_sha=review.commit_sha or "",
        changed_files=changed_files,
    )

    diff = _get_diff(
        workspace_path,
        base_sha=review.base_sha,
        base_ref=review.base_ref,
    )

    initial_state: ReviewState = {
        "review_id": review.id,
        "pr": pr_metadata,
        "diff": diff,
        "workspace_path": workspace_path,
        "installation_id": installation_id,
        "standards_version": review.standards_version,
        "raw_findings": {},
        "triaged_findings": {},
        "scanner_statuses": {},
        "agent_notes": {},
        "quality_result": {},
        "test_gap_result": {},
        "doc_result": {},
        "agent_outcomes": {},
    }

    from backend.services.progress import recorder
    progress = recorder(db.get_bind(), review.id, review.attempt or 0)
    # Release the read transaction before parallel progress writers start.
    db.commit()
    progress("analysis", "started")
    graph = build_supervisor_graph(progress=progress)
    final_state = graph.invoke(initial_state)
    progress("aggregation", "started")
    report = aggregate(final_state)
    _persist_findings(db, review, report)
    _persist_agent_runs(db, review, final_state, report)

    comment_md = format_pr_comment(
        report,
        pr_number=review.pr_number,
        commit_sha=review.commit_sha or "",
    )
    review.report_markdown = comment_md
    review.delivery_status = "pending"

    review.status = "completed"
    review.summary = _build_summary(report)
    review.completed_at = _utcnow()
    from backend.db.models import ReviewProgress
    db.add(ReviewProgress(review_id=review.id, attempt=review.attempt or 0,
        stage="aggregation", status="ok"))
    db.commit()
    deliver_report(db, review)


def _persist_findings(db: Session, review: Review, report: AggregatedReport) -> None:
    """Batch-insert Finding rows for all unified findings."""
    db.query(Finding).filter_by(review_id=review.id).delete(synchronize_session=False)
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
            evidence=json.dumps(uf.evidence) if uf.evidence else None,
        )
        db.add(finding)
    db.flush()


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
        outcome = AgentOutcome.coerce(outcomes.get(agent_name, AgentOutcome.UNKNOWN.value))
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
                raw_findings=json.dumps([f.to_prompt_dict() for f in state.get("raw_findings", {}).get(agent_name, [])]),
            )
        )

    db.flush()
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
        return "No issues found." if report.agent_statuses and all(s.succeeded for s in report.agent_statuses) else "No findings in completed checks; review incomplete."
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
        if review.requested_by:
            from sqlalchemy.orm import object_session
            from backend.services.authorization import user_github
            gh = user_github(object_session(review).get(User, review.requested_by))
        elif installation_id is not None:
            from backend.tools.github_app import get_installation_github
            gh = get_installation_github(installation_id)
        else:
            from github import Github
            settings = get_settings()
            token = settings.require("github_token")
            gh = Github(token, timeout=15)

        repo = gh.get_repo(review.repo_full_name)
        pr = repo.get_pull(review.pr_number)
        marker = f"<!-- codeguardian-review:{review.id} -->"
        body = marker + "\n" + comment_md
        existing = next((c for c in pr.get_issue_comments() if (c.body or "") == body), None)
        comment = existing or pr.create_issue_comment(body)
        review.comment_id = str(comment.id)
        logger.info("Posted PR comment to %s#%d", review.repo_full_name, review.pr_number)
    except Exception as exc:
        logger.error(
            "Failed to post PR comment for review %d: %s",
            review.id,
            exc,
        )
        raise


def deliver_report(db: Session, review: Review) -> None:
    review.delivery_attempts = (review.delivery_attempts or 0) + 1
    try:
        _post_pr_comment(review, review.report_markdown or "", installation_id=review.installation_id)
        review.delivery_status = "posted"
        review.delivery_error = None
    except Exception as exc:
        review.delivery_status = "failed"
        review.delivery_error = f"GitHub delivery failed ({type(exc).__name__})."
    db.commit()


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


def _resolve_base_target(
    workspace_path: str,
    base_sha: str | None = None,
    base_ref: str | None = None,
) -> str:
    """Resolve the base commit target to diff HEAD against.

    Prefers base_sha if present and reachable. If base_sha is unreachable but
    base_ref was provided, attempts to find the merge-base between origin/base_ref
    and HEAD. If both are absent or unreachable, fail explicitly.
    """
    if base_sha:
        check = _run_git_diff(workspace_path, ["cat-file", "-t", base_sha], "check base_sha")
        if check and check.strip() == "commit":
            mb = _run_git_diff(workspace_path, ["merge-base", base_sha, "HEAD"], "merge-base")
            if mb and mb.strip():
                return mb.strip()

    if base_ref:
        candidates = [f"origin/{base_ref}", base_ref] if not base_ref.startswith("origin/") else [base_ref]
        for ref_candidate in candidates:
            mb = _run_git_diff(workspace_path, ["merge-base", ref_candidate, "HEAD"], "merge-base")
            if mb and mb.strip():
                return mb.strip()

    logger.warning(
        "Neither base_sha (%s) nor base_ref (%s) has a resolvable merge base",
        base_sha,
        base_ref,
    )
    raise RuntimeError("Cannot determine the PR merge base; review input is unavailable.")


def _get_changed_files(
    workspace_path: str,
    base_sha: str | None = None,
    base_ref: str | None = None,
) -> list[str]:
    """Get list of changed files from the workspace (via git diff --name-only)."""
    base_target = _resolve_base_target(workspace_path, base_sha, base_ref)
    out = _run_git_diff(
        workspace_path, ["diff", "--name-only", "-z", base_target, "HEAD"], "changed files"
    )
    if out is None:
        raise RuntimeError("Cannot read PR changed files.")
    return [f for f in out.split("\0") if f]


def _get_diff(
    workspace_path: str,
    base_sha: str | None = None,
    base_ref: str | None = None,
) -> str:
    """Get unified diff from the workspace."""
    base_target = _resolve_base_target(workspace_path, base_sha, base_ref)
    out = _run_git_diff(workspace_path, ["-c", "core.quotepath=false", "diff", base_target, "HEAD"], "diff")
    if out is None:
        raise RuntimeError("Cannot read PR diff.")
    return out


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
