"""CodeGuardian AI — FastAPI application entrypoint.

Run locally (with the backend/venv active):

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import auth, autofix, health, installations, metrics, reviews, webhooks
from backend.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hooks."""
    logger.info("CodeGuardian AI backend starting up.")
    yield
    logger.info("CodeGuardian AI backend shutting down.")


app = FastAPI(
    title="CodeGuardian AI",
    description=(
        "Autonomous multi-agent code review and DevSecOps platform. "
        "Session 8: GitHub App multi-tenant reviews, OAuth, and installations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The dashboard is served from a separate dev-server origin, so the browser needs
# CORS headers to call this API at all. An explicit origin list rather than "*":
# these endpoints push branches and record human approvals, so an arbitrary page
# must not be able to drive them.
_cors_origins = get_settings().cors_origins()
logger.info("CORS allowed origins: %s", _cors_origins or "(none configured)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(reviews.router)
app.include_router(metrics.router)
app.include_router(autofix.router)
app.include_router(auth.router)
app.include_router(installations.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Basic service banner."""
    return {"service": "CodeGuardian AI", "version": app.version, "docs": "/docs"}
