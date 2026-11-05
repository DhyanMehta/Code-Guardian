"""Cooperative time budget for an agent's provider operations."""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from threading import Event

deadline: ContextVar[float | None] = ContextVar("review_deadline", default=None)


required_analysis_done: ContextVar[Event | None] = ContextVar("required_analysis_done", default=None)


@contextmanager
def optional_draft_budget():
    """Wait for essential analysis, then give drafting a small separate budget."""
    required = required_analysis_done.get()
    if required is None:
        yield True
        return
    from backend.tools.llm_metrics import provider_wait

    left = remaining()
    if left is None or left <= 0:
        yield False
        return
    if not required.is_set():
        with provider_wait("priority"):
            ready = required.wait(timeout=left)
        if not ready:
            yield False
            return
    end = deadline.get()
    assert end is not None
    token = deadline.set(min(end, monotonic() + 60))
    try:
        yield bool(remaining())
    finally:
        deadline.reset(token)


def remaining() -> float | None:
    end = deadline.get()
    return None if end is None else max(0.0, end - monotonic())
