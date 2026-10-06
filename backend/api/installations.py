"""Installations API (dashboard-facing).

Session 8: Provides installation and repository discovery for authenticated users:
- ``GET /installations``: lists installations accessible to the logged-in user.
- ``GET /installations/{id}/repos``: lists repositories accessible to the user
  (queried live from GitHub using the user's access token).
- ``GET /installations/{id}/repos/{owner}/{repo}/pulls``: lists open pull requests
  for a given repository.
"""

from __future__ import annotations

import logging
from typing import Any, Literal


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import Installation, User, UserInstallation
from backend.services.review_service import create_review

from backend.services.authorization import require_repo, require_manager, accessible_repos, user_github

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/installations", tags=["installations"])


class UpdateSettingsRequest(BaseModel):
    review_mode: Literal["auto", "manual"]


def _verify_user_installation_access(
    user: User,
    installation_id: int,
    db: Session,
    required_role: str | None = None,
) -> Installation:
    """Verify *user* has access to *installation_id* and the installation is active.

    Raises HTTP 403 if unlinked or role insufficient, HTTP 404 if missing/uninstalled,
    or HTTP 400 if suspended.
    """
    link = next(
        (l for l in user.installation_links if l.installation_id == installation_id),
        None,
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this installation.",
        )

    if required_role is not None and link.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires '{required_role}' role on this installation.",
        )

    inst = db.get(Installation, installation_id)
    if inst is None or inst.uninstalled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Installation {installation_id} not found or uninstalled.",
        )
    if inst.suspended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Installation {installation_id} is currently suspended.",
        )

    if required_role == "admin":
        require_manager(user, inst)

    return inst


@router.get("")
def list_installations(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List installations linked to the current user."""
    results = []
    for link in current_user.installation_links:
        inst = link.installation
        if not inst or inst.uninstalled_at is not None:
            continue
        results.append({
            "id": inst.id,
            "account_login": inst.account_login,
            "account_type": inst.account_type,
            "app_slug": inst.app_slug,
            "target_type": inst.target_type,
            "role": link.role,
            "review_mode": inst.review_mode,
            "suspended": inst.suspended_at is not None,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
        })
    return results


@router.get("/{installation_id}/settings")
def get_installation_settings(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get settings for *installation_id*."""
    inst = _verify_user_installation_access(current_user, installation_id, db)
    return {
        "installation_id": inst.id,
        "review_mode": inst.review_mode,
    }


@router.patch("/{installation_id}/settings")
def update_installation_settings(
    installation_id: int,
    payload: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update settings for *installation_id*. Requires 'admin' role."""
    inst = _verify_user_installation_access(
        current_user, installation_id, db, required_role="admin"
    )
    inst.review_mode = payload.review_mode
    db.commit()
    db.refresh(inst)
    logger.info(
        "User %s updated installation %d review_mode to %s.",
        current_user.github_login,
        installation_id,
        inst.review_mode,
    )
    return {
        "installation_id": inst.id,
        "review_mode": inst.review_mode,
    }


@router.get("/{installation_id}/repos")
def list_installation_repos(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List repositories accessible to *installation_id*.

    Queries GitHub's ``GET /installation/repositories`` API live using
    the installation token, ensuring changes to selected repositories are
    reflected immediately without stale cache issues.
    """
    _verify_user_installation_access(current_user, installation_id, db)

    return [{key: r.get(key) for key in ("id", "name", "full_name", "private", "html_url", "default_branch", "open_issues_count")} for r in accessible_repos(current_user, installation_id)]

@router.get("/{installation_id}/repos/{owner}/{repo}/pulls")
def list_installation_repo_pulls(
    installation_id: int,
    owner: str,
    repo: str,
    state: str = Query("open", pattern="^(open|closed|all)$"),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List pull requests for a repository accessible to *installation_id*."""
    _verify_user_installation_access(current_user, installation_id, db)
    require_repo(current_user, installation_id, f"{owner}/{repo}")

    try:
        gh = user_github(current_user)
        gh_repo = gh.get_repo(f"{owner}/{repo}")
        pulls = gh_repo.get_pulls(state=state)
        items = []
        from itertools import islice
        for p in islice(pulls, (page - 1) * per_page, page * per_page):
            items.append({
                "number": p.number,
                "title": p.title,
                "state": p.state,
                "head_sha": p.head.sha,
                "user": p.user.login if p.user else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "html_url": p.html_url,
            })
        return items
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch pulls for %s/%s on installation %d: %s",
            owner,
            repo,
            installation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch pull requests: {exc}",
        ) from exc


@router.post("/{installation_id}/repos/{owner}/{repo}/pulls/{number}/review", status_code=status.HTTP_202_ACCEPTED)
def trigger_review(
    installation_id: int,
    owner: str,
    repo: str,
    number: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger a CodeGuardian review for a specific pull request."""
    _verify_user_installation_access(current_user, installation_id, db)
    require_repo(current_user, installation_id, f"{owner}/{repo}", write=True)

    try:
        gh = user_github(current_user)
        gh_repo = gh.get_repo(f"{owner}/{repo}")
        pr = gh_repo.get_pull(number)
        head_sha = pr.head.sha
        base_sha = pr.base.sha if pr.base else None
        base_ref = pr.base.ref if pr.base else None
        
        # Detect fork PRs
        head_repo_full_name = pr.head.repo.full_name if pr.head.repo else ""
        is_fork = head_repo_full_name != "" and head_repo_full_name != f"{owner}/{repo}"

    except Exception as exc:
        logger.error(
            "Failed to fetch PR %d for %s/%s on installation %d: %s",
            number,
            owner,
            repo,
            installation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch pull request: {exc}",
        ) from exc

    review = create_review(
        db,
        repo_full_name=f"{owner}/{repo}",
        pr_number=number,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref=base_ref,
        is_fork=is_fork,
        installation_id=installation_id,
        requested_by=current_user.id,
    )

    logger.info(
        "Manual review triggered by user %s for %s/%s#%d (review_id=%d).",
        current_user.github_login,
        owner,
        repo,
        number,
        review.id,
    )

    return {
        "status": "accepted",
        "review_id": review.id,
    }
