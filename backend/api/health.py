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
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.warning("Readiness: database check failed: %s", exc)
        checks["database"] = "unavailable"

    # --- ChromaDB (local persistent client) ---
    try:
        import chromadb

        chromadb.PersistentClient(path=settings.chroma_persist_dir).heartbeat()
        checks["chromadb"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must never raise
        logger.warning("Readiness: chromadb check failed: %s", exc)
        checks["chromadb"] = "unavailable"

    ready = all(v == "ok" for v in checks.values())
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
