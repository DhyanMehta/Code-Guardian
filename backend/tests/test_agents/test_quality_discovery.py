"""Independent discovery regressions from real PR #1, with isolated provider stubs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.quality_agent import QualityAgent, canonical_rule
from backend.rag.retriever import RetrievedPassage, RetrievalResult
from backend.services.agent_checkpoints import quality_checkpoints
from backend.tools.llm_client import LLMAuthError, LLMBudgetError, LLMError


FIXTURES = Path(__file__).parents[1] / "fixtures"
PINNED_SHA = "c1c01ffe775bc50061790a4e4e34ec953a6ee90f"
LENGTH_RULE = (
    "A single function or method should not exceed **40 lines** of logic "
    "(excluding blank lines, decorators, and the docstring)."
)
EXPECTED_LENGTHS = {
    "membership_breakdown": 42,
    "event_attendance": 49,
    "test_analytics_counts_correct": 226,
}


class Provider:
    """Boundary-only stub; no real API credential or request is used."""

    def __init__(self, response=None):
        self.response = response or {"findings": []}
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return json.dumps(self.response)


def passages(*rules):
    return RetrievalResult(passages=[
        RetrievedPassage(rule, "python_coding_standards.md", 0.1, str(i))
        for i, rule in enumerate(rules)
    ])


def added_diff(path, source):
    lines = source.splitlines()
    return (f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n"
            f"@@ -0,0 +1,{len(lines)} @@\n" +
            "\n".join("+" + line for line in lines) + "\n")


@pytest.fixture
def pinned_workspace(tmp_path):
    service = json.loads((FIXTURES / "odooxldce_quality.json").read_text(encoding="utf-8"))
    test = json.loads((FIXTURES / "odooxldce_test_analytics_function.json").read_text(encoding="utf-8"))
    assert service["commit"] == test["commit"] == PINNED_SHA
    assert set(service["functions"]) == {
        "club_summary", "membership_breakdown", "event_attendance", "revenue_by_type"
    }
    sources = {
        service["file"]: "from __future__ import annotations\n\n" +
        "\n\n".join(service["functions"].values()) + "\n",
        test["file"]: "from __future__ import annotations\n\n" + test["source"] + "\n",
    }
    for name, source in sources.items():
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")
    return tmp_path, sources, "".join(added_diff(name, source) for name, source in sources.items())


def measured_lengths(result):
    return {f.symbol: f for f in result.findings
            if canonical_rule(f.rule_violated) == "maximum_function_length"
            and f.evidence_kind == "verified"}


def assert_pinned_lengths(result):
    verified = measured_lengths(result)
    assert set(verified) == set(EXPECTED_LENGTHS)
    for symbol, length in EXPECTED_LENGTHS.items():
        assert f"{length} " in verified[symbol].explanation
        assert "40" in verified[symbol].explanation
        assert verified[symbol].cited_passage == LENGTH_RULE
    assert "club_summary" not in verified
    assert "revenue_by_type" not in verified


@pytest.mark.parametrize("provider_result", [
    {"findings": []},
    LLMError("Provider timeout"),
    LLMBudgetError("Provider token budget exhausted"),
    LLMAuthError("Provider unavailable"),
], ids=["empty", "timeout", "budget", "auth"])
def test_pinned_measurable_violations_do_not_depend_on_model(pinned_workspace, provider_result):
    root, sources, diff = pinned_workspace
    agent = QualityAgent(llm_client=Provider(provider_result), retriever_fn=lambda *a, **k: passages(LENGTH_RULE))
    result = agent.run(diff, list(sources), str(root))
    assert_pinned_lengths(result)


def test_incomplete_and_contradictory_proposals_cannot_hide_or_conflict(pinned_workspace):
    root, sources, diff = pinned_workspace
    service_file = next(name for name in sources if "/services/" in name)
    proposals = [
        {"symbol": "membership_breakdown", "rule_violated": "function_too_long", "explanation": "This function has 100 lines and exceeds 40."},
        {"symbol": "club_summary", "rule_violated": "Maximum Function Length", "explanation": "This function exceeds the 40-line limit."},
        {"symbol": "revenue_by_type", "rule_violated": "function_length", "explanation": "This function exceeds the 40-line limit."},
    ]
    for proposal in proposals:
        proposal.update(passage_index=0, file_path=service_file, severity="high")
    agent = QualityAgent(llm_client=Provider({"findings": proposals}),
                         retriever_fn=lambda *a, **k: passages(LENGTH_RULE))
    result = agent.run(diff, list(sources), str(root))
    assert_pinned_lengths(result)
    keys = [(f.file_path, f.symbol, canonical_rule(f.rule_violated)) for f in result.findings]
    assert len(keys) == len(set(keys))
    assert not any("100 lines" in f.explanation for f in result.findings)


def test_discovery_requires_applicable_retrieved_versioned_python_rule(pinned_workspace):
    root, sources, diff = pinned_workspace
    calls = []

    def retrieve(query, **kwargs):
        calls.append(kwargs)
        return passages(LENGTH_RULE)

    agent = QualityAgent(llm_client=Provider(), retriever_fn=retrieve, standards_version="frozen-team-v7")
    assert_pinned_lengths(agent.run(diff, list(sources), str(root)))
    assert calls and all(call["collection_name"] == "frozen-team-v7" for call in calls)
    for unrelated in (RetrievalResult(error="No standards available"), passages("Use meaningful names."),
                      RetrievalResult(passages=[RetrievedPassage(
                          "JavaScript functions should not exceed 2 lines of logic.", "javascript.md", 0.1, "js")])):
        agent = QualityAgent(llm_client=Provider(), retriever_fn=lambda *a, value=unrelated, **k: value)
        assert not measured_lengths(agent.run(diff, list(sources), str(root)))


def test_discovery_limits_findings_to_changed_functions(tmp_path):
    source = "def untouched():\n    a = 1\n    b = 2\n    return a+b\n\ndef changed():\n    return 1\n"
    (tmp_path / "app.py").write_text(source)
    diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -7 +7 @@\n-    return 0\n+    return 1\n"
    agent = QualityAgent(llm_client=Provider(), retriever_fn=lambda *a, **k: passages(
        "A single function should not exceed **2 lines** of logic (excluding blank lines, decorators, and the docstring)."))
    assert not measured_lengths(agent.run(diff, ["app.py"], str(tmp_path)))


def test_supported_parameter_and_future_import_rules_are_discovered(tmp_path):
    source = ("def too_many(a, b, /, c, d, e, f, *, optional=1):\n    return a\n\n"
              "def allowed(a, b, c, d, e, *, optional=1):\n    return a\n\n"
              "class Example:\n    def method(self, a, b, c, d, e, *, optional=1):\n        return a\n")
    (tmp_path / "app.py").write_text(source)
    agent = QualityAgent(llm_client=Provider(), retriever_fn=lambda *a, **k: passages(
        "Functions should accept **5 or fewer positional parameters**.",
        "Use `from __future__ import annotations` at the top of every Python module."))
    result = agent.run(added_diff("app.py", source), ["app.py"], str(tmp_path))
    keys = {(canonical_rule(f.rule_violated), f.symbol) for f in result.findings if f.evidence_kind == "verified"}
    assert keys == {("maximum_positional_parameters", "too_many"), ("future_annotations_import", "<module>")}


def test_present_future_import_and_keyword_only_parameters_are_not_violations(tmp_path):
    source = "from __future__ import annotations\n\ndef allowed(a, *, b, c, d, e, f, g):\n    return a\n"
    (tmp_path / "app.py").write_text(source)
    agent = QualityAgent(llm_client=Provider(), retriever_fn=lambda *a, **k: passages(
        "Functions should accept **5 or fewer positional parameters**.",
        "Use `from __future__ import annotations` at the top of every Python module."))
    assert not agent.run(added_diff("app.py", source), ["app.py"], str(tmp_path)).findings


def test_checkpoint_replay_preserves_discovery_without_more_provider_calls(pinned_workspace):
    root, sources, diff = pinned_workspace

    class Checkpoints:
        def __init__(self):
            self.saved = {}
        def quality_batch(self, batch):
            saved = self.saved
            class Batch:
                def load(self, name):
                    return saved.get((batch, name))
                def save(self, name, value):
                    saved[(batch, name)] = value
            return Batch()

    checkpoints = Checkpoints()
    provider = Provider()
    agent = QualityAgent(llm_client=provider, retriever_fn=lambda *a, **k: passages(LENGTH_RULE))
    token = quality_checkpoints.set(checkpoints)
    try:
        first = agent.run(diff, list(sources), str(root))
        count = provider.calls
        second = agent.run(diff, list(sources), str(root))
    finally:
        quality_checkpoints.reset(token)
    assert_pinned_lengths(first)
    assert_pinned_lengths(second)
    assert provider.calls == count

