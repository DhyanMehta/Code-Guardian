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
import time

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
_TRANSIENT = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


class LLMClient:
    """Typed, retry-aware wrapper around the Groq chat completions API."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        backoff_base: float = 0.5,
        api_key: str | None = None,
        client: Groq | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.groq_model
        self.timeout = timeout if timeout is not None else settings.groq_timeout_seconds
        self.max_retries = (
            max_retries if max_retries is not None else settings.groq_max_retries
        )
        self.backoff_base = backoff_base

        if client is not None:
            self._client = client
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
    ) -> str:
        """Return the model's text completion for the given prompts.

        Raises:
            LLMAuthError: authentication/authorization failed (not retried).
            LLMRateLimitError: rate limited beyond ``max_retries``.
            LLMServiceError: transient provider error beyond ``max_retries``.
            LLMResponseError: the response was malformed/empty, or the request was
                rejected as invalid.
            LLMError: any other provider error.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_transient: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return self._extract_content(response)
            except (AuthenticationError, PermissionDeniedError) as exc:
                raise LLMAuthError(f"authentication failed: {exc}") from exc
            except BadRequestError as exc:
                raise LLMResponseError(f"request rejected as invalid: {exc}") from exc
            except _TRANSIENT as exc:
                last_transient = exc
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2**attempt)
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
                if isinstance(exc, RateLimitError):
                    raise LLMRateLimitError(
                        f"rate limited after {self.max_retries + 1} attempts: {exc}"
                    ) from exc
                raise LLMServiceError(
                    f"transient error after {self.max_retries + 1} attempts: {exc}"
                ) from exc
            except APIError as exc:  # any other Groq API error
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
        if not content or not str(content).strip():
            raise LLMResponseError("provider returned an empty completion")
        return str(content)
