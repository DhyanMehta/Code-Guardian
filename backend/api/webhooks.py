"""GitHub webhook receiver.

Authenticates incoming webhook deliveries using GitHub's ``X-Hub-Signature-256``
HMAC-SHA256 signature, validated against ``GITHUB_WEBHOOK_SECRET``. Invalid or missing
signatures are rejected with 401.

Session 8 extends the handler to branch on event type:
- ``installation`` events create/update/deactivate Installation rows.
- ``pull_request`` events resolve the installation from the payload, create a
  scoped pending Review row for the durable worker (202).
- All other event types are accepted (200) but ignored.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.database import get_db
from backend.db.models import Installation, User
from backend.services.review_service import create_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened"}
_INSTALLATION_ACTIONS = {"created", "deleted", "suspend", "unsuspend", "new_permissions_accepted"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Return True if ``signature_header`` is a valid HMAC-SHA256 of ``payload``."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


# --------------------------------------------------------------------------- #
# Installation event handling (Session 8)
# --------------------------------------------------------------------------- #


def _handle_installation_event(
    event: dict, db: Session
) -> dict[str, str | int]:
    """Process an ``installation`` webhook event.

    Actions: ``created``, ``deleted``, ``suspend``, ``unsuspend``,
    ``new_permissions_accepted``.  Rows are soft-deleted (``uninstalled_at``)
    rather than hard-deleted because reviews hold a FK reference.
    """
    action = event.get("action", "")
    inst = event.get("installation") or {}
    installation_id = inst.get("id")
    account = inst.get("account") or {}

    if not installation_id:
        logger.warning("Installation event has no installation.id; ignoring.")
        return {"status": "ignored", "reason": "missing installation.id"}

    if action == "created":
        db_inst = Installation(
            id=installation_id,
            account_login=account.get("login", ""),
            account_type=account.get("type", "User"),
            app_slug=inst.get("app_slug", ""),
            target_type=inst.get("repository_selection", "selected"),
            permissions=json.dumps(inst.get("permissions", {})),
        )
        db.merge(db_inst)
        db.commit()
        logger.info(
            "Installation %d created for %s (%s).",
            installation_id,
            account.get("login", "?"),
            account.get("type", "?"),
        )

    elif action == "deleted":
        row = db.get(Installation, installation_id)
        if row:
            row.uninstalled_at = _utcnow()
            db.commit()
            logger.info("Installation %d soft-deleted.", installation_id)
            # Evict cached auth so stale tokens aren't used.
            from backend.tools.github_app import invalidate_installation
            invalidate_installation(installation_id)
        else:
            logger.info(
                "Installation %d deleted but not in DB; ignoring.",
                installation_id,
            )

    elif action == "suspend":
        row = db.get(Installation, installation_id)
        if row:
            row.suspended_at = _utcnow()
            db.commit()
            from backend.tools.github_app import invalidate_installation
            invalidate_installation(installation_id)
            logger.info("Installation %d suspended.", installation_id)
        else:
            logger.info(
                "Installation %d suspend event but not in DB; ignoring.",
                installation_id,
            )

    elif action == "unsuspend":
        row = db.get(Installation, installation_id)
        if row:
            row.suspended_at = None
            db.commit()
            logger.info("Installation %d unsuspended.", installation_id)
        else:
            logger.info(
                "Installation %d unsuspend event but not in DB; ignoring.",
                installation_id,
            )

    elif action == "new_permissions_accepted":
        row = db.get(Installation, installation_id)
        if row:
            row.permissions = json.dumps(inst.get("permissions", {}))
            row.updated_at = _utcnow()
            db.commit()
            logger.info("Installation %d permissions updated.", installation_id)

    else:
        logger.info(
            "Installation event action '%s' not handled; ignoring.",
            action,
        )
        return {"status": "ignored", "reason": f"unhandled installation action '{action}'"}

    return {
        "status": "processed",
        "event": "installation",
        "action": action,
        "installation_id": installation_id,
    }


# --------------------------------------------------------------------------- #
# Installation resolution for pull_request events
# --------------------------------------------------------------------------- #


def _resolve_installation(
    event: dict, db: Session
) -> Installation | None:
    """Extract and validate the Installation from a webhook payload.

    If the installation is not yet in the DB, auto-creates it (the ``created``
    webhook may have been missed, e.g. the app was installed before this code
    was deployed).

    Returns ``None`` if the payload has no installation block (legacy PAT setup)
    or if the installation is suspended/uninstalled.
    """
    inst_data = event.get("installation")
    if not inst_data or not inst_data.get("id"):
        return None

    installation_id = inst_data["id"]
    row = db.get(Installation, installation_id)

    if row is None:
        # Auto-create: the app was installed but we missed the installation event.
        account = inst_data.get("account", {})
        row = Installation(
            id=installation_id,
            account_login=account.get("login", ""),
            account_type=account.get("type", "User"),
        )
        db.add(row)
        db.commit()
        logger.info(
            "Auto-created installation %d for %s (missed 'created' event).",
            installation_id,
            account.get("login", "?"),
        )

    if row.uninstalled_at:
        logger.warning(
            "Ignoring PR event for uninstalled installation %d.",
            installation_id,
        )
        return None

    if row.suspended_at:
        logger.warning(
            "Ignoring PR event for suspended installation %d.",
            installation_id,
        )
        return None

    return row


# --------------------------------------------------------------------------- #
# Main webhook endpoint
# --------------------------------------------------------------------------- #


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> dict[str, str | int]:
    """Receive a GitHub webhook delivery.

    - Rejects requests with a missing/invalid signature (401).
    - Handles ``installation`` events (create/delete/suspend/unsuspend).
    - For reviewable PR actions, resolves the installation, creates a Review,
      and dispatches in background (202).
    - All other events are accepted (200) but ignored.
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

    if not isinstance(event, dict):
        raise HTTPException(400, "Webhook must be an object.")
    def object_field(parent, key):
        value = parent.get(key)
        if value is not None and not isinstance(value, dict):
            raise HTTPException(400, f"Invalid webhook object: {key}.")
        return value or {}
    installation = object_field(event, "installation")
    if installation and (type(installation.get("id")) is not int or installation["id"] <= 0):
        raise HTTPException(400, "Invalid installation ID.")
    object_field(installation, "account")
    object_field(event, "sender")
    repository = object_field(event, "repository")
    pull_request = object_field(event, "pull_request")
    head = object_field(pull_request, "head")
    base = object_field(pull_request, "base")
    object_field(head, "repo")
    if x_github_event == "github_app_authorization" and event.get("action") == "revoked":
        sender_id = (event.get("sender") or {}).get("id")
        user = db.query(User).filter_by(github_user_id=sender_id).first() if sender_id else None
        if user:
            user.access_token_enc = None
            user.refresh_token_enc = None
            user.session_version += 1
            user.installation_links.clear()
            db.commit()
        return {"status": "processed"}
    # ----- Branch on event type -----

    if x_github_event == "installation":
        return _handle_installation_event(event, db)

    if x_github_event == "installation_repositories":
        from backend.tools.github_app import invalidate_installation
        if installation:
            invalidate_installation(installation["id"])
        return {"status": "processed", "reason": "repository permissions are checked live"}

    if x_github_event != "pull_request":
        logger.info("Webhook ignored: event type '%s' is not handled.", x_github_event)
        return {"status": "ignored", "reason": f"unhandled event '{x_github_event}'"}

    # ----- pull_request event -----

    action = event.get("action")
    if action not in _REVIEWABLE_ACTIONS:
        logger.info("Webhook ignored: pull_request action '%s' not reviewable.", action)
        return {"status": "ignored", "reason": f"unhandled action '{action}'"}

    pr = event.get("pull_request") or {}
    repo_full_name = repository.get("full_name", "")
    pr_number = pr.get("number", 0)
    head_sha = head.get("sha", "")
    base_sha = base.get("sha", "")
    base_ref = base.get("ref", "")

    # Detect fork PRs
    head_repo = (head.get("repo") or {}).get("full_name", "")
    is_fork = head_repo != "" and head_repo != repo_full_name
    if not isinstance(repo_full_name, str) or len(repo_full_name.split("/")) != 2 or not all(repo_full_name.split("/")) or type(pr_number) is not int or pr_number <= 0 or not isinstance(head_sha, str) or not head_sha or head_sha.startswith("-"):
        raise HTTPException(400, "Repository, PR number and head SHA are required.")
    if not isinstance(base_sha, str) or not isinstance(base_ref, str):
        raise HTTPException(400, "Invalid PR base information.")

    # Resolve the installation from the payload (Session 8).
    inst = _resolve_installation(event, db)

    if inst is None and event.get("installation"):
        # The payload had an installation block but it resolved to None
        # (suspended or uninstalled). Reject without creating a review.
        return {
            "status": "rejected",
            "reason": "installation is suspended or removed",
        }

    if inst is not None and inst.review_mode == "manual":
        logger.info(
            "Webhook skipped review for PR #%d on %s: installation %d review_mode is 'manual'.",
            pr_number,
            repo_full_name,
            inst.id,
        )
        return {
            "status": "ignored",
            "reason": "installation review_mode is manual",
            "installation_id": inst.id,
        }

    installation_id = inst.id if inst else None
    if installation_id is None and not settings.legacy_pat_enabled:
        raise HTTPException(400, "GitHub App installation is required.")

    review = create_review(
        db,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref=base_ref,
        is_fork=is_fork,
        installation_id=installation_id,
        delivery_id=x_github_delivery,
    )

    logger.info(
        "Accepted pull_request '%s' for %s#%d (review_id=%d, installation_id=%s). "
        "Queued durable review.",
        action,
        repo_full_name,
        pr_number,
        review.id,
        installation_id,
    )
    return {
        "status": "accepted",
        "review_id": review.id,
        "repository": repo_full_name,
        "pull_request": pr_number,
    }
