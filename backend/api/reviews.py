"""Reviews API (dashboard-facing).

Provides endpoints to list reviews, get review details, and render the PR-comment
markdown for a given review.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Finding, Review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def list_reviews(
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List past reviews (repo, PR #, status, summary, timestamp)."""
    reviews = (
        db.query(Review)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "repo_full_name": r.repo_full_name,
            "pr_number": r.pr_number,
            "commit_sha": r.commit_sha,
            "status": r.status,
            "summary": r.summary,
            "is_fork": r.is_fork,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finding_count": len(r.findings),
        }
        for r in reviews
    ]


@router.get("/{review_id}")
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one review's full detail including per-agent findings."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found.",
        )

    findings_by_agent: dict[str, list[dict]] = {}
    for f in review.findings:
        findings_by_agent.setdefault(f.agent, []).append({
            "id": f.id,
            "severity": f.severity,
            "title": f.title,
            "detail": f.detail,
            "file_path": f.file_path,
            "line": f.line,
            "fix_data": json.loads(f.fix_data) if f.fix_data else None,
        })

    return {
        "id": review.id,
        "repo_full_name": review.repo_full_name,
        "pr_number": review.pr_number,
        "commit_sha": review.commit_sha,
        "status": review.status,
        "summary": review.summary,
        "is_fork": review.is_fork,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "autofix_status": review.autofix_status,
        "autofix_branch": review.autofix_branch,
        "autofix_approved_by": review.autofix_approved_by,
        "autofix_approved_at": (
            review.autofix_approved_at.isoformat() if review.autofix_approved_at else None
        ),
        "findings_by_agent": findings_by_agent,
        "finding_count": len(review.findings),
    }


@router.get("/{review_id}/report")
def get_review_report(
    review_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Return the rendered PR-comment markdown for a review."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found.",
        )

    if review.status not in ("completed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Review {review_id} is still in '{review.status}' state.",
        )

    from backend.services.report_builder import (
        AggregatedReport,
        AgentStatus,
        UnifiedFinding,
        format_pr_comment,
    )
    from backend.tools.results import Severity

    findings = []
    for f in review.findings:
        fix_data = json.loads(f.fix_data) if f.fix_data else None
        findings.append(UnifiedFinding(
            agent=f.agent,
            severity=Severity.normalize(f.severity),
            title=f.title,
            detail=f.detail or "",
            file_path=f.file_path,
            line=f.line,
            fixable=fix_data is not None,
            fix_data=fix_data,
        ))

    agents_seen = {f.agent for f in review.findings}
    statuses = [
        AgentStatus(name=a, finding_count=sum(1 for f in review.findings if f.agent == a))
        for a in sorted(agents_seen)
    ]

    report = AggregatedReport(findings=findings, agent_statuses=statuses)
    md = format_pr_comment(report, pr_number=review.pr_number, commit_sha=review.commit_sha or "")

    return {"review_id": review_id, "markdown": md}
