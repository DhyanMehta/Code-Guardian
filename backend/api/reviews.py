"""Reviews API (dashboard-facing).

Provides endpoints to list reviews, get review details, and render the PR-comment
markdown for a given review.

Two deliberate design points, both about keeping ordering and status logic in one
place:

* Findings are returned **pre-ranked** by the same ordering the PR comment uses, so
  the dashboard renders the array as received. If the ranking lived in the client
  too, the two would drift.
* Agent status is read from persisted ``review_agent_runs`` rows. It used to be
  reconstructed here from "which agents have findings", which silently dropped any
  agent with zero findings and reported everything else as OK — so a review where
  an agent could not run rendered as a clean run.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from backend.agents.state import AgentOutcome
from backend.agents.supervisor import AGENT_NAMES
from backend.api.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import Finding, Review, ReviewAgentRun, User
from backend.services.report_builder import (
    AgentStatus,
    aggregate_from_records,
    format_pr_comment,
    format_scanner_info,
)
from backend.tools.results import Severity
from backend.services.authorization import authorized_repo_names, require_repo

router = APIRouter(prefix="/reviews", tags=["reviews"])

SEVERITY_KEYS = tuple(s.value for s in Severity)


def _empty_severity_counts() -> dict[str, int]:
    """All severity keys present and zeroed, so clients never key-check."""
    return {key: 0 for key in SEVERITY_KEYS}


def _empty_agent_counts() -> dict[str, int]:
    return {name: 0 for name in AGENT_NAMES}


def _count_by_severity(findings: list[Finding]) -> dict[str, int]:
    counts = _empty_severity_counts()
    for f in findings:
        key = Severity.normalize(f.severity).value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _count_by_agent(findings: list[Finding]) -> dict[str, int]:
    counts = _empty_agent_counts()
    for f in findings:
        counts[f.agent] = counts.get(f.agent, 0) + 1
    return counts


def _serialize_finding(f: Finding, rank: int | None = None) -> dict[str, Any]:
    fix_data = json.loads(f.fix_data) if f.fix_data else None
    payload: dict[str, Any] = {
        "id": f.id,
        "agent": f.agent,
        "severity": Severity.normalize(f.severity).value,
        "title": f.title,
        "detail": f.detail,
        "file_path": f.file_path,
        "line": f.line,
        "fixable": fix_data is not None,
        "fix_data": fix_data,
        "evidence": json.loads(f.evidence) if f.evidence else None,
    }
    if rank is not None:
        payload["rank"] = rank
    return payload


def _agent_runs_payload(review: Review) -> list[dict[str, Any]]:
    """Persisted per-agent outcomes, ordered by the canonical agent order.

    Reviews created before Session 6 have no agent-run rows. Rather than inventing
    an OK status for them, ``outcome`` is reported as ``null`` with
    ``recorded=False`` so the dashboard can say "not recorded" instead of "fine".
    """
    by_agent = {r.agent: r for r in review.agent_runs}
    payload = []
    for name in AGENT_NAMES:
        run = by_agent.get(name)
        if run is None:
            payload.append({
                "agent": name,
                "outcome": None,
                "recorded": False,
                "finding_count": sum(
                    1 for f in review.findings if f.agent == name
                ),
                "failure_reason": None,
                "notes": [],
            })
            continue
        scanner_statuses = (
            json.loads(run.scanner_statuses) if run.scanner_statuses else []
        )
        payload.append({
            "agent": name,
            "outcome": AgentOutcome.coerce(run.outcome).value,
            "recorded": AgentOutcome.coerce(run.outcome) is not AgentOutcome.UNKNOWN,
            "finding_count": run.finding_count,
            "failure_reason": run.failure_reason,
            "notes": json.loads(run.notes) if run.notes else [],
            "scanner_statuses": scanner_statuses,
            "scanner_info": format_scanner_info(scanner_statuses),
            "raw_findings": json.loads(run.raw_findings) if run.raw_findings else [],
        })
    return payload


def _autofix_payload(review: Review) -> dict[str, Any]:
    return {
        "status": review.autofix_status,
        "branch": review.autofix_branch,
        "approved_by": review.autofix_approved_by,
        "approved_at": (
            review.autofix_approved_at.isoformat()
            if review.autofix_approved_at
            else None
        ),
        "applied_count": review.autofix_applied_count,
        "commit_sha": review.autofix_commit_sha,
        "error": review.autofix_error,
        "skipped_fixes": (
            json.loads(review.autofix_skipped_fixes)
            if review.autofix_skipped_fixes
            else []
        ),
    }


@router.get("")
def list_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repo: str | None = None,
    installation_id: int | None = None,
) -> dict[str, Any]:
    """List past reviews, newest first, with the counts the dashboard needs.

    Returns an envelope rather than a bare array so ``total`` is available for
    pagination without a second request.
    """
    allowed_inst_ids = [
        link.installation_id 
        for link in current_user.installation_links 
        if link.installation and not link.installation.uninstalled_at
    ]

    query = db.query(Review).filter(Review.installation_id.in_(allowed_inst_ids))
    query = query.filter(Review.repo_full_name.in_(authorized_repo_names(current_user)))
    if repo:
        query = query.filter(Review.repo_full_name == repo)
    if installation_id is not None:
        if installation_id not in allowed_inst_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this installation.",
            )
        query = query.filter(Review.installation_id == installation_id)

    total = query.count()
    reviews = (
        query.options(selectinload(Review.findings), selectinload(Review.agent_runs)).order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for r in reviews:
        items.append({
            "id": r.id,
            "installation_id": r.installation_id,
            "repo_full_name": r.repo_full_name,
            "pr_number": r.pr_number,
            "commit_sha": r.commit_sha,
            "status": r.status,
            "delivery_status": r.delivery_status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "summary": r.summary,
            "is_fork": r.is_fork,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "finding_count": len(r.findings),
            "severity_counts": _count_by_severity(r.findings),
            "agent_counts": _count_by_agent(r.findings),
            "fixable_count": sum(1 for f in r.findings if f.fix_data),
            "autofix_status": r.autofix_status,
            "autofix_branch": r.autofix_branch,
            "degraded_agents": [
                run.agent
                for run in r.agent_runs
                if AgentOutcome.coerce(run.outcome) is not AgentOutcome.OK
            ],
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{review_id}")
def get_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one review's full detail.

    ``findings`` is flat and pre-ranked using the report builder's ordering (the
    same one the PR comment uses), with a 1-based ``rank`` so a finding's number in
    the dashboard matches its number in the posted comment.
    ``findings_by_agent`` is retained for the per-agent view.
    """
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found.",
        )

    allowed_inst_ids = [
        link.installation_id 
        for link in current_user.installation_links 
        if link.installation and not link.installation.uninstalled_at
    ]
    if review.installation_id not in allowed_inst_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this review.",
        )

    require_repo(current_user, review.installation_id, review.repo_full_name)
    ranked = _rank_findings(review.findings)

    findings_by_agent: dict[str, list[dict]] = {}
    for f, rank in ranked:
        findings_by_agent.setdefault(f.agent, []).append(_serialize_finding(f, rank))

    return {
        "id": review.id,
        "installation_id": review.installation_id,
        "repo_full_name": review.repo_full_name,
        "pr_number": review.pr_number,
        "commit_sha": review.commit_sha,
        "status": review.status,
        "delivery_status": review.delivery_status,
        "delivery_error": review.delivery_error,
        "comment_id": review.comment_id,
        "standards_version": review.standards_version,
        "started_at": review.started_at.isoformat() if review.started_at else None,
        "summary": review.summary,
        "is_fork": review.is_fork,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "completed_at": (
            review.completed_at.isoformat() if review.completed_at else None
        ),
        # Retained at the top level for backwards compatibility with Session 5
        # consumers; the grouped structure below is the canonical detail payload.
        "autofix_status": review.autofix_status,
        "autofix_branch": review.autofix_branch,
        "autofix_approved_by": review.autofix_approved_by,
        "autofix_approved_at": (
            review.autofix_approved_at.isoformat()
            if review.autofix_approved_at
            else None
        ),
        "autofix": _autofix_payload(review),
        "findings": [_serialize_finding(f, rank) for f, rank in ranked],
        "findings_by_agent": findings_by_agent,
        "finding_count": len(review.findings),
        "severity_counts": _count_by_severity(review.findings),
        "agent_counts": _count_by_agent(review.findings),
        "fixable_count": sum(1 for f in review.findings if f.fix_data),
        "agent_runs": _agent_runs_payload(review),
    }


def _rank_findings(findings: list[Finding]) -> list[tuple[Finding, int]]:
    """Order findings exactly as the PR comment does, and number them 1..n.

    Ordering is delegated to ``report_builder`` so severity ranking has a single
    owner. This function only pairs the result back to the ORM rows.
    """
    report = aggregate_from_records(findings)
    # Findings are uniquely identified by their DB id, carried through aggregation.
    by_id = {f.id: f for f in findings}
    ranked: list[tuple[Finding, int]] = []
    for index, unified in enumerate(report.findings, start=1):
        record = by_id.get(unified.record_id)
        if record is not None:
            ranked.append((record, index))
    return ranked


@router.get("/{review_id}/report")
def get_review_report(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the rendered PR-comment markdown for a review.

    The return annotation doubles as the FastAPI response model, so it must admit
    the integer ``review_id``; annotating it ``dict[str, str]`` made every call to
    this endpoint fail response validation with a 500.

    Agent statuses come from persisted ``review_agent_runs`` rows so this output
    matches the comment that was actually posted to GitHub.
    """
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found.",
        )

    allowed_inst_ids = [
        link.installation_id
        for link in current_user.installation_links
        if link.installation and not link.installation.uninstalled_at
    ]
    if review.installation_id not in allowed_inst_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this review.",
        )

    if review.status not in ("completed", "failed"):
        # "still in" is only true while the review can still progress. A skipped
        # review is terminal and will never produce a report, and telling a caller
        # to wait for one that is never coming is worse than saying no.
        if review.status == "skipped":
            detail = (
                f"Review {review_id} was skipped, so no report was generated. "
                "A skipped review never ran the agents."
            )
        else:
            detail = f"Review {review_id} is still in '{review.status}' state."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    require_repo(current_user, review.installation_id, review.repo_full_name)
    if review.report_markdown:
        return {"review_id": review.id, "markdown": review.report_markdown}
    report = aggregate_from_records(review.findings)
    report.agent_statuses = _agent_statuses_from_records(review)

    md = format_pr_comment(
        report,
        pr_number=review.pr_number,
        commit_sha=review.commit_sha or "",
    )

    return {"review_id": review_id, "markdown": md}


def _agent_statuses_from_records(review: Review) -> list[AgentStatus]:
    """Build report-builder statuses from persisted agent-run rows."""
    by_agent = {r.agent: r for r in review.agent_runs}
    statuses: list[AgentStatus] = []
    for name in AGENT_NAMES:
        run = by_agent.get(name)
        if run is None:
            # No record (pre-Session-6 review). Report the finding count with an OK
            # outcome, which is the most this row can honestly support.
            statuses.append(
                AgentStatus(
                    name=name,
                    outcome=AgentOutcome.UNKNOWN,
                    finding_count=sum(
                        1 for f in review.findings if f.agent == name
                    ),
                )
            )
            continue
        statuses.append(
            AgentStatus(
                name=name,
                outcome=AgentOutcome.coerce(run.outcome),
                finding_count=run.finding_count,
                error_message=run.failure_reason,
                scanner_info=format_scanner_info(
                    json.loads(run.scanner_statuses) if run.scanner_statuses else []
                ),
            )
        )
    return statuses
