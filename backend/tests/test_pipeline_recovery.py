from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import pytest

from backend.agents import supervisor
from backend.tools import llm_client
from backend.tools.review_budget import deadline


def test_supervisor_reuses_completed_outputs(monkeypatch):
    class Checkpoints:
        saved = {}

        def save(self, agent, result):
            self.saved[agent] = result

        def load(self, agent):
            return self.saved.get(agent)

    checkpoints = Checkpoints()
    for agent in ("security", "test_gap", "documentation"):
        checkpoints.save(agent, {"agent_outcomes": {agent: "ok"},
                                 "agent_notes": {agent: ["saved result"]}})

        def unexpected(_state):
            pytest.fail("Completed agent was dispatched again")

        monkeypatch.setattr(supervisor, f"_run_{agent}_node", unexpected)
    monkeypatch.setattr(supervisor, "_run_quality_node",
                        lambda _: {"agent_outcomes": {"quality": "degraded"}})
    graph = supervisor.build_supervisor_graph(checkpoints=checkpoints)
    result = graph.invoke({})
    assert result["agent_outcomes"] == {
        "security": "ok", "test_gap": "ok", "documentation": "ok", "quality": "degraded"
    }
    assert result["agent_notes"]["security"] == ["saved result"]


def test_provider_slot_wait_respects_agent_deadline(monkeypatch):
    from threading import Semaphore

    gate = Semaphore(0)
    monkeypatch.setattr(llm_client, "_get_call_gate", lambda: gate)

    def attempt():
        token = deadline.set(monotonic() + 0.01)
        try:
            with pytest.raises(llm_client.LLMBudgetError, match="provider slot"):
                with llm_client._throttled_call():
                    pytest.fail("Provider slot was unavailable")
        finally:
            deadline.reset(token)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(attempt)
        try:
            future.result(timeout=1)
        finally:
            gate.release()

def test_quality_skips_unsupported_diff_before_retrieval():
    from backend.agents.quality_agent import QualityAgent

    def unexpected(*args, **kwargs):
        pytest.fail("Unsupported TypeScript reached standards retrieval")

    diff = "diff --git a/App.tsx b/App.tsx\n--- a/App.tsx\n+++ b/App.tsx\n@@ -0,0 +1 @@\n+export const value = 1;\n"
    result = QualityAgent(retriever_fn=unexpected).run(diff, ["App.tsx"])
    assert result.outcome.value == "degraded"
    assert result.notes == ["Excluded from Quality: App.tsx"]

def test_optional_drafts_do_not_use_an_expired_review_budget():
    from threading import Event

    from backend.tools.review_budget import optional_draft_budget, required_analysis_done

    required = Event()
    priority = required_analysis_done.set(required)
    expires = deadline.set(monotonic() - 1)
    try:
        with optional_draft_budget() as allowed:
            assert not allowed
    finally:
        deadline.reset(expires)
        required_analysis_done.reset(priority)

def test_large_token_reservation_cannot_be_overtaken_during_quota_wait(monkeypatch):
    from threading import Event

    limiter = llm_client.TokenBucketLimiter()
    entered = Event()
    unblock = Event()
    order = []

    def reserve(tokens, *, reservation_id):
        order.append(tokens)
        if tokens == 6000:
            entered.set()
            assert unblock.wait(2)

    monkeypatch.setattr(limiter, "acquire", reserve)
    with ThreadPoolExecutor(max_workers=2) as executor:
        big = executor.submit(limiter.reserve_request, 6000, "big")
        try:
            assert entered.wait(2)
            small = executor.submit(limiter.reserve_request, 400, "small")
            assert order == [6000]
        finally:
            unblock.set()
        big.result(timeout=2)
        small.result(timeout=2)
    assert order == [6000, 400]

def test_token_wait_limited_by_review_budget_reports_budget_exhaustion():
    limiter = llm_client.TokenBucketLimiter(tpm_limit=1000, safety_margin=1)
    limiter.record_tokens(1000)
    token = deadline.set(monotonic() + 0.5)
    try:
        with pytest.raises(llm_client.LLMBudgetError, match="Token wait"):
            limiter.reserve_request(500, "next")
    finally:
        deadline.reset(token)
