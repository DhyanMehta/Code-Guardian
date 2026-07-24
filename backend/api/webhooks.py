"""GitHub webhook receiver.

Authenticates incoming webhook deliveries using GitHub's ``X-Hub-Signature-256``
HMAC-SHA256 signature, validated against ``GITHUB_WEBHOOK_SECRET``. Invalid or missing
signatures are rejected with 401. Valid ``pull_request`` ``opened``/``synchronize``
events are accepted with 202.

NOTE: In Session 1 the actual review dispatch is a clearly labeled stub. It does not
run any agents or produce findings — it only logs intent. Real dispatch arrives in
Session 5. No fabricated results are ever returned (see RULES.md #5, #6).
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# PR actions that should trigger a review.
_REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened"}


def _verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Return True if ``signature_header`` is a valid HMAC-SHA256 of ``payload``.

    The header format is ``sha256=<hexdigest>``. Comparison is constant-time.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive a GitHub webhook delivery.

    - Rejects requests with a missing/invalid signature (401).
    - Ignores non-``pull_request`` events (202, ignored).
    - For reviewable PR actions, logs intent and returns 202 (dispatch stubbed).
    """
    settings = get_settings()

    # Fail fast and explicitly if the server is misconfigured.
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

    # Parse JSON only after the signature is verified.
    try:
        event = await request.json()
    except Exception as exc:  # noqa: BLE001 - explicit, no silent failure
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
    repo = event.get("repository", {}).get("full_name", "<unknown>")
    pr_number = pr.get("number", "<unknown>")

    # STUB (Session 1): review dispatch is not implemented yet. Do not fabricate
    # results. Real dispatch to the supervisor graph is added in Session 5.
    logger.info(
        "Accepted pull_request '%s' for %s#%s. Review dispatch is stubbed (Session 5).",
        action,
        repo,
        pr_number,
    )
    return {
        "status": "accepted",
        "detail": "Review dispatch not yet implemented (stub).",
        "repository": str(repo),
        "pull_request": str(pr_number),
    }
