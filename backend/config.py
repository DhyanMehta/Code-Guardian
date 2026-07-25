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
_ENV_FILES = (_PROJECT_ROOT / ".env", _BACKEND_DIR / ".env")


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
    github_token: str = ""
    github_webhook_secret: str = ""

    # LLM configuration (Groq). Model must be a currently-supported Groq model id;
    # verify against Groq's model catalogue if changed.
    groq_model: str = "llama-3.1-8b-instant"
    groq_timeout_seconds: int = 30
    groq_max_retries: int = 3

    # Infrastructure.
    database_url: str = (
        "postgresql+psycopg2://guardian:guardian@localhost:5432/codeguardian"
    )
    chroma_persist_dir: str = "./chroma_db"

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
