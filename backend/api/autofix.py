"""Auto-fix gate API endpoints.

POST /reviews/{id}/autofix — create an auto-fix branch (never merges).
POST /reviews/{id}/autofix/approve — record explicit human approval.
POST /reviews/{id}/autofix/reject — reject the auto-fix branch.

Session 9: All three endpoints now require authentication (``get_current_user``)
and verify the caller owns the installation linked to the review (403) **before**
any business logic executes. This prevents unauthenticated callers from
triggering GitHub side effects (branch creation, push, approval recording).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import Review, User
from backend.services.authorization import require_repo
from backend.services.autofix_service import (
    AutofixError,
    approve_autofix,
    create_autofix,
    reject_autofix,
)

router = APIRouter(prefix="/reviews", tags=["autofix"])


class ApproveRequest(BaseModel):
    approved_by: str | None = None  # Compatibility only; identity always comes from the session.


def _get_authorized_review(
    review_id: int,
    current_user: User,
    db: Session,
) -> Review:
    """Load a review and verify the caller owns its installation.

    Raises 404 if the review does not exist, 403 if the caller does not have
    access to the review's installation. This check runs **before** any autofix
    business logic so no GitHub side effects can occur for unauthorized callers.
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

    require_repo(current_user, review.installation_id, review.repo_full_name, write=True)
    return review


@router.post("/{review_id}/autofix", status_code=status.HTTP_201_CREATED)
def create_autofix_endpoint(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create an auto-fix commit on a new branch (never merges)."""
    # Auth + ownership check BEFORE any side effects.
    _get_authorized_review(review_id, current_user, db)

    try:
        result = create_autofix(db, review_id, user=current_user)
    except AutofixError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        if "unavailable for fork" in error_msg:
            raise HTTPException(status_code=422, detail=error_msg) from exc
        if "already exists" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg) from exc
        if "no fixable findings" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg) from exc
        if "All fixes failed" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg) from exc
        raise HTTPException(status_code=400, detail=error_msg) from exc

    return {
        "status": "created",
        "branch": result.branch,
        "applied_fixes": len(result.applied_fixes),
        "skipped_fixes": [
            {"target": f"{s.target_file}:{s.target_function}", "reason": s.reason}
            for s in result.skipped_fixes
        ],
    }


@router.post("/{review_id}/autofix/approve")
def approve_autofix_endpoint(
    review_id: int,
    current_user: User = Depends(get_current_user),
    body: ApproveRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Record explicit human approval for the auto-fix branch."""
    # Auth + ownership check BEFORE any side effects.
    _get_authorized_review(review_id, current_user, db)

    try:
        approve_autofix(db, review_id, approved_by=current_user.github_login, user=current_user)
    except AutofixError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        raise HTTPException(status_code=409, detail=error_msg) from exc

    return {"status": "approved", "review_id": str(review_id)}


@router.post("/{review_id}/autofix/reject")
def reject_autofix_endpoint(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reject an auto-fix branch."""
    # Auth + ownership check BEFORE any side effects.
    _get_authorized_review(review_id, current_user, db)

    try:
        reject_autofix(db, review_id)
    except AutofixError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        raise HTTPException(status_code=409, detail=error_msg) from exc

    return {"status": "rejected", "review_id": str(review_id)}
