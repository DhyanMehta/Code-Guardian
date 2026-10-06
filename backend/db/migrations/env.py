"""Alembic migration environment for CodeGuardian AI.

The database URL is resolved at runtime from the application settings
(``DATABASE_URL`` env / ``.env``) rather than being hardcoded in ``alembic.ini``.
An offline SQLite fallback (``ALEMBIC_URL``) can be supplied to generate/render
migrations without a live PostgreSQL server.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import the application's models so their metadata is available for autogenerate.
from backend.config import get_settings
from backend.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve the database URL.

    Priority: explicit ``ALEMBIC_URL`` override (useful for offline generation) >
    application ``DATABASE_URL`` setting.
    """
    return os.getenv("ALEMBIC_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DBAPI connection)."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect via an Engine)."""
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
