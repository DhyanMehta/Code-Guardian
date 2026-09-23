"""Code-health metrics aggregation for the dashboard's trends view.

Aggregation lives here rather than in the client for two reasons: the client would
otherwise have to page the entire reviews table into the browser to compute totals,
and the severity weights below would end up duplicated in JavaScript where they
could drift from the backend's definition.

What the trends actually measure is bounded by what is persisted: per-review finding
counts, their severity and agent breakdown, review outcomes, and auto-fix decisions.
There is deliberately no duration series — ``Review.completed_at`` only exists from
Session 6 onward, so it is null for every earlier row and charting it now would draw
a line through mostly-missing data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.agents.state import AgentOutcome
from backend.agents.supervisor import AGENT_NAMES
from backend.db.models import Review
from backend.tools.results import Severity

logger = logging.getLogger(__name__)

# Weighted severity index. One number per review so a trend line can show whether
# severity is getting worse even when the raw count stays flat. The weights are a
# judgement call, not a measurement, which is why they are returned in the response
# for the UI to display alongside the number.
SEVERITY_WEIGHTS: dict[str, int] = {
    Severity.CRITICAL.value: 10,
    Severity.HIGH.value: 5,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
    Severity.INFO.value: 0,
    Severity.UNKNOWN.value: 0,
}

DEFAULT_LIMIT = 50
MAX_LIMIT = 500

# Outcome strings that represent a genuinely persisted agent run.
_VALID_OUTCOMES = frozenset(outcome.value for outcome in AgentOutcome)

TERMINAL_STATUSES = ("completed", "failed", "skipped")


def _empty_severity_counts() -> dict[str, int]:
    return {s.value: 0 for s in Severity}


def _empty_agent_counts() -> dict[str, int]:
    return {name: 0 for name in AGENT_NAMES}


def compute_trends(
    db: Session,
    *,
    repo: str | None = None,
    limit: int = DEFAULT_LIMIT,
    since: datetime | None = None,
    days: int | None = None,
    installation_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Build the trends payload.

    Args:
        db: active session.
        repo: restrict to one ``owner/name`` repository.
        limit: maximum number of reviews to include (most recent first, then
            returned oldest-first so charts read left to right).
        since: absolute lower bound on ``created_at``.
        days: relative lower bound, applied only when ``since`` is not given.
        installation_ids: restrict to reviews belonging to these installations.
            When provided, only reviews whose ``installation_id`` is in this
            list are included.

    Returns:
        The trends document described in the Session 6 plan.
    """
    limit = max(1, min(limit, MAX_LIMIT))

    if since is None and days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=max(1, days))

    query = db.query(Review)
    if installation_ids is not None:
        query = query.filter(Review.installation_id.in_(installation_ids))
    if repo:
        query = query.filter(Review.repo_full_name == repo)
    if since is not None:
        query = query.filter(Review.created_at >= since)

    # Newest-first for the limit, then reversed so the series is chronological.
    recent = (
        query.order_by(Review.created_at.desc(), Review.id.desc()).limit(limit).all()
    )
    reviews = list(reversed(recent))

    points: list[dict[str, Any]] = []
    totals_severity = _empty_severity_counts()
    totals_agent = _empty_agent_counts()
    status_counts: dict[str, int] = {s: 0 for s in TERMINAL_STATUSES}
    autofix_counts = {"created": 0, "approved": 0, "rejected": 0}
    total_findings = 0

    for review in reviews:
        severity_counts = _empty_severity_counts()
        agent_counts = _empty_agent_counts()
        for finding in review.findings:
            key = Severity.normalize(finding.severity).value
            severity_counts[key] = severity_counts.get(key, 0) + 1
            agent_counts[finding.agent] = agent_counts.get(finding.agent, 0) + 1

        for key, count in severity_counts.items():
            totals_severity[key] = totals_severity.get(key, 0) + count
        for key, count in agent_counts.items():
            totals_agent[key] = totals_agent.get(key, 0) + count

        weighted = sum(
            SEVERITY_WEIGHTS.get(key, 0) * count
            for key, count in severity_counts.items()
        )

        # An agent that could not run makes this point a lower bound, not a real
        # improvement. Surfaced per point so the chart can mark it instead of
        # letting a coverage gap read as progress.
        #
        # Three states, not two. A review that predates agent-run persistence has no
        # rows at all, and "no evidence of a gap" is not "evidence of no gap" — the
        # earlier version of this function inferred a complete run from an empty
        # relationship, which drew six of ten real reviews as verified-complete.
        # A row whose outcome is not a recognized value is likewise treated as
        # unrecorded rather than OK. The column is NOT NULL, so this guards
        # unrecognized strings — an outcome written by a different version of the
        # code, say. ``AgentOutcome.coerce`` falls back to OK, which is the right
        # default for a live agent reporting its own status and the wrong one for
        # reading history back out of the database.
        degraded: list[str] = []
        recorded_agents: set[str] = set()
        for run in review.agent_runs:
            if run.outcome not in _VALID_OUTCOMES:
                continue
            recorded_agents.add(run.agent)
            if AgentOutcome.coerce(run.outcome) is not AgentOutcome.OK:
                degraded.append(run.agent)

        unrecorded = [name for name in AGENT_NAMES if name not in recorded_agents]
        coverage_recorded = not unrecorded

        finding_count = len(review.findings)
        total_findings += finding_count
        if review.status in status_counts:
            status_counts[review.status] += 1

        if review.autofix_status is not None:
            autofix_counts["created"] += 1
        if review.autofix_status == "approved":
            autofix_counts["approved"] += 1
        elif review.autofix_status == "rejected":
            autofix_counts["rejected"] += 1

        points.append({
            "review_id": review.id,
            "repo_full_name": review.repo_full_name,
            "pr_number": review.pr_number,
            "commit_sha": review.commit_sha,
            "status": review.status,
            "is_fork": review.is_fork,
            "created_at": (
                review.created_at.isoformat() if review.created_at else None
            ),
            "total_findings": finding_count,
            "severity_counts": severity_counts,
            "agent_counts": agent_counts,
            "weighted_index": weighted,
            "degraded_agents": degraded,
            "unrecorded_agents": unrecorded,
            # True only when every agent persisted a run outcome.
            "coverage_recorded": coverage_recorded,
            # True only when coverage is both known and complete. False therefore
            # means "do not read this point as a clean baseline", covering both a
            # recorded gap and an unknown one; the two are told apart by
            # coverage_recorded / degraded_agents.
            "coverage_complete": coverage_recorded and not degraded,
        })

    repos = sorted({r.repo_full_name for r in reviews})

    return {
        "range": {
            "since": (
                points[0]["created_at"] if points else (since.isoformat() if since else None)
            ),
            "until": points[-1]["created_at"] if points else None,
            "review_count": len(points),
            "requested_limit": limit,
            "repo": repo,
        },
        "repos": repos,
        "points": points,
        "totals": {
            "reviews": len(points),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "skipped": status_counts.get("skipped", 0),
            "findings": total_findings,
            "severity_counts": totals_severity,
            "agent_counts": totals_agent,
            "autofix": autofix_counts,
            "weights_used": dict(SEVERITY_WEIGHTS),
            # How much of the series is trustworthy as a baseline. The dashboard
            # states these next to the charts rather than quietly averaging over
            # reviews whose coverage is unknown.
            "coverage_recorded_reviews": sum(
                1 for point in points if point["coverage_recorded"]
            ),
            "coverage_complete_reviews": sum(
                1 for point in points if point["coverage_complete"]
            ),
            "reviews_with_coverage_gap": sum(
                1 for point in points if point["degraded_agents"]
            ),
        },
    }
