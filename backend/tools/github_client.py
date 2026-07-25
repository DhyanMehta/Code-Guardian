"""GitHub client wrapper (PyGithub).

Provides typed, error-handled access to the PyGithub API surface the agents need.
Session 2 adds fetching a pull request's changed files and unified diff. Every call
translates PyGithub failures into a typed :class:`GitHubClientError` subclass — no
bare excepts, no silent failures (see ``RULES.md`` #9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from github import Auth, Github
from github.GithubException import (
    BadCredentialsException,
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15


# --------------------------------------------------------------------------- #
# Typed errors
# --------------------------------------------------------------------------- #
class GitHubClientError(Exception):
    """Base class for GitHub client failures."""


class GitHubAuthError(GitHubClientError):
    """Authentication/authorization failed (bad or missing token, 401/403)."""


class GitHubRateLimitError(GitHubClientError):
    """The GitHub API rate limit was exceeded."""


class GitHubNotFoundError(GitHubClientError):
    """The requested repository or pull request does not exist (404)."""


class GitHubApiError(GitHubClientError):
    """Any other GitHub API error."""


# --------------------------------------------------------------------------- #
# Typed data
# --------------------------------------------------------------------------- #
@dataclass
class ChangedFile:
    """A single file changed in a pull request."""

    filename: str
    status: str  # added / modified / removed / renamed
    additions: int
    deletions: int
    changes: int
    patch: str | None = None  # unified diff hunk (absent for binary files)


@dataclass
class PullRequestDiff:
    """The changed files and combined unified diff for a pull request."""

    repo_full_name: str
    pr_number: int
    head_sha: str
    changed_files: list[ChangedFile] = field(default_factory=list)

    @property
    def filenames(self) -> list[str]:
        return [f.filename for f in self.changed_files]

    @property
    def unified_diff(self) -> str:
        """Concatenated per-file patches (best-effort unified diff)."""
        parts = []
        for f in self.changed_files:
            if f.patch:
                parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")
        return "\n".join(parts)


class GitHubClient:
    """Thin, typed wrapper around a PyGithub client."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        client: Github | None = None,
    ) -> None:
        """Create a client.

        Args:
            token: GitHub token. If omitted, read from settings (``GITHUB_TOKEN``).
            timeout: per-request timeout in seconds.
            client: an existing ``Github`` instance (primarily for testing).
        """
        if client is not None:
            self._gh = client
        else:
            resolved = token if token is not None else get_settings().github_token
            if not resolved:
                raise GitHubAuthError(
                    "No GitHub token configured (set GITHUB_TOKEN or pass token=)."
                )
            self._gh = Github(auth=Auth.Token(resolved), timeout=timeout)

    def get_pull_request_diff(
        self, repo_full_name: str, pr_number: int
    ) -> PullRequestDiff:
        """Fetch the changed files + diff for ``repo_full_name`` PR ``pr_number``.

        Raises:
            GitHubAuthError: authentication/authorization failed.
            GitHubRateLimitError: rate limit exceeded.
            GitHubNotFoundError: the repo or PR does not exist.
            GitHubApiError: any other API error.
        """
        try:
            repo = self._gh.get_repo(repo_full_name)
            pull = repo.get_pull(pr_number)
            changed = [
                ChangedFile(
                    filename=f.filename,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    changes=f.changes,
                    patch=getattr(f, "patch", None),
                )
                for f in pull.get_files()
            ]
        except RateLimitExceededException as exc:
            logger.warning("GitHub rate limit exceeded for %s#%s", repo_full_name, pr_number)
            raise GitHubRateLimitError(f"rate limit exceeded: {exc}") from exc
        except BadCredentialsException as exc:
            logger.error("GitHub authentication failed: %s", exc)
            raise GitHubAuthError(f"authentication failed: {exc}") from exc
        except UnknownObjectException as exc:
            logger.warning("GitHub object not found: %s#%s", repo_full_name, pr_number)
            raise GitHubNotFoundError(
                f"repository or pull request not found: {repo_full_name}#{pr_number}"
            ) from exc
        except GithubException as exc:
            status = getattr(exc, "status", None)
            if status in (401, 403):
                # 403 may also be a rate limit; PyGithub usually raises the
                # dedicated class above, so treat remaining 401/403 as auth.
                raise GitHubAuthError(f"authorization failed (HTTP {status}): {exc}") from exc
            if status == 404:
                raise GitHubNotFoundError(
                    f"not found (HTTP 404): {repo_full_name}#{pr_number}"
                ) from exc
            raise GitHubApiError(f"GitHub API error (HTTP {status}): {exc}") from exc

        return PullRequestDiff(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha=pull.head.sha,
            changed_files=changed,
        )
