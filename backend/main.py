"""CodeGuardian AI — FastAPI application entrypoint.

Run locally (with the venv active):

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import health, reviews, webhooks

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
        "Session 1: scaffold + GitHub webhook receiver."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(reviews.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Basic service banner."""
    return {"service": "CodeGuardian AI", "version": app.version, "docs": "/docs"}
