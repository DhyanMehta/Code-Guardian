"""Code-health metrics API (dashboard-facing).

GET /metrics/trends — per-review series plus range totals for the trends charts.

Session 9: Requires authentication and scopes results to the caller's
installations. Raises 403 if the caller requests an ``installation_id`` they
do not own.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import User
from backend.services.authorization import authorized_repo_names
from backend.services.metrics_service import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    compute_trends,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/trends")
def get_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    repo: str | None = Query(None, description="Restrict to one owner/name repo."),
    installation_id: int | None = Query(None, description="Restrict to one installation."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    days: int | None = Query(None, ge=1, description="Only reviews from the last N days."),
    since: datetime | None = Query(None, description="Absolute lower bound (ISO 8601)."),
) -> dict[str, Any]:
    """Return code-health metrics over time.

    Points are chronological (oldest first) so charts read left to right, which is
    the opposite of ``GET /reviews`` — that list is newest-first for a history view.
    """
    allowed_inst_ids = [
        link.installation_id
        for link in current_user.installation_links
        if link.installation and not link.installation.uninstalled_at
    ]

    if installation_id is not None:
        if installation_id not in allowed_inst_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this installation.",
            )
        # Scope to the single requested installation.
        scope_ids = [installation_id]
    else:
        # Scope to all of the user's installations.
        scope_ids = allowed_inst_ids

    return compute_trends(
        db,
        repo=repo,
        limit=limit,
        since=since,
        days=days,
        installation_ids=scope_ids,
        repo_names=authorized_repo_names(current_user),
    )
