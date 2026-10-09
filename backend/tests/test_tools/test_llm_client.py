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
    TokenBucketLimiter,
    _extract_retry_delay,
    _get_token_limiter,
    estimate_tokens,
    reset_throttle,
)

_REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


@pytest.fixture(autouse=True)
def _reset_throttle_each_test():
    reset_throttle()
    yield
    reset_throttle()



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


def test_agent_metrics_count_retries_and_reported_usage(monkeypatch, caplog):
    from backend.tools.llm_metrics import agent_metrics
    # Alembic's logging configuration in migration tests disables existing loggers.
    monkeypatch.setattr('backend.tools.llm_metrics.logger.disabled', False)
    monkeypatch.setattr('backend.tools.llm_client.time.sleep', lambda _: None)
    response = _completion('ok')
    response.usage = SimpleNamespace(total_tokens=42)
    client = _make_client(_FakeCreate([APIConnectionError(request=_REQ), response]), max_retries=1)
    with caplog.at_level('INFO'), agent_metrics('security') as metrics:
        assert client.complete(system_prompt='private-system', user_prompt='private-code') == 'ok'
    assert metrics['calls'] == 1
    assert metrics['requests'] == 2
    assert metrics['retries'] == 1
    assert metrics['responses_with_usage'] == 1
    assert metrics['reported_total_tokens'] == 42
    assert metrics['retry_wait_seconds'] == 0.5
    assert 'private-code' not in caplog.text
    assert 'private-system' not in caplog.text
    assert 'agent_llm_metrics' in caplog.text


def test_agent_metrics_are_isolated_and_unknown_usage_is_explicit():
    from concurrent.futures import ThreadPoolExecutor
    from backend.tools.llm_metrics import agent_metrics, measure
    def run(name):
        with agent_metrics(name) as metrics:
            measure('calls', 2)
        return metrics
    with ThreadPoolExecutor(max_workers=2) as pool:
        metrics = list(pool.map(run, ['quality', 'documentation']))
    assert [m['calls'] for m in metrics] == [2, 2]
    assert all(m['responses_with_usage'] == 0 for m in metrics)


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


# --------------------------------------------------------------------------- #
# Token Bucket Limiter & Rate Limiting Requirements
# --------------------------------------------------------------------------- #


class TestTokenLimiter:
    def test_requests_below_budget_proceed_immediately(self) -> None:
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        # Safe budget is 6400
        waited = limiter.acquire(2000, max_wait=5.0)
        assert waited < 0.1
        waited2 = limiter.acquire(2000, max_wait=5.0)
        assert waited2 < 0.1
        assert len(limiter._history) == 2

    def test_request_exceeding_budget_waits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        slept: list[float] = []
        monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda s: slept.append(s))
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        # First acquire 5000 tokens (safe limit is 6400)
        limiter.acquire(5000, max_wait=70.0)
        # Second acquire needs 2000 tokens -> 5000 + 2000 = 7000 > 6400 -> must wait
        limiter.acquire(2000, max_wait=70.0)
        assert len(slept) > 0
        assert slept[0] > 0

    def test_old_requests_evicted_from_rolling_window(self) -> None:
        import time as _time
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        now = _time.monotonic()
        # Add an old request from 65 seconds ago
        limiter.record_tokens(5000, ts=now - 65.0)
        limiter._evict_expired(now)
        assert len(limiter._history) == 0
        # New request for 5000 proceeds immediately without waiting
        waited = limiter.acquire(5000, max_wait=5.0)
        assert waited < 0.1

    def test_concurrent_callers_do_not_bypass_budget(self) -> None:
        import threading
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        results = []

        def worker():
            w = limiter.acquire(1000, max_wait=2.0)
            results.append(w)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 6
        assert len(limiter._history) == 6
        total_tokens = sum(t for _, t in limiter._history)
        assert total_tokens == 6000 <= 6400

    def test_reconciliation_updates_reservation(self) -> None:
        import time as _time
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        now = _time.monotonic()
        limiter.acquire(3000, max_wait=5.0)
        assert limiter._history[0][1] == 3000
        # Reconcile with actual provider usage
        limiter.reconcile(now, 3000, 2450)
        assert limiter._history[0][1] == 2450

    def test_cooldown_blocks_until_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        slept: list[float] = []
        monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda s: slept.append(s))
        limiter = TokenBucketLimiter(tpm_limit=8000, safety_margin=0.8, window_seconds=60.0)
        limiter.record_cooldown(12.5)
        limiter.acquire(500, max_wait=70.0)
        assert len(slept) > 0
        assert slept[0] >= 12.0


class TestRateLimitDelayParsingDetailed:
    @pytest.mark.parametrize(
        ("message", "expected_delay"),
        [
            ("Please try again in 12.9s", 12.9),
            ("Please try again in 18.62s", 18.62),
            ("Please try again in 14.1375s", 14.1375),
            ("Rate limit reached for model `openai/gpt-oss-120b`. Please try again in 18.62s.", 18.62),
            ("rate limited: retry in 4.5s", 4.5),
        ],
    )
    def test_extract_retry_delay_formats(self, message: str, expected_delay: float) -> None:
        assert _extract_retry_delay(message) == expected_delay


def test_empty_generation_records_tokens_and_paces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated 400 json_validate_failed with empty generation records prompt tokens and paces."""
    slept: list[float] = []
    monkeypatch.setattr("backend.tools.llm_client.time.sleep", lambda s: slept.append(s))

    limiter = _get_token_limiter()
    limiter.reset()

    create = _FakeCreate(
        [
            _bad_request(empty_generation=True),
            _completion("{\"findings\": []}"),
        ]
    )
    client = _make_client(create)
    res = client.complete(system_prompt="s" * 300, user_prompt="u" * 600)
    assert res == "{\"findings\": []}"
    assert create.calls == 2
    # Verify limiter recorded both the failed prompt tokens and the retry reservation
    assert len(limiter._history) >= 2
    limiter.reset()
