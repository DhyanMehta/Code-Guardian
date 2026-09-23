"""GitHub OAuth and dashboard session authentication.

Session 8: Provides OAuth login via the GitHub App ("Sign in with GitHub"):
- ``GET /auth/github/login``: returns the GitHub authorization URL and anti-CSRF state.
- ``POST /auth/github/callback``: exchanges the OAuth code, queries user identity
  and accessible installations live, upserts User and UserInstallation records,
  and issues a 30-day HS256 session JWT.
- ``GET /auth/me``: returns the currently authenticated user profile and installations.
- ``POST /auth/logout``: client-side session discard acknowledgement.

OAuth user tokens are used ONLY during the login callback to sync identity and
installations.  They are NOT stored in the database (access_token_enc dropped per
approved architecture).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.database import get_db
from backend.db.models import Installation, User, UserInstallation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_JWT_EXPIRY_DAYS = 30
_JWT_ALGORITHM = "HS256"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallbackRequest(BaseModel):
    code: str
    state: str | None = None


# --------------------------------------------------------------------------- #
# Auth dependency: get_current_user
# --------------------------------------------------------------------------- #


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Validate the session JWT from the ``session_jwt`` cookie.

    Raises HTTP 401 on missing, expired, or invalid tokens.
    """
    token = request.cookies.get("session_jwt")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session cookie.",
        )
    settings = get_settings()

    try:
        secret = settings.require("session_secret")
    except RuntimeError as exc:
        logger.error("Auth failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session secret is not configured on the server.",
        ) from exc

    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired.",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session token: {exc}",
        ) from exc

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user_id.",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User belonging to this token no longer exists.",
        )

    return user


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("/github/login")
def github_login() -> dict[str, str]:
    """Return the GitHub OAuth authorization URL."""
    settings = get_settings()
    client_id = settings.github_app_client_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GITHUB_APP_CLIENT_ID is not configured.",
        )

    state = secrets.token_urlsafe(16)
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}&state={state}"
    )
    return {"url": url, "state": state}


@router.post("/github/callback")
def github_callback(
    req: CallbackRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Exchange an OAuth authorization code for a session JWT.

    1. Exchanges ``code`` with GitHub for a temporary user access token.
    2. Queries ``GET /user`` for identity.
    3. Queries ``GET /user/installations`` to discover visible installations.
    4. Upserts ``User`` and updates ``UserInstallation`` links.
    5. Issues an HS256 session JWT valid for 30 days.
    """
    settings = get_settings()

    try:
        client_id = settings.require("github_app_client_id")
        client_secret = settings.require("github_app_client_secret")
        session_secret = settings.require("session_secret")
    except RuntimeError as exc:
        logger.error("OAuth callback failed configuration check: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # Step 1: Exchange code for user token
    token_url = "https://github.com/login/oauth/access_token"
    token_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": req.code,
    }
    if req.state:
        token_payload["state"] = req.state

    try:
        with httpx.Client(timeout=15) as client:
            token_resp = client.post(
                token_url,
                json=token_payload,
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()
    except Exception as exc:
        logger.error("Failed to reach GitHub for token exchange: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub token exchange request failed: {exc}",
        ) from exc

    user_token = token_data.get("access_token")
    if not user_token:
        error_msg = token_data.get("error_description") or token_data.get("error") or "No access token returned"
        logger.warning("GitHub OAuth token exchange failed: %s", error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth error: {error_msg}",
        )

    # Step 2: Fetch user profile
    gh_headers = {
        "Authorization": f"Bearer {user_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        with httpx.Client(timeout=15) as client:
            user_resp = client.get("https://api.github.com/user", headers=gh_headers)
            if user_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch GitHub user profile: {user_resp.text}",
                )
            gh_user = user_resp.json()

            # Step 3: Fetch accessible installations for this user
            inst_resp = client.get(
                "https://api.github.com/user/installations", headers=gh_headers
            )
            installations_data = (
                inst_resp.json().get("installations", [])
                if inst_resp.status_code == 200
                else []
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to query GitHub user API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API query failed: {exc}",
        ) from exc

    # Step 4: Upsert User (NO OAuth token stored!)
    github_user_id = gh_user["id"]
    github_login = gh_user["login"]
    avatar_url = gh_user.get("avatar_url")

    user = (
        db.query(User)
        .filter(User.github_user_id == github_user_id)
        .first()
    )
    if user is None:
        user = User(
            github_user_id=github_user_id,
            github_login=github_login,
            avatar_url=avatar_url,
        )
        db.add(user)
    else:
        user.github_login = github_login
        user.avatar_url = avatar_url
        user.last_login_at = _utcnow()

    db.commit()
    db.refresh(user)

    # Refresh user_installations links live
    active_inst_ids = set()
    for inst_item in installations_data:
        inst_id = inst_item["id"]
        active_inst_ids.add(inst_id)
        account = inst_item.get("account", {})

        # Ensure installation row exists
        inst_row = db.get(Installation, inst_id)
        if inst_row is None:
            inst_row = Installation(
                id=inst_id,
                account_login=account.get("login", ""),
                account_type=account.get("type", "User"),
                app_slug=inst_item.get("app_slug", ""),
                target_type=inst_item.get("repository_selection", "selected"),
            )
            db.add(inst_row)
            db.commit()

        # Link user to installation
        existing_link = (
            db.query(UserInstallation)
            .filter(
                UserInstallation.user_id == user.id,
                UserInstallation.installation_id == inst_id,
            )
            .first()
        )
        role = "admin" if inst_item.get("permissions", {}).get("administration") == "write" else "member"
        if existing_link is None:
            db.add(
                UserInstallation(
                    user_id=user.id,
                    installation_id=inst_id,
                    role=role,
                )
            )
        else:
            existing_link.role = role

    # Remove links to installations the user no longer has access to
    if active_inst_ids:
        (
            db.query(UserInstallation)
            .filter(
                UserInstallation.user_id == user.id,
                ~UserInstallation.installation_id.in_(active_inst_ids),
            )
            .delete(synchronize_session=False)
        )
    db.commit()

    # Step 5: Issue session JWT
    now = _utcnow()
    exp = now + timedelta(days=_JWT_EXPIRY_DAYS)
    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "github_login": user.github_login,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    session_token = jwt.encode(payload, session_secret, algorithm=_JWT_ALGORITHM)

    logger.info(
        "OAuth login successful for user %s (id=%d, %d installations synced).",
        user.github_login,
        user.id,
        len(active_inst_ids),
    )

    response.set_cookie(
        key="session_jwt",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_JWT_EXPIRY_DAYS * 24 * 3600,
    )

    return {
        "user": {
            "id": user.id,
            "github_user_id": user.github_user_id,
            "github_login": user.github_login,
            "avatar_url": user.avatar_url,
        },
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the profile and active installations of the logged-in user."""
    installations = [
        {
            "id": link.installation.id,
            "account_login": link.installation.account_login,
            "account_type": link.installation.account_type,
            "target_type": link.installation.target_type,
            "role": link.role,
            "suspended": link.installation.suspended_at is not None,
        }
        for link in current_user.installation_links
        if link.installation and not link.installation.uninstalled_at
    ]

    return {
        "id": current_user.id,
        "github_user_id": current_user.github_user_id,
        "github_login": current_user.github_login,
        "avatar_url": current_user.avatar_url,
        "installations": installations,
    }


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Acknowledge user logout and clear session cookie."""
    response.delete_cookie("session_jwt", httponly=True, secure=True, samesite="lax")
    return {"status": "ok"}
