"""Auto-fix gate API endpoints.

POST /reviews/{id}/autofix — create an auto-fix branch (never merges).
POST /reviews/{id}/autofix/approve — record explicit human approval.
POST /reviews/{id}/autofix/reject — reject the auto-fix branch.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.autofix_service import (
    AutofixError,
    approve_autofix,
    create_autofix,
    reject_autofix,
)

router = APIRouter(prefix="/reviews", tags=["autofix"])


class ApproveRequest(BaseModel):
    approved_by: str


@router.post("/{review_id}/autofix", status_code=status.HTTP_201_CREATED)
def create_autofix_endpoint(
    review_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create an auto-fix commit on a new branch (never merges)."""
    try:
        result = create_autofix(db, review_id)
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
    body: ApproveRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Record explicit human approval for the auto-fix branch."""
    try:
        approve_autofix(db, review_id, approved_by=body.approved_by)
    except AutofixError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        raise HTTPException(status_code=409, detail=error_msg) from exc

    return {"status": "approved", "review_id": str(review_id)}


@router.post("/{review_id}/autofix/reject")
def reject_autofix_endpoint(
    review_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reject an auto-fix branch."""
    try:
        reject_autofix(db, review_id)
    except AutofixError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        raise HTTPException(status_code=409, detail=error_msg) from exc

    return {"status": "rejected", "review_id": str(review_id)}
