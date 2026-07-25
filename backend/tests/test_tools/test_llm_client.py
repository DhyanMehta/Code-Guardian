"""Tests for the Groq LLM client wrapper."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from groq import (
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
)

from backend.tools.llm_client import (
    LLMAuthError,
    LLMClient,
    LLMConfigError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
)

_REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=_REQ)


def _completion(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class _FakeCreate:
    """Callable that yields queued results/exceptions on successive calls."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = outcomes
        self.calls = 0

    def __call__(self, **kwargs):
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_client(create: _FakeCreate, **kw) -> LLMClient:
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return LLMClient(client=fake, **kw)


def test_missing_api_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # No client injected and empty key -> config error.
    with pytest.raises(LLMConfigError):
        LLMClient(api_key="")


def test_complete_success() -> None:
    create = _FakeCreate([_completion("triaged output")])
    client = _make_client(create)
    out = client.complete(system_prompt="s", user_prompt="u")
    assert out == "triaged output"
    assert create.calls == 1


def test_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda d: slept.append(d))
    create = _FakeCreate(
        [
            APIConnectionError(request=_REQ),
            APIConnectionError(request=_REQ),
            _completion("ok"),
        ]
    )
    client = _make_client(create, max_retries=3, backoff_base=0.1)
    out = client.complete(system_prompt="s", user_prompt="u")
    assert out == "ok"
    assert create.calls == 3
    # Two backoff sleeps with exponential growth.
    assert slept == [0.1, 0.2]


def test_auth_error_not_retried() -> None:
    create = _FakeCreate([AuthenticationError("bad key", response=_resp(401), body=None)])
    client = _make_client(create)
    with pytest.raises(LLMAuthError):
        client.complete(system_prompt="s", user_prompt="u")
    assert create.calls == 1  # not retried


def test_rate_limit_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda d: None)
    create = _FakeCreate(
        [RateLimitError("rl", response=_resp(429), body=None) for _ in range(3)]
    )
    client = _make_client(create, max_retries=2, backoff_base=0.01)
    with pytest.raises(LLMRateLimitError):
        client.complete(system_prompt="s", user_prompt="u")
    assert create.calls == 3  # initial + 2 retries


def test_malformed_response_raises() -> None:
    create = _FakeCreate([SimpleNamespace(choices=[])])
    client = _make_client(create)
    with pytest.raises(LLMResponseError):
        client.complete(system_prompt="s", user_prompt="u")


def test_empty_content_raises() -> None:
    create = _FakeCreate([_completion("   ")])
    client = _make_client(create)
    with pytest.raises(LLMResponseError):
        client.complete(system_prompt="s", user_prompt="u")
