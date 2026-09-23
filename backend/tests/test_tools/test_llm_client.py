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


from groq import BadRequestError

def _bad_request(empty_generation: bool = False) -> BadRequestError:
    body = {"error": {"code": "json_validate_failed"}}
    if empty_generation:
        body["error"]["failed_generation"] = ""
    else:
        body["error"]["failed_generation"] = "{"
    
    return BadRequestError(
        message="bad",
        response=_resp(400),
        body=body
    )


def test_empty_generation_retried_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda d: slept.append(d))
    
    # Fails once with empty generation, then succeeds
    create = _FakeCreate(
        [
            _bad_request(empty_generation=True),
            _completion("success"),
        ]
    )
    client = _make_client(create)
    out = client.complete(system_prompt="s", user_prompt="u")
    assert out == "success"
    assert create.calls == 2
    assert slept == [2.0]  # 2-second short delay


def test_empty_generation_exhausts_retries_and_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda d: slept.append(d))
    
    # Fails 3 times (initial + 2 retries) with empty generation
    create = _FakeCreate(
        [
            _bad_request(empty_generation=True),
            _bad_request(empty_generation=True),
            _bad_request(empty_generation=True),
        ]
    )
    client = _make_client(create)
    with pytest.raises(LLMResponseError, match="request rejected as invalid"):
        client.complete(system_prompt="s", user_prompt="u")
    assert create.calls == 3
    assert slept == [2.0, 2.0]


def test_normal_bad_request_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda d: slept.append(d))
    
    # Fails with a real validation failure (not empty)
    create = _FakeCreate(
        [
            _bad_request(empty_generation=False),
        ]
    )
    client = _make_client(create)
    with pytest.raises(LLMResponseError, match="request rejected as invalid"):
        client.complete(system_prompt="s", user_prompt="u")
    assert create.calls == 1
    assert not slept


# --------------------------------------------------------------------------- #
# Call throttle
#
# Four agents fan out in parallel and each may call the LLM. On Groq's free tier
# that reliably trips a 429. The throttle gates the calls without changing how the
# graph schedules the agents.
# --------------------------------------------------------------------------- #


class TestCallThrottle:
    def _client(self, monkeypatch, *, concurrency=1, interval=0.0):
        """A client whose provider call records start/end timestamps."""
        import time as _time
        from unittest.mock import MagicMock

        from backend.config import get_settings
        from backend.tools import llm_client as module

        settings = get_settings()
        monkeypatch.setattr(settings, "llm_max_concurrent_calls", concurrency,
                            raising=False)
        monkeypatch.setattr(settings, "llm_min_call_interval_seconds", interval,
                            raising=False)
        module.reset_throttle()

        windows: list[tuple[float, float]] = []

        def _create(**_kwargs):
            start = _time.monotonic()
            _time.sleep(0.05)
            windows.append((start, _time.monotonic()))
            response = MagicMock()
            response.choices[0].message.content = "ok"
            return response

        fake_provider = MagicMock()
        fake_provider.chat.completions.create.side_effect = _create
        client = module.LLMClient(client=fake_provider, max_retries=0)
        return client, windows, module

    def test_concurrent_calls_do_not_overlap_at_concurrency_one(self, monkeypatch):
        import threading

        client, windows, module = self._client(monkeypatch, concurrency=1)

        threads = [
            threading.Thread(
                target=client.complete,
                kwargs={"system_prompt": "s", "user_prompt": f"u{i}"},
            )
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(windows) == 4
        ordered = sorted(windows)
        for (_, prev_end), (next_start, _) in zip(ordered, ordered[1:]):
            assert next_start >= prev_end - 1e-6, "calls overlapped despite the gate"

        module.reset_throttle()

    def test_minimum_interval_spaces_consecutive_calls(self, monkeypatch):
        client, windows, module = self._client(monkeypatch, interval=0.20)

        for i in range(3):
            client.complete(system_prompt="s", user_prompt=f"u{i}")

        starts = [w[0] for w in windows]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        assert all(gap >= 0.18 for gap in gaps), f"gaps too small: {gaps}"

        module.reset_throttle()

    def test_zero_interval_does_not_delay(self, monkeypatch):
        client, windows, module = self._client(monkeypatch, interval=0.0)

        for i in range(3):
            client.complete(system_prompt="s", user_prompt=f"u{i}")

        starts = [w[0] for w in windows]
        assert starts[-1] - starts[0] < 0.5
        module.reset_throttle()

    def test_retries_stay_inside_one_slot(self, monkeypatch):
        """A backing-off caller must not hand its slot to three others mid-window."""
        from unittest.mock import MagicMock

        from groq import RateLimitError

        from backend.config import get_settings
        from backend.tools import llm_client as module

        settings = get_settings()
        monkeypatch.setattr(settings, "llm_max_concurrent_calls", 1, raising=False)
        monkeypatch.setattr(settings, "llm_min_call_interval_seconds", 0.0,
                            raising=False)
        module.reset_throttle()

        attempts = {"n": 0}

        def _create(**_kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RateLimitError(
                    "429", response=MagicMock(status_code=429), body=None
                )
            response = MagicMock()
            response.choices[0].message.content = "recovered"
            return response

        provider = MagicMock()
        provider.chat.completions.create.side_effect = _create
        client = module.LLMClient(client=provider, max_retries=2, backoff_base=0.01)

        assert client.complete(system_prompt="s", user_prompt="u") == "recovered"
        assert attempts["n"] == 2
        module.reset_throttle()
