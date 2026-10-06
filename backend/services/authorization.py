"""GitHub user-scoped authorization. Installation tokens never authorize a person."""
from datetime import datetime, timedelta, timezone
import time

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from github import Auth, Github
from sqlalchemy.orm import object_session

from backend.config import get_settings


def encrypt_token(token: str) -> str:
    return Fernet(get_settings().require("token_encryption_key").encode()).encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    try:
        return Fernet(get_settings().require("token_encryption_key").encode()).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, RuntimeError) as exc:
        raise HTTPException(503, "OAuth credential storage unavailable; contact the administrator.") from exc


def user_token(user) -> str:
    if not user.access_token_enc:
        raise HTTPException(401, "Please sign in with GitHub again.")
    expiry = user.token_expires_at
    if expiry and expiry.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) + timedelta(seconds=60):
        session = object_session(user)
        if session:
            from backend.db.models import User
            user = session.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
            expiry = user.token_expires_at
            if expiry and expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) + timedelta(seconds=60):
                session.commit()
                return decrypt_token(user.access_token_enc)
        if not user.refresh_token_enc:
            raise HTTPException(401, "GitHub authorization expired; sign in again.")
        settings = get_settings()
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post("https://github.com/login/oauth/access_token", json={
                    "client_id": settings.require("github_app_client_id"),
                    "client_secret": settings.require("github_app_client_secret"),
                    "grant_type": "refresh_token", "refresh_token": decrypt_token(user.refresh_token_enc),
                }, headers={"Accept": "application/json"})
                response.raise_for_status()
                data = response.json()
            if not data.get("access_token"):
                raise HTTPException(401, "GitHub authorization expired; sign in again.")
            store_tokens(user, data)
            if session:
                session.commit()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "Could not refresh GitHub authorization.") from exc
    return decrypt_token(user.access_token_enc)


def store_tokens(user, data):
    user.access_token_enc = encrypt_token(data["access_token"])
    if data.get("refresh_token"):
        user.refresh_token_enc = encrypt_token(data["refresh_token"])
    user.token_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))) if data.get("expires_in") else None


def github_json(token: str, path: str, *, params=None):
    """Bounded retries for idempotent GitHub reads; never expose response secrets."""
    for attempt in range(3):
        try:
            with httpx.Client(timeout=15) as client:
                response = client.get("https://api.github.com" + path, params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
            if response.status_code in (401, 403, 404):
                raise HTTPException(401 if response.status_code == 401 else 403, "GitHub access is unavailable for this resource.")
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == 2:
                raise HTTPException(502, "GitHub is temporarily unavailable.") from exc
            time.sleep(0.25 * 2**attempt)


def github_pages(token: str, path: str, key: str):
    items = []
    for page in range(1, 101):
        data = github_json(token, path, params={"per_page": 100, "page": page})
        batch = data.get(key, [])
        items.extend(batch)
        if len(batch) < 100:
            return items
    raise HTTPException(502, "GitHub result exceeds the supported pagination bound.")


def accessible_repos(user, installation_id: int):
    return github_pages(user_token(user), f"/user/installations/{installation_id}/repositories", "repositories")


def authorized_repo_names(user):
    names = set()
    for link in user.installation_links:
        inst = link.installation
        if inst and not inst.uninstalled_at and not inst.suspended_at:
            names.update(r["full_name"] for r in accessible_repos(user, inst.id))
    return names


def require_repo(user, installation_id: int, name: str, *, write=False):
    link = next((x for x in user.installation_links if x.installation_id == installation_id), None)
    if not link or not link.installation or link.installation.uninstalled_at or link.installation.suspended_at:
        raise HTTPException(403, "Installation is not accessible.")
    if name not in {r["full_name"] for r in accessible_repos(user, installation_id)}:
        raise HTTPException(403, "You do not have access to this repository.")
    if write:
        permissions = github_json(user_token(user), f"/repos/{name}").get("permissions", {})
        if not (permissions.get("push") or permissions.get("maintain") or permissions.get("admin")):
            raise HTTPException(403, "Repository write permission is required.")


def is_manager(token, login, account_login, account_type):
    if account_type == "User":
        return login.casefold() == account_login.casefold()
    try:
        membership = github_json(token, f"/user/memberships/orgs/{account_login}")
        return membership.get("state") == "active" and membership.get("role") == "admin"
    except HTTPException as exc:
        if exc.status_code == 403:
            return False
        raise


def require_manager(user, installation):
    if not is_manager(user_token(user), user.github_login, installation.account_login, installation.account_type):
        raise HTTPException(403, "Verified installation owner or organization admin required.")


def user_github(user):
    return Github(auth=Auth.Token(user_token(user)), timeout=15)
