"""Reviews API (dashboard-facing).

Stub for Session 1. These endpoints will list and return persisted review results
once the supervisor and persistence layers exist (Sessions 5-6). They intentionally
return HTTP 501 rather than fabricating data (see RULES.md #6).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def list_reviews() -> None:
    """List past reviews. Not implemented until persistence lands (Session 5/6)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Review listing is not implemented yet (planned for Session 5/6).",
    )


@router.get("/{review_id}")
def get_review(review_id: int) -> None:
    """Return one review's detail. Not implemented yet (Session 5/6)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Review detail is not implemented yet (planned for Session 5/6).",
    )
