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
    """Discard throttle state. For tests, and after a settings change."""
    global _call_gate, _last_call_started_at
    with _throttle_state_lock:
        _call_gate = None
        _last_call_started_at = 0.0


@contextmanager
def _throttled_call():
    """Hold a call slot and space consecutive calls by the configured interval.

    The slot is held for the whole ``complete()`` invocation including its retries,
    so a backing-off caller does not let three others pile onto the same rate window.
    """
    global _last_call_started_at

    gate = _get_call_gate()
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
        yield
    finally:
        gate.release()


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

        with _throttled_call():
            return self._complete_with_retries(create_kwargs)

    def _complete_with_retries(self, create_kwargs: dict) -> str:
        """Issue the request, retrying transient failures with backoff."""
        last_transient: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                for gen_attempt in range(3):
                    try:
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
                            logger.warning(
                                "LLM empty generation hallucination (attempt %d/3); retrying in 2.0s",
                                gen_attempt + 1,
                            )
                            time.sleep(2.0)
                            continue
                        
                        # If not an empty generation, or retries exhausted, raise it up
                        raise LLMResponseError(f"request rejected as invalid: {exc}") from exc
                        
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
                                    delay = max(delay, float(retry_after))
                        except Exception:
                            pass
                        match = re.search(r"retry in ([\d\.]+)s", str(exc))
                        if match:
                            try:
                                delay = max(delay, float(match.group(1)))
                            except Exception:
                                pass
                                
                    delay = min(delay, 30.0)
                    
                    logger.warning(
                        "LLM transient error (attempt %d/%d): %s; retrying in %.2fs",
                        attempt + 1,
                        self.max_retries + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
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
    def _extract_content(response: object) -> str:
        """Pull the assistant message text out of a chat completion response."""
        try:
            choices = response.choices  # type: ignore[attr-defined]
            content = choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"malformed response structure: {exc}"
            ) from exc
            
        try:
            tokens = response.usage.total_tokens
            with open("llm_tokens.log", "a") as f:
                f.write(f"{tokens}\n")
        except Exception:
            pass

        if not content or not str(content).strip():
            with open("llm_debug_empty.txt", "w") as f:
                f.write("RESPONSE OBJECT:\n")
                f.write(repr(response))
            raise LLMResponseError("provider returned an empty completion")
        return str(content)
