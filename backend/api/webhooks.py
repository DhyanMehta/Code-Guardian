"""GitHub webhook receiver.

Authenticates incoming webhook deliveries using GitHub's ``X-Hub-Signature-256``
HMAC-SHA256 signature, validated against ``GITHUB_WEBHOOK_SECRET``. Invalid or missing
signatures are rejected with 401. Valid ``pull_request`` ``opened``/``synchronize``
events create a Review row and dispatch the review as a background task (202).
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.database import get_db
from backend.services.review_service import create_review, run_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened"}


def _verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Return True if ``signature_header`` is a valid HMAC-SHA256 of ``payload``."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, str | int]:
    """Receive a GitHub webhook delivery.

    - Rejects requests with a missing/invalid signature (401).
    - Ignores non-``pull_request`` events (200, ignored).
    - For reviewable PR actions, creates a Review and dispatches in background (202).
    """
    settings = get_settings()

    try:
        secret = settings.require("github_webhook_secret")
    except RuntimeError as exc:
        logger.error("Webhook rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret is not configured on the server.",
        ) from exc

    raw_body = await request.body()

    if not _verify_signature(raw_body, x_hub_signature_256, secret):
        logger.warning("Webhook rejected: invalid or missing signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Hub-Signature-256 signature.",
        )

    try:
        event = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook rejected: body is not valid JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is not valid JSON.",
        ) from exc

    if x_github_event != "pull_request":
        logger.info("Webhook ignored: event type '%s' is not handled.", x_github_event)
        return {"status": "ignored", "reason": f"unhandled event '{x_github_event}'"}

    action = event.get("action")
    if action not in _REVIEWABLE_ACTIONS:
        logger.info("Webhook ignored: pull_request action '%s' not reviewable.", action)
        return {"status": "ignored", "reason": f"unhandled action '{action}'"}

    pr = event.get("pull_request", {})
    repo_full_name = event.get("repository", {}).get("full_name", "")
    pr_number = pr.get("number", 0)
    head_sha = pr.get("head", {}).get("sha", "")

    # Detect fork PRs
    head_repo = pr.get("head", {}).get("repo", {}).get("full_name", "")
    is_fork = head_repo != "" and head_repo != repo_full_name

    review = create_review(
        db,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        is_fork=is_fork,
    )

    from backend.db.database import get_sessionmaker
    session_factory = get_sessionmaker()

    def _background_review(review_id: int) -> None:
        session = session_factory()
        try:
            run_review(session, review_id)
        finally:
            session.close()

    background_tasks.add_task(_background_review, review.id)

    logger.info(
        "Accepted pull_request '%s' for %s#%d (review_id=%d). Dispatching background review.",
        action,
        repo_full_name,
        pr_number,
        review.id,
    )
    return {
        "status": "accepted",
        "review_id": review.id,
        "repository": repo_full_name,
        "pull_request": pr_number,
    }
