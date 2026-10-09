"""Groq LLM client wrapper.

Provides a small, typed, retry-aware interface around the Groq SDK. The LLM is used
strictly to explain / triage / prioritize deterministic tool output — never to
originate a finding (see ``RULES.md`` #5).

Design notes:
- The Groq SDK's built-in retries are disabled (``max_retries=0``) so this wrapper
  owns retry/backoff deterministically (and so it can be unit tested).
- Transient errors (rate limit, connection, timeout, 5xx) are retried with
  exponential backoff. Auth errors and bad requests are not retried.
- Every failure surfaces as a typed :class:`LLMError` subclass; there are no bare
  ``except`` blocks and nothing is swallowed silently.
"""

from __future__ import annotations

import logging
import threading
import time
import re
import uuid
from contextlib import contextmanager

import openai
from groq import Groq
from groq import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

from backend.config import get_settings
from backend.tools.llm_metrics import measure

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Typed errors
# --------------------------------------------------------------------------- #
class LLMError(Exception):
    """Base class for LLM client failures."""


class LLMConfigError(LLMError):
    """The client is misconfigured (e.g. missing API key)."""


class LLMAuthError(LLMError):
    """Authentication/authorization with the LLM provider failed."""


class LLMRateLimitError(LLMError):
    """The provider rate limit was exceeded (after retries were exhausted)."""


class LLMResponseError(LLMError):
    """The provider returned a malformed / empty / unusable response."""


class LLMServiceError(LLMError):
    """A transient provider error persisted after retries were exhausted."""


# Exceptions worth retrying (transient).
_TRANSIENT = (
    APIConnectionError, APITimeoutError, InternalServerError, RateLimitError,
    openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError, openai.RateLimitError
)

MAX_RATE_LIMIT_WAIT: float = 65.0
"""Maximum cumulative seconds to wait across rate-limit retries for a single call.
Derived from the 60-second rolling TPM window plus 5s for clock skew and network RTT."""


# --------------------------------------------------------------------------- #
# Process-wide call throttle
#
# The supervisor graph fans out to four specialist agents in parallel, and each may
# call the LLM. On Groq's free tier (6000 tokens/minute) four simultaneous calls
# reliably trip a 429: in a real run the Security Agent's triage exhausted all four
# retries and the review silently reported zero security findings while every scanner
# had actually succeeded.
#
# This gates the *calls*, not the agents. Nodes still execute in parallel — scanners,
# AST work, and retrieval all overlap as before; only the LLM requests queue up.
# --------------------------------------------------------------------------- #
_throttle_state_lock = threading.Lock()
_call_gate: threading.Semaphore | None = None
_last_call_started_at: float = 0.0


# --------------------------------------------------------------------------- #
# Process-wide token-aware TPM rate limiter
# --------------------------------------------------------------------------- #
class TokenBucketLimiter:
    """Process-wide rolling 60-second token-per-minute (TPM) rate limiter.

    Coordinates concurrent agent requests across threads, ensuring the cumulative
    tokens (estimated before request, reconciled after completion) do not exceed
    the safe TPM budget within any 60-second window.
    """

    def __init__(
        self,
        tpm_limit: int = 8000,
        safety_margin: float = 0.8,
        window_seconds: float = 60.0,
    ) -> None:
        self.tpm_limit = tpm_limit
        self.safety_margin = safety_margin
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # History of (monotonic_timestamp, token_count)
        self._history: list[tuple[float, int]] = []
        self._cooldown_until: float = 0.0
        self._reservations: dict[str, float] = {}

    @property
    def safe_tpm(self) -> int:
        return max(100, int(self.tpm_limit * self.safety_margin))

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self._history = [(ts, tokens) for ts, tokens in self._history if ts > cutoff]
        self._reservations = {key: ts for key, ts in self._reservations.items() if ts > cutoff}

    def current_used_tokens(self, now: float | None = None) -> int:
        with self._lock:
            t = now if now is not None else time.monotonic()
            self._evict_expired(t)
            return sum(tokens for _, tokens in self._history)

    def record_cooldown(self, delay: float) -> None:
        """Record a server-mandated cooldown duration (e.g. from 429 Retry-After)."""
        with self._lock:
            target = time.monotonic() + delay
            if target > self._cooldown_until:
                self._cooldown_until = target
                logger.info("Token limiter cooldown set for %.2fs", delay)

    def record_tokens(self, token_count: int, ts: float | None = None) -> None:
        """Directly record tokens consumed (e.g. prompt tokens billed by failed attempts)."""
        with self._lock:
            t = ts if ts is not None else time.monotonic()
            self._history.append((t, token_count))

    def acquire(self, estimated_tokens: int, max_wait: float = MAX_RATE_LIMIT_WAIT, *, reservation_id: str | None = None) -> float:
        """Wait until sufficient token budget is available and reserve it atomically.

        Returns:
            The cumulative seconds waited.
        Raises:
            LLMRateLimitError if wait would exceed max_wait.
        """
        if estimated_tokens > self.safe_tpm:
            raise LLMRateLimitError("Request exceeds configured token budget; split the input.")
        start_time = time.monotonic()
        while True:
            with self._lock:
                now = time.monotonic()
                self._evict_expired(now)
                used = sum(tokens for _, tokens in self._history)

                cooldown_remaining = self._cooldown_until - now
                if cooldown_remaining > 0:
                    wait_time = cooldown_remaining
                elif used + estimated_tokens <= self.safe_tpm or not self._history:
                    # Budget is available, or history is empty (allow clean first request)
                    self._history.append((now, estimated_tokens))
                    if reservation_id:
                        self._reservations[reservation_id] = now
                    return time.monotonic() - start_time
                else:
                    # Calculate wait time based on oldest token entry
                    oldest_ts, _ = self._history[0]
                    wait_time = max(0.05, (oldest_ts + self.window_seconds) - now + 0.05)

            elapsed = time.monotonic() - start_time
            if elapsed + wait_time > max_wait:
                raise LLMRateLimitError(
                    f"Token limiter wait cap ({max_wait}s) exceeded: "
                    f"need {estimated_tokens} tokens, currently used {used}/{self.safe_tpm}"
                )

            logger.info(
                "Token limiter pacing: used %d/%d TPM, need %d; waiting %.2fs",
                used,
                self.safe_tpm,
                estimated_tokens,
                wait_time,
            )
            t_before_sleep = time.monotonic()
            measure('token_wait_seconds', wait_time)
            time.sleep(wait_time)
            t_after_sleep = time.monotonic()

            with self._lock:
                # Mark cooldown as satisfied after sleep (supports mocked time.sleep in tests)
                if self._cooldown_until > 0 and self._cooldown_until <= now + wait_time + 0.1:
                    self._cooldown_until = 0.0
                # If time.sleep was mocked (clock did not advance), evict oldest to avoid infinite loop
                if t_after_sleep <= t_before_sleep and self._history:
                    self._history.pop(0)


    def reconcile(self, reservation_ts: float | str, estimated_tokens: int, actual_tokens: int) -> None:
        """Update an estimated reservation with actual token usage reported by provider."""
        with self._lock:
            identified = isinstance(reservation_ts, str)
            reservation_ts = self._reservations.pop(reservation_ts, None) if identified else reservation_ts
            if reservation_ts is None:
                return
            for i, (ts, tokens) in enumerate(self._history):
                if (ts == reservation_ts if identified else abs(ts - reservation_ts) < 1.0) and tokens == estimated_tokens:
                    self._history[i] = (ts, actual_tokens)
                    break

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._reservations.clear()
            self._cooldown_until = 0.0


def estimate_tokens(system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> int:
    """Conservative token estimation for prompts and completions.

    Code and diffs with symbols, syntax, and punctuation have higher token density
    than plain English. On Groq's BPE tokenizer:
    - Standard English: ~4 chars per token.
    - Python code and diffs: ~2.8 - 3.2 chars per token.

    We use a conservative ratio of 3.0 chars per token for prompt text plus 20 tokens
    for framing/message overhead, plus expected completion tokens (clamped to realistic bounds).
    """
    prompt_len = len(system_prompt) + len(user_prompt)
    prompt_tokens = max(1, int(prompt_len / 3.0) + 20)
    completion_budget = max_tokens if max_tokens is not None else 4096
    return prompt_tokens + completion_budget


_token_limiter: TokenBucketLimiter | None = None


def _get_token_limiter() -> TokenBucketLimiter:
    """Lazily build the token limiter from settings (process-wide singleton)."""
    global _token_limiter
    with _throttle_state_lock:
        if _token_limiter is None:
            settings = get_settings()
            _token_limiter = TokenBucketLimiter(
                tpm_limit=settings.llm_tpm_limit,
                safety_margin=settings.llm_tpm_safety_margin,
            )
            logger.debug(
                "LLM token limiter initialised with TPM limit %d (safe %d)",
                _token_limiter.tpm_limit,
                _token_limiter.safe_tpm,
            )
        return _token_limiter


def _get_call_gate() -> threading.Semaphore:
    """Lazily build the concurrency gate from settings (process-wide singleton)."""
    global _call_gate
    with _throttle_state_lock:
        if _call_gate is None:
            size = max(1, get_settings().llm_max_concurrent_calls)
            _call_gate = threading.Semaphore(size)
            logger.debug("LLM call gate initialised with concurrency %d", size)
        return _call_gate


def reset_throttle() -> None:
    """Discard throttle and token limiter state. For tests, and after a settings change."""
    global _call_gate, _last_call_started_at, _token_limiter
    with _throttle_state_lock:
        _call_gate = None
        _last_call_started_at = 0.0
        if _token_limiter is not None:
            _token_limiter.reset()
        _token_limiter = None


@contextmanager
def _throttled_call():
    """Hold a call slot and space consecutive calls by the configured interval.

    The slot is held for the whole ``complete()`` invocation including its retries,
    so a backing-off caller does not let three others pile onto the same rate window.
    """
    global _last_call_started_at

    gate = _get_call_gate()
    gate_started = time.monotonic()
    gate.acquire()
    try:
        interval = get_settings().llm_min_call_interval_seconds
        if interval > 0:
            # Held across the sleep on purpose: waiters then measure their own gap
            # from the most recent actual start, rather than all waking together.
            with _throttle_state_lock:
                wait = interval - (time.monotonic() - _last_call_started_at)
                if wait > 0:
                    logger.debug("Throttling LLM call: sleeping %.2fs", wait)
                    time.sleep(wait)
                _last_call_started_at = time.monotonic()
        measure('gate_wait_seconds', max(0.0, time.monotonic() - gate_started))
        yield
    finally:
        gate.release()



def _extract_retry_delay(exc: Exception | str) -> float | None:
    """Extract recommended retry delay in seconds from error message, if present.

    Supports formats such as:
    - 'retry in 4.5s'
    - 'Please try again in 18.62s.'
    """
    match = re.search(r"(?:retry in|try again in) ([\d\.]+)s", str(exc), re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


class LLMClient:
    """Typed, retry-aware wrapper around the Groq/Gemini chat completions API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        backoff_base: float = 0.5,
        api_key: str | None = None,
        client: Groq | openai.OpenAI | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider.lower()
        if self.provider not in {"groq", "gemini"}:
            raise LLMConfigError("Unsupported LLM provider.")
        
        if self.provider == "gemini":
            self.model = model or settings.gemini_model
        else:
            self.model = model or settings.groq_model
            
        self.timeout = timeout if timeout is not None else settings.groq_timeout_seconds
        self.max_retries = (
            max_retries if max_retries is not None else settings.groq_max_retries
        )
        self.backoff_base = backoff_base

        if client is not None:
            self._client = client
        else:
            if self.provider == "gemini":
                resolved_key = api_key if api_key is not None else settings.gemini_api_key
                if not resolved_key:
                    raise LLMConfigError(
                        "No Gemini API key configured (set GEMINI_API_KEY or pass api_key=)."
                    )
                self._client = openai.OpenAI(
                    api_key=resolved_key,
                    timeout=self.timeout,
                    max_retries=0,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
            else:
                resolved_key = api_key if api_key is not None else settings.groq_api_key
                if not resolved_key:
                    raise LLMConfigError(
                        "No Groq API key configured (set GROQ_API_KEY or pass api_key=)."
                    )
                # Disable SDK-level retries; this wrapper owns retry/backoff.
                self._client = Groq(
                    api_key=resolved_key, timeout=self.timeout, max_retries=0
                )

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Return the model's text completion for the given prompts.

        Args:
            json_mode: if True, set response_format to force valid JSON output.

        Raises:
            LLMAuthError: authentication/authorization failed (not retried).
            LLMRateLimitError: rate limited beyond ``max_retries``.
            LLMServiceError: transient provider error beyond ``max_retries``.
            LLMResponseError: the response was malformed/empty, or the request was
                rejected as invalid.
            LLMError: any other provider error.
        """
        measure('calls')
        if json_mode:
            system_prompt += (
                "\n\nIMPORTANT: You must output ONLY valid JSON. "
                "Do not include markdown formatting like ```json or any prefix/suffix text."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        create_kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens if max_tokens is not None else 4096,
        }
        if json_mode:
            create_kwargs["response_format"] = {"type": "json_object"}

        # For open-weight reasoning models (e.g. openai/gpt-oss-120b),
        # cap reasoning effort to 'low' so reasoning tokens do not exhaust max_tokens
        # before the JSON document can be emitted.
        if "gpt-oss" in self.model:
            create_kwargs["reasoning_effort"] = "low"

        estimated_tokens = estimate_tokens(system_prompt, user_prompt, max_tokens)
        limiter = _get_token_limiter()

        with _throttled_call():
            reservation_ts = uuid.uuid4().hex
            limiter.acquire(estimated_tokens, reservation_id=reservation_ts)
            measure('estimated_reserved_tokens', estimated_tokens)
            return self._complete_with_retries(
                create_kwargs,
                estimated_tokens=estimated_tokens,
                reservation_ts=reservation_ts,
                limiter=limiter,
            )

    def _complete_with_retries(
        self,
        create_kwargs: dict,
        estimated_tokens: int = 1000,
        reservation_ts: float = 0.0,
        limiter: TokenBucketLimiter | None = None,
    ) -> str:
        """Issue the request, retrying transient failures with backoff."""
        if limiter is None:
            limiter = _get_token_limiter()

        last_transient: Exception | None = None
        cumulative_rate_limit_wait: float = 0.0
        for attempt in range(self.max_retries + 1):
            try:
                for gen_attempt in range(3):
                    try:
                        measure('requests')
                        response = self._client.chat.completions.create(**create_kwargs)
                        break
                    except (BadRequestError, openai.BadRequestError) as exc:
                        is_empty_gen = False
                        try:
                            if hasattr(exc, "body") and isinstance(exc.body, dict):
                                err_dict = exc.body.get("error", {})
                            elif hasattr(exc, "response") and hasattr(exc.response, "json"):
                                err_dict = exc.response.json().get("error", {})
                            else:
                                err_dict = {}

                            if err_dict.get("code") == "json_validate_failed" and err_dict.get("failed_generation") == "":
                                is_empty_gen = True
                        except Exception:
                            pass

                        if is_empty_gen and gen_attempt < 2:
                            # Record prompt tokens consumed by Groq for this failed request
                            # Keep the failed attempt's reservation conservatively;
                            # every retry gets a separate reservation below.

                            retry_delay = get_settings().llm_empty_generation_retry_delay
                            logger.warning(
                                "LLM empty generation hallucination (attempt %d/3); pacing and retrying in %.1fs",
                                gen_attempt + 1,
                                retry_delay,
                            )
                            if retry_delay > 0:
                                measure('retry_wait_seconds', retry_delay)
                                time.sleep(retry_delay)
                            reservation_ts = uuid.uuid4().hex
                            limiter.acquire(estimated_tokens, reservation_id=reservation_ts)
                            measure('estimated_reserved_tokens', estimated_tokens)
                            measure('retries')
                            continue

                        # If not an empty generation, or retries exhausted, raise it up
                        raise LLMResponseError(f"request rejected as invalid: {exc}") from exc

                actual_tokens = self._extract_total_tokens(response)
                if actual_tokens is not None:
                    measure('responses_with_usage')
                    measure('reported_total_tokens', actual_tokens)
                    limiter.reconcile(reservation_ts, estimated_tokens, actual_tokens)
                return self._extract_content(response)
            except (AuthenticationError, PermissionDeniedError, openai.AuthenticationError, openai.PermissionDeniedError) as exc:
                raise LLMAuthError(f"authentication failed: {exc}") from exc
            except _TRANSIENT as exc:
                last_transient = exc
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2**attempt)

                    if isinstance(exc, (RateLimitError, openai.RateLimitError)):
                        try:
                            if hasattr(exc, "response") and exc.response is not None:
                                retry_after = exc.response.headers.get("retry-after")
                                if retry_after is not None:
                                    delay = max(delay, float(retry_after) + 1.0)
                        except Exception:
                            pass
                        parsed_delay = _extract_retry_delay(exc)
                        if parsed_delay is not None:
                            delay = max(delay, parsed_delay + 1.0)

                        limiter.record_cooldown(delay)

                        remaining_wait = MAX_RATE_LIMIT_WAIT - cumulative_rate_limit_wait
                        if remaining_wait <= 0:
                            raise LLMRateLimitError(
                                f"rate limit wait cap ({MAX_RATE_LIMIT_WAIT}s) exceeded: {exc}"
                            ) from exc
                        delay = min(delay, remaining_wait)
                        cumulative_rate_limit_wait += delay
                    else:
                        delay = min(delay, 30.0)

                    logger.warning(
                        "LLM transient error (attempt %d/%d): %s; retrying in %.2fs",
                        attempt + 1,
                        self.max_retries + 1,
                        exc,
                        delay,
                    )
                    measure('retry_wait_seconds', delay)
                    time.sleep(delay)
                    reservation_ts = uuid.uuid4().hex
                    limiter.acquire(estimated_tokens, reservation_id=reservation_ts)
                    measure('estimated_reserved_tokens', estimated_tokens)
                    measure('retries')
                    continue
                # Retries exhausted.
                if isinstance(exc, (RateLimitError, openai.RateLimitError)):
                    raise LLMRateLimitError(
                        f"rate limited after {self.max_retries + 1} attempts: {exc}"
                    ) from exc
                raise LLMServiceError(
                    f"transient error after {self.max_retries + 1} attempts: {exc}"
                ) from exc
            except (APIError, openai.APIError) as exc:  # any other API error
                raise LLMError(f"LLM provider error: {exc}") from exc

        # Unreachable, but keeps the type checker satisfied.
        raise LLMServiceError(f"exhausted retries: {last_transient}")

    @staticmethod
    def _extract_total_tokens(response: object) -> int | None:
        """Pull the total token usage out of a chat completion response if present."""
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                total = getattr(usage, "total_tokens", None)
                if isinstance(total, int) and total > 0:
                    return total
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_content(response: object) -> str:
        """Pull the assistant message text out of a chat completion response."""
        try:
            choices = response.choices  # type: ignore[attr-defined]
            content = choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"malformed response structure: {exc}"
            ) from exc

        if not content or not str(content).strip():
            raise LLMResponseError("provider returned an empty completion")
        return str(content)
