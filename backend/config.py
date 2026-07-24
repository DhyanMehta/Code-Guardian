"""Application configuration.

Loads settings from environment variables (and a local ``.env`` file when present)
using pydantic-settings. Secrets are never hardcoded. Fields default to empty strings
so the app and test suite can import without a populated ``.env``; components that
actually need a secret must validate its presence at call time (fail fast, no silent
fallbacks). See ``RULES.md``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Secrets (empty by default; validated where used).
    groq_api_key: str = ""
    github_token: str = ""
    github_webhook_secret: str = ""

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
