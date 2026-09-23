"""Installations API (dashboard-facing).

Session 8: Provides installation and repository discovery for authenticated users:
- ``GET /installations``: lists installations accessible to the logged-in user.
- ``GET /installations/{id}/repos``: lists repositories accessible to the installation
  (queried live from GitHub using the installation's access token).
- ``GET /installations/{id}/repos/{owner}/{repo}/pulls``: lists open pull requests
  for a given repository.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.db.database import get_db, get_sessionmaker
from backend.db.models import Installation, User, UserInstallation
from backend.services.review_service import create_review, run_review
from backend.tools.github_app import get_installation_github, get_installation_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/installations", tags=["installations"])


def _verify_user_installation_access(
    user: User,
    installation_id: int,
    db: Session,
) -> Installation:
    """Verify *user* has access to *installation_id* and the installation is active.

    Raises HTTP 403 if unlinked, HTTP 404 if missing/uninstalled,
    or HTTP 400 if suspended.
    """
    has_access = any(
        link.installation_id == installation_id
        for link in user.installation_links
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this installation.",
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
            "suspended": inst.suspended_at is not None,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
        })
    return results


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

    try:
        token = get_installation_token(installation_id)
    except Exception as exc:
        logger.error(
            "Failed to acquire token for installation %d: %s",
            installation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to acquire installation token: {exc}",
        ) from exc

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                "https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
    except Exception as exc:
        logger.error("GitHub API error fetching repositories: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API connection error: {exc}",
        ) from exc

    if resp.status_code != 200:
        logger.warning(
            "GitHub /installation/repositories failed with %d: %s",
            resp.status_code,
            resp.text[:200],
        )
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"GitHub API error: {resp.text[:200]}",
        )

    data = resp.json()
    repos = [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": r.get("private", False),
            "html_url": r.get("html_url", ""),
            "default_branch": r.get("default_branch", "main"),
            "open_issues_count": r.get("open_issues_count", 0),
        }
        for r in data.get("repositories", [])
    ]
    return repos


@router.get("/{installation_id}/repos/{owner}/{repo}/pulls")
def list_installation_repo_pulls(
    installation_id: int,
    owner: str,
    repo: str,
    state: str = Query("open", pattern="^(open|closed|all)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List pull requests for a repository accessible to *installation_id*."""
    _verify_user_installation_access(current_user, installation_id, db)

    try:
        gh = get_installation_github(installation_id)
        gh_repo = gh.get_repo(f"{owner}/{repo}")
        pulls = gh_repo.get_pulls(state=state)
        items = []
        for p in pulls:
            items.append({
                "number": p.number,
                "title": p.title,
                "state": p.state,
                "head_sha": p.head.sha,
                "user": p.user.login if p.user else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "html_url": p.html_url,
            })
            if len(items) >= 50:
                break
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

    try:
        gh = get_installation_github(installation_id)
        gh_repo = gh.get_repo(f"{owner}/{repo}")
        pr = gh_repo.get_pull(number)
        head_sha = pr.head.sha
        
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
        is_fork=is_fork,
        installation_id=installation_id,
    )

    session_factory = get_sessionmaker()

    def _background_review(review_id: int, inst_id: int | None) -> None:
        session = session_factory()
        try:
            run_review(session, review_id, installation_id=inst_id)
        finally:
            session.close()

    background_tasks.add_task(_background_review, review.id, installation_id)

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
