"""Application configuration.

Loads settings from environment variables (and a local ``.env`` file when present)
using pydantic-settings. Secrets are never hardcoded. Fields default to empty strings
so the app and test suite can import without a populated ``.env``; components that
actually need a secret must validate its presence at call time (fail fast, no silent
fallbacks). See ``RULES.md``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env file(s) to absolute paths so secrets load regardless of the
# current working directory (uvicorn/pytest/alembic are all launched from the
# project root, but the .env may live either at the project root or inside the
# self-contained ``backend/`` package). Files are listed lowest-to-highest
# precedence; a value in a later file overrides an earlier one.
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (_PROJECT_ROOT / ".env",)


class Settings(BaseSettings):
    """Typed application settings sourced from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Secrets (empty by default; validated where used).
    groq_api_key: str = ""
    github_token: str = ""  # Legacy PAT — kept for backward compat during App migration.
    github_webhook_secret: str = ""

    # GitHub App (replaces the single PAT for all API calls).
    github_app_id: int = 0
    github_app_private_key_path: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_slug: str = ""

    # Dashboard session JWTs (HS256).
    session_secret: str = ""
    token_encryption_key: str = ""
    legacy_pat_enabled: bool = False
    review_timeout_seconds: int = 900
    worker_poll_seconds: float = 2.0
    max_review_attempts: int = 2

    # LLM configuration. Default to Groq.
    llm_provider: str = "groq"

    # Gemini configuration.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # Groq configuration. Model must be a currently-supported Groq model id;
    # verify against Groq's model catalogue if changed.
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: int = 30
    groq_max_retries: int = 3

    # LLM call pacing. The supervisor fans out to four agents in parallel, so
    # without throttling they hit Groq simultaneously and blow the free tier's
    # tokens-per-minute cap (observed: the Security Agent's triage lost the race,
    # exhausted its retries on 429, and reported zero findings). These throttle the
    # *calls*, not the agent scheduling — the graph still runs nodes in parallel.
    llm_max_concurrent_calls: int = 1
    llm_min_call_interval_seconds: float = 1.5

    # LLM token rate pacing (TPM limiter). Groq on-demand tier enforces an 8,000 TPM
    # cap across a rolling 60-second window. The token limiter tracks estimated and
    # actual token consumption, holding requests before dispatch if the remaining
    # budget within the last 60 seconds is insufficient.
    llm_tpm_limit: int = 8000
    llm_tpm_safety_margin: float = 0.8
    llm_empty_generation_retry_delay: float = 2.0

    # Infrastructure.
    database_url: str = (
        "postgresql+psycopg2://guardian:guardian@localhost:5432/codeguardian"
    )
    chroma_persist_dir: str = str(_PROJECT_ROOT / "chroma_db")

    # Dashboard. Comma-separated origins allowed to call the API from a browser.
    # Typed as a plain string, not list[str], because pydantic-settings would then
    # try to JSON-decode the env value and require `["http://..."]` in .env.
    # Never widened to "*": these endpoints create branches and record approvals.
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Session cookie ``Secure`` flag.  Defaults to ``True`` so production cookies
    # are only sent over HTTPS.  Set ``COOKIE_SECURE=false`` in ``.env`` for local
    # HTTP-only development (the browser will refuse to store a Secure cookie
    # received over plain ``http://localhost``).
    cookie_secure: bool = True

    def cors_origins(self) -> list[str]:
        """Parse ``cors_allowed_origins`` into a list of origins."""
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    def require(self, field_name: str) -> str:
        """Return a required setting's value or raise if it is unset/empty.

        Use this at the point of use for secrets so failures are explicit rather
        than silent.
        """
        value = getattr(self, field_name, "")
        if not value:
            raise RuntimeError(
                f"Required setting '{field_name}' is not configured. "
                f"Set it in your environment or .env file (see .env.example)."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
