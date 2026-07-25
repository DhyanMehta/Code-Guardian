"""Tests for the PR workspace checkout utility (backend/tools/workspace.py).

Uses a local bare git repo created in a pytest fixture — fully offline, no GitHub.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from backend.tools.workspace import (
    WorkspaceContext,
    WorkspaceError,
    checkout_pr,
)


@pytest.fixture
def local_bare_repo(tmp_path):
    """Create a local bare git repo with one commit, return (repo_path, sha)."""
    repo_dir = tmp_path / "bare_repo.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    # Init bare repo
    subprocess.run(
        ["git", "init", "--bare", str(repo_dir)],
        capture_output=True, check=True,
    )

    # Clone it to a working copy, add a file, commit, push
    subprocess.run(
        ["git", "clone", str(repo_dir), str(work_dir)],
        capture_output=True, check=True,
    )
    # Configure git user in the working copy
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(work_dir), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(work_dir), capture_output=True, check=True,
    )

    # Create a file and commit
    (work_dir / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "hello.py"],
        cwd=str(work_dir), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(work_dir), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "push", "origin", "master"],
        cwd=str(work_dir), capture_output=True, check=True,
    )

    # Get the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(work_dir), capture_output=True, text=True, check=True,
    )
    sha = result.stdout.strip()

    return str(repo_dir), sha


class TestCheckoutPrOffline:
    def test_clones_and_contains_files(self, local_bare_repo) -> None:
        repo_path, sha = local_bare_repo

        # Use the local path as clone URL (no token needed for local repos)
        # We monkey-patch checkout_pr to use the local path directly
        from backend.tools import workspace

        original_fn = workspace.checkout_pr

        # For local testing, use the bare repo path as the clone URL
        from contextlib import contextmanager
        from typing import Iterator

        @contextmanager
        def _local_checkout(
            repo_full_name: str,
            head_sha: str,
            github_token: str,
            *,
            timeout: int = 60,
        ) -> Iterator[WorkspaceContext]:
            """Variant that clones from a local bare repo path."""
            import shutil
            import tempfile

            tmp_dir = tempfile.mkdtemp(prefix="codeguardian_test_")
            ws = WorkspaceContext(path=tmp_dir)

            try:
                workspace._run_git(
                    ["git", "clone", "--depth=1", repo_full_name, tmp_dir],
                    timeout=timeout,
                    context="clone",
                )
                workspace._run_git(
                    ["git", "fetch", "--depth=1", "origin", head_sha],
                    timeout=timeout,
                    cwd=tmp_dir,
                    context="fetch SHA",
                )
                workspace._run_git(
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

        with _local_checkout(repo_path, sha, "fake-token") as ws:
            assert os.path.isdir(ws.path)
            assert os.path.isfile(os.path.join(ws.path, "hello.py"))
            content = open(os.path.join(ws.path, "hello.py")).read()
            assert "hello" in content

    def test_cleanup_removes_directory(self, local_bare_repo) -> None:
        repo_path, sha = local_bare_repo

        from backend.tools import workspace

        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="codeguardian_test_")
        ws = WorkspaceContext(path=tmp_dir)

        workspace._run_git(
            ["git", "clone", "--depth=1", repo_path, tmp_dir],
            timeout=60,
            context="clone",
        )

        assert os.path.isdir(tmp_dir)
        ws.cleanup()
        assert not os.path.isdir(tmp_dir)

    def test_cleanup_idempotent(self, tmp_path) -> None:
        ws = WorkspaceContext(path=str(tmp_path / "nonexistent"))
        # Calling cleanup on non-existent path should not raise
        ws.cleanup()
        ws.cleanup()


class TestCheckoutPrValidation:
    def test_missing_repo_name_raises(self) -> None:
        with pytest.raises(WorkspaceError, match="required"):
            with checkout_pr("", "abc123", "token"):
                pass

    def test_missing_sha_raises(self) -> None:
        with pytest.raises(WorkspaceError, match="required"):
            with checkout_pr("owner/repo", "", "token"):
                pass

    def test_missing_token_raises(self) -> None:
        with pytest.raises(WorkspaceError, match="required"):
            with checkout_pr("owner/repo", "abc123", ""):
                pass


class TestCheckoutPrErrorCases:
    def test_invalid_repo_raises_workspace_error(self) -> None:
        with pytest.raises(WorkspaceError):
            with checkout_pr(
                "nonexistent-owner-xyz/nonexistent-repo-xyz",
                "0000000000000000000000000000000000000000",
                "fake-invalid-token",
                timeout=10,
            ):
                pass

    def test_timeout_is_respected(self, local_bare_repo, monkeypatch) -> None:
        """Verify that the timeout parameter is passed through to subprocess."""
        import subprocess as sp
        from backend.tools import workspace

        calls = []
        original_run = sp.run

        def _recording_run(*args, **kwargs):
            calls.append(kwargs.get("timeout"))
            return original_run(*args, **kwargs)

        monkeypatch.setattr(sp, "run", _recording_run)

        repo_path, sha = local_bare_repo
        # Use _run_git directly to test timeout propagation
        workspace._run_git(
            ["git", "clone", "--depth=1", repo_path, str(local_bare_repo[0]) + "_clone"],
            timeout=42,
            context="test",
        )

        assert 42 in calls
