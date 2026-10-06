"""Health check endpoints: liveness and readiness."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, str]:
    """Liveness probe. Always 200 while the process is running."""
    return {"status": "alive"}


@router.get("/ready")
def readiness() -> JSONResponse:
    """Readiness probe.

    Checks that dependencies (PostgreSQL, ChromaDB) are reachable. Degrades
    gracefully: if a dependency is unavailable the endpoint reports ``not_ready``
    with per-dependency detail and a 503 status rather than raising.
    """
    settings = get_settings()
    checks: dict[str, str] = {}

    # --- PostgreSQL ---
    try:
        from sqlalchemy import text

        from backend.db.database import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            from pathlib import Path
            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "db" / "migrations"))
            expected = ScriptDirectory.from_config(config).get_current_head()
            if conn.execute(text("SELECT version_num FROM alembic_version")).scalar() != expected:
                raise RuntimeError("Database migration required.")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.warning("Readiness: database check failed: %s", exc)
        checks["database"] = "unavailable"

    # --- ChromaDB (local persistent client) ---
    try:
        import chromadb

        from backend.rag.ingest import resolve_active_collection
        collection = chromadb.PersistentClient(path=settings.chroma_persist_dir).get_collection(resolve_active_collection())
        if collection.count() == 0:
            raise RuntimeError("Default standards are empty.")
        checks["chromadb"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.warning("Readiness: chromadb check failed: %s", exc)
        checks["chromadb"] = "unavailable"

    try:
        from datetime import datetime, timezone, timedelta
        with engine.connect() as conn:
            last = conn.execute(text("SELECT updated_at FROM worker_heartbeat WHERE id=1")).scalar()
        checks["worker"] = "ok" if last and last >= datetime.now(timezone.utc) - timedelta(seconds=90) else "unavailable"
    except Exception:
        checks["worker"] = "unavailable"
    try:
        from cryptography.fernet import Fernet
        Fernet(settings.require("token_encryption_key").encode())
        settings.require("session_secret")
        settings.require("github_webhook_secret")
        checks["configuration"] = "ok"
    except (ValueError, RuntimeError):
        checks["configuration"] = "unavailable"
    ready = all(v == "ok" for v in checks.values())
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
