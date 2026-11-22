"""Cooperative time budget for an agent's provider operations."""
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from threading import Event, Lock

deadline: ContextVar[float | None] = ContextVar("review_deadline", default=None)


required_analysis_done: ContextVar[Event | None] = ContextVar("required_analysis_done", default=None)


class ProviderRequestBudget:
    """One shared send allowance for all agents in one worker attempt."""

    def __init__(self, limit: int):
        self._remaining = limit
        self._lock = Lock()

    def available(self) -> bool:
        with self._lock:
            return self._remaining > 0

    def claim(self) -> bool:
        with self._lock:
            if self._remaining == 0:
                return False
            self._remaining -= 1
            return True


provider_request_budget: ContextVar[ProviderRequestBudget | None] = ContextVar(
    "provider_request_budget", default=None,
)


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
