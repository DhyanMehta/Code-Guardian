"""Cooperative time budget for an agent's provider operations."""
from contextvars import ContextVar
from time import monotonic

deadline: ContextVar[float | None] = ContextVar("review_deadline", default=None)


def remaining() -> float | None:
    end = deadline.get()
    return None if end is None else max(0.0, end - monotonic())
