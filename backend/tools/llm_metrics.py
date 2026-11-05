"""Per-agent LLM measurements. Logs contain counts and identifiers, never prompts."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import time

logger = logging.getLogger(__name__)
_current: ContextVar[dict | None] = ContextVar('agent_llm_metrics', default=None)


_observer: ContextVar = ContextVar("provider_wait_observer", default=None)


@contextmanager
def provider_wait(category: str):
    """Measure actual elapsed wait and optionally emit a bounded progress pair."""
    observer = _observer.get()
    started = time.monotonic()
    if observer:
        observer(category, "started")
    try:
        yield
    finally:
        measure(f"{category}_wait_seconds", max(0.0, time.monotonic() - started))
        if observer:
            observer(category, "ok")


def measure(field: str, value: int | float = 1) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics[field] += value


@contextmanager
def agent_metrics(agent: str, *, repo: str | None = None, pr: int | None = None, revision: str | None = None, progress=None):
    metrics = dict(agent=agent, repo=repo, pr=pr, revision=revision,
                   calls=0, requests=0, retries=0, responses_with_usage=0,
                   reported_total_tokens=0, estimated_reserved_tokens=0,
                   gate_wait_seconds=0.0, token_wait_seconds=0.0,
                   retry_wait_seconds=0.0, cooldown_wait_seconds=0.0, priority_wait_seconds=0.0, duration_seconds=0.0)
    counts: dict[str, int] = {}

    def observe(category, status):
        count = counts.get(category, 0)
        if count < 40:
            progress(f"provider_{category}", status, agent)
            counts[category] = count + 1

    observer_token = _observer.set(observe if progress else None)
    token = _current.set(metrics)
    started = time.monotonic()
    try:
        yield metrics
    finally:
        metrics['duration_seconds'] = max(0.0, time.monotonic() - started)
        _current.reset(token)
        _observer.reset(observer_token)
        logger.info('agent_llm_metrics %s', json.dumps(metrics, sort_keys=True))
