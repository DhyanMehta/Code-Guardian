"""Tests for the GitHub client wrapper."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from github.GithubException import (
    BadCredentialsException,
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)

from backend.tools.github_client import (
    GitHubApiError,
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


def _fake_file(**kw):
    defaults = dict(
        filename="app/x.py",
        status="modified",
        additions=3,
        deletions=1,
        changes=4,
        patch="@@ -1 +1 @@\n-old\n+new",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class _FakeGithub:
    def __init__(self, files=None, head_sha="abc123", exc=None):
        self._files = files if files is not None else [_fake_file()]
        self._head_sha = head_sha
        self._exc = exc

    def get_repo(self, name):
        if self._exc is not None:
            raise self._exc
        pull = SimpleNamespace(
            get_files=lambda: self._files,
            head=SimpleNamespace(sha=self._head_sha),
        )
        return SimpleNamespace(get_pull=lambda n: pull)


def test_get_pull_request_diff_success() -> None:
    client = GitHubClient(client=_FakeGithub(files=[_fake_file(), _fake_file(filename="b.py")]))
    diff = client.get_pull_request_diff("acme/widgets", 7)
    assert diff.repo_full_name == "acme/widgets"
    assert diff.pr_number == 7
    assert diff.head_sha == "abc123"
    assert diff.filenames == ["app/x.py", "b.py"]
    assert "app/x.py" in diff.unified_diff


def test_missing_token_raises_auth_error() -> None:
    with pytest.raises(GitHubAuthError):
        GitHubClient(token="")


def test_rate_limit_mapped() -> None:
    gh = _FakeGithub(exc=RateLimitExceededException(403, {"message": "rate"}, {}))
    client = GitHubClient(client=gh)
    with pytest.raises(GitHubRateLimitError):
        client.get_pull_request_diff("acme/widgets", 1)


def test_bad_credentials_mapped() -> None:
    gh = _FakeGithub(exc=BadCredentialsException(401, {"message": "bad"}, {}))
    client = GitHubClient(client=gh)
    with pytest.raises(GitHubAuthError):
        client.get_pull_request_diff("acme/widgets", 1)


def test_unknown_object_mapped_to_not_found() -> None:
    gh = _FakeGithub(exc=UnknownObjectException(404, {"message": "nope"}, {}))
    client = GitHubClient(client=gh)
    with pytest.raises(GitHubNotFoundError):
        client.get_pull_request_diff("acme/widgets", 999)


def test_generic_404_mapped_to_not_found() -> None:
    gh = _FakeGithub(exc=GithubException(404, {"message": "missing"}, {}))
    client = GitHubClient(client=gh)
    with pytest.raises(GitHubNotFoundError):
        client.get_pull_request_diff("acme/widgets", 999)


def test_generic_500_mapped_to_api_error() -> None:
    gh = _FakeGithub(exc=GithubException(500, {"message": "boom"}, {}))
    client = GitHubClient(client=gh)
    with pytest.raises(GitHubApiError):
        client.get_pull_request_diff("acme/widgets", 1)
