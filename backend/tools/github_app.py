"""GitHub App authentication helpers.

Provides a process-wide ``Auth.AppAuth`` instance, ``GithubIntegration`` for
issuing installation access tokens, and helper functions to acquire scoped
Github clients and raw tokens.

The private key is loaded once at first use from the path configured via
``GITHUB_APP_PRIVATE_KEY_PATH``.  It is never logged, serialized, or returned
in any API response.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from github import Auth, Github, GithubIntegration

from backend.config import get_settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Module-level singletons and cache, guarded by a lock for thread safety.
# --------------------------------------------------------------------------- #
_lock = threading.RLock()
_app_auth: Auth.AppAuth | None = None
_integration: GithubIntegration | None = None
_cached_tokens: dict[int, tuple[str, datetime]] = {}


def _load_private_key(path: str) -> str:
    """Read the PEM private key from *path* and return its contents.

    Raises ``RuntimeError`` if the file is missing or unreadable.
    """
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(
            f"GitHub App private key not found at '{p}'. "
            "Set GITHUB_APP_PRIVATE_KEY_PATH in your .env."
        )
    try:
        key = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read GitHub App private key at '{p}': {exc}"
        ) from exc

    if "PRIVATE KEY" not in key:
        raise RuntimeError(
            f"File at '{p}' does not look like a PEM private key."
        )

    return key


def get_app_auth() -> Auth.AppAuth:
    """Return the cached, process-wide ``AppAuth`` instance.

    Creates it lazily on first call.  The underlying JWT is re-signed by
    PyGithub whenever it approaches expiry (10-minute window), so a single
    ``AppAuth`` is safe to keep for the lifetime of the process.
    """
    global _app_auth  # noqa: PLW0603
    if _app_auth is not None:
        return _app_auth

    with _lock:
        if _app_auth is not None:
            return _app_auth

        settings = get_settings()
        app_id = settings.github_app_id
        key_path = settings.github_app_private_key_path

        if not app_id:
            raise RuntimeError(
                "GITHUB_APP_ID is not configured. "
                "Set it in your environment or .env file."
            )
        if not key_path:
            raise RuntimeError(
                "GITHUB_APP_PRIVATE_KEY_PATH is not configured. "
                "Set it in your environment or .env file."
            )

        private_key = _load_private_key(key_path)
        _app_auth = Auth.AppAuth(app_id=app_id, private_key=private_key)
        logger.info(
            "GitHub App auth initialized (app_id=%d, key=%s).",
            app_id,
            Path(key_path).name,  # log filename only, never contents
        )
        return _app_auth


def get_integration() -> GithubIntegration:
    """Return the cached, process-wide ``GithubIntegration`` instance."""
    global _integration  # noqa: PLW0603
    if _integration is not None:
        return _integration

    with _lock:
        if _integration is not None:
            return _integration

        app_auth = get_app_auth()
        _integration = GithubIntegration(auth=app_auth)
        return _integration


def get_installation_token(installation_id: int) -> str:
    """Return a valid access token string for *installation_id*.

    This is used where a plain token string is needed rather than a PyGithub
    auth object — primarily for ``git clone`` URLs of the form
    ``https://x-access-token:{token}@github.com/...``.

    Tokens are cached in memory and refreshed automatically when within 60s
    of expiration.
    """
    now = datetime.now(timezone.utc)

    with _lock:
        if installation_id in _cached_tokens:
            token, expires_at = _cached_tokens[installation_id]
            if (expires_at - now).total_seconds() > 60:
                return token

        gi = get_integration()
        auth_obj = gi.get_access_token(installation_id)
        expires_at = auth_obj.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        _cached_tokens[installation_id] = (auth_obj.token, expires_at)
        logger.info(
            "Acquired new installation token for installation_id=%d (expires %s).",
            installation_id,
            expires_at.isoformat(),
        )
        return auth_obj.token


def get_installation_auth(installation_id: int) -> Auth.Token:
    """Return an ``Auth.Token`` object for *installation_id*."""
    token = get_installation_token(installation_id)
    return Auth.Token(token)


def get_installation_github(installation_id: int) -> Github:
    """Return a ``Github`` client authenticated as *installation_id*."""
    auth = get_installation_auth(installation_id)
    return Github(auth=auth, timeout=15)


def invalidate_installation(installation_id: int) -> None:
    """Remove a cached installation token (e.g. after an uninstall event)."""
    with _lock:
        _cached_tokens.pop(installation_id, None)
