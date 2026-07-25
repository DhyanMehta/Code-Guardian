"""PR workspace checkout utility.

Provides a context manager that shallow-clones a GitHub repository at a specific
commit SHA into a temporary directory. Used by the Supervisor (Session 5) to provide
a local ``workspace_path`` to all agents. See ``RULES.md`` #9: every subprocess call
has explicit error handling, timeouts, and typed errors.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_CLONE_TIMEOUT = 60


class WorkspaceError(Exception):
    """Any failure during workspace creation or cleanup."""


@dataclass
class WorkspaceContext:
    """Handle to a temporary checkout directory."""

    path: str

    def cleanup(self) -> None:
        """Remove the temporary directory. Safe to call multiple times."""
        p = Path(self.path)
        if p.exists():
            shutil.rmtree(self.path, onerror=_force_remove_readonly)
            logger.info("Cleaned up workspace: %s", self.path)


def _force_remove_readonly(func, path, _exc_info):
    """Handle read-only files on Windows (e.g. .git/objects)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


@contextmanager
def checkout_pr(
    repo_full_name: str,
    head_sha: str,
    github_token: str,
    *,
    timeout: int = DEFAULT_CLONE_TIMEOUT,
) -> Iterator[WorkspaceContext]:
    """Clone a repo at a specific SHA into a temp directory.

    Usage::

        with checkout_pr("owner/repo", "abc123f", token) as ws:
            # ws.path is the root of the checkout
            ...
        # temp dir is removed on exit

    Raises:
        WorkspaceError: git is not installed, clone fails, or checkout fails.
    """
    if not repo_full_name or not head_sha or not github_token:
        raise WorkspaceError(
            "repo_full_name, head_sha, and github_token are all required."
        )

    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"
    tmp_dir = tempfile.mkdtemp(prefix="codeguardian_")
    ws = WorkspaceContext(path=tmp_dir)

    try:
        _run_git(
            ["git", "clone", "--depth=1", clone_url, tmp_dir],
            timeout=timeout,
            context="clone",
        )
        _run_git(
            ["git", "fetch", "--depth=1", "origin", head_sha],
            timeout=timeout,
            cwd=tmp_dir,
            context="fetch SHA",
        )
        _run_git(
            ["git", "checkout", head_sha],
            timeout=timeout,
            cwd=tmp_dir,
            context="checkout SHA",
        )
    except WorkspaceError:
        ws.cleanup()
        raise

    try:
        yield ws
    finally:
        ws.cleanup()


def _run_git(
    command: list[str],
    *,
    timeout: int,
    cwd: str | None = None,
    context: str = "",
) -> subprocess.CompletedProcess[str]:
    """Execute a git command with timeout and typed error handling."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        raise WorkspaceError(
            f"git executable not found ({context}): {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceError(
            f"git {context} timed out after {timeout}s"
        ) from exc
    except OSError as exc:
        raise WorkspaceError(
            f"OS error during git {context}: {exc}"
        ) from exc

    if result.returncode != 0:
        stderr_snippet = (result.stderr or "").strip()[:500]
        raise WorkspaceError(
            f"git {context} failed (exit {result.returncode}): {stderr_snippet}"
        )

    return result
