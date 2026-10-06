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
from backend.tools.git_auth import git_auth, git_environment

logger = logging.getLogger(__name__)

DEFAULT_CLONE_TIMEOUT = 60

# The review pipeline diffs the head commit against its parent (``HEAD~1``) to work
# out what the PR changed. A depth of 1 leaves ``HEAD~1`` unresolvable in the shallow
# clone (``fatal: ambiguous argument 'HEAD~1'``), which silently produced an empty
# diff and starved the Quality / Test-Gap / Documentation agents of input. Depth 2
# keeps the clone cheap while guaranteeing the parent commit is present.
CLONE_DEPTH = 2


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
def checkout_pr(repo_full_name, head_sha, github_token, **kwargs):
    with git_auth(github_token):
        with _checkout_pr(repo_full_name, head_sha, github_token, **kwargs) as workspace:
            yield workspace


@contextmanager
def _checkout_pr(
    repo_full_name: str,
    head_sha: str,
    github_token: str,
    *,
    base_sha: str | None = None,
    base_ref: str | None = None,
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

    clone_url = f"https://github.com/{repo_full_name}.git"
    tmp_dir = tempfile.mkdtemp(prefix="codeguardian_")
    ws = WorkspaceContext(path=tmp_dir)

    try:
        depth = 1000 if (base_sha or base_ref) else CLONE_DEPTH
        _run_git(
            ["git", "clone", f"--depth={depth}", clone_url, tmp_dir],
            timeout=timeout,
            context="clone",
        )
        _run_git(
            ["git", "fetch", f"--depth={depth}", "origin", head_sha],
            timeout=timeout,
            cwd=tmp_dir,
            context="fetch SHA",
        )
        if base_sha:
            try:
                _run_git(
                    ["git", "fetch", f"--depth={depth}", "origin", base_sha],
                    timeout=timeout,
                    cwd=tmp_dir,
                    context="fetch base SHA",
                )
            except WorkspaceError as exc:
                if base_ref:
                    logger.warning(
                        "Direct fetch of base_sha %s failed (%s); falling back to fetching base_ref %s",
                        base_sha, exc, base_ref
                    )
                    _run_git(
                        ["git", "fetch", f"--depth={depth}", "origin", f"{base_ref}:refs/remotes/origin/{base_ref}"],
                        timeout=timeout,
                        cwd=tmp_dir,
                        context="fetch base ref fallback",
                    )
                else:
                    raise
        elif base_ref:
            _run_git(
                ["git", "fetch", f"--depth={depth}", "origin", f"{base_ref}:refs/remotes/origin/{base_ref}"],
                timeout=timeout,
                cwd=tmp_dir,
                context="fetch base ref",
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
            env=git_environment(),
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
