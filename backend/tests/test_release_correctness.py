"""Regressions discovered during the isolated deployment audit."""
import pytest

from backend.agents import supervisor
from backend.agents.frontend_analysis import parse_sources
from backend.agents.state import PRMetadata


def test_frontend_failure_does_not_become_quality_success(monkeypatch):
    for name in ("security", "test_gap", "documentation"):
        monkeypatch.setattr(supervisor, f"_run_{name}_node", lambda _, name=name: {
            "agent_outcomes": {name: "ok"}, "agent_notes": {name: []}})
    monkeypatch.setattr(supervisor, "_run_quality_node", lambda _: {
        "agent_outcomes": {"quality": "degraded"}, "agent_notes": {"quality": []},
        "quality_result": {"quality": {"findings": [], "outcome": "degraded",
            "failure_reason": "Python Quality batches exclude non-Python and generated/vendor files; see structured coverage."}}})
    def broken(name, state, result):
        if name == "quality":
            raise ValueError("Actual frontend parser failure")
    monkeypatch.setattr("backend.agents.frontend_analysis.extend_result", broken)
    result = supervisor.build_supervisor_graph().invoke({"pr": PRMetadata("owner/repo", 1, changed_files=["view.tsx"])})
    assert result["agent_outcomes"]["quality"] == "degraded"
    assert result["agent_coverage"]["quality"]["status"] == "partial"


def test_shadowed_import_is_not_a_test_reference():
    parsed = parse_sources([{"file": "view.test.ts", "source":
        "import { View } from './view';\nfunction helper(View: () => void) { View(); }"}])[0]
    assert "View" not in parsed["references"]


def test_missing_future_import_claim_is_rejected_when_present(tmp_path):
    from backend.agents.quality_agent import QualityAgent
    file = tmp_path / "app.py"
    file.write_text("from __future__ import annotations\n")
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "future_import_missing"},
        "All Python modules must include from __future__ import annotations.", "<module>", file)
    assert kind == "contradicted"
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "MissingFutureAnnotationsImport"},
        "All Python modules must include from __future__ import annotations.", "<module>", file)
    assert kind == "contradicted"


def test_alphabetical_local_import_example_is_not_a_violation(tmp_path):
    from backend.agents.quality_agent import QualityAgent
    file = tmp_path / "app.py"
    file.write_text("from app.db.session import get_db\nfrom app.dependencies.auth import AuthContext\n")
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "ImportSorting",
        "explanation": "Local imports are not sorted alphabetically; 'app.db.session' appears before 'app.dependencies.auth'."},
        "Sort imports alphabetically within each group.", "<module>", file)
    assert kind == "contradicted"
    (tmp_path / "app").mkdir()
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "import_ordering",
        "explanation": "Imports are not alphabetically sorted within the local/project group."},
        "Sort imports alphabetically within each group.", "<module>", file)
    assert kind == "contradicted"


def test_partial_coverage_warns_even_when_execution_is_ok():
    from dataclasses import asdict
    from backend.services.agent_coverage import Coverage
    from backend.services.report_builder import AgentStatus, AggregatedReport, format_pr_comment
    from backend.agents.state import AgentOutcome
    coverage = Coverage(execution="completed", status="partial", findings=21)
    report = AggregatedReport(agent_statuses=[AgentStatus("quality", AgentOutcome.OK, 21, coverage=asdict(coverage))])
    text = format_pr_comment(report, 1)
    assert "1/1 agent executions completed" in text
    assert "Incomplete coverage" in text
    assert "completed with limitations" in text
    assert "| 21 |" in text


def test_security_includes_json_for_secret_scanning():
    from backend.services.agent_coverage import classify
    assert classify(["config.json", "api.d.ts"], "security").eligible_files == ["api.d.ts", "config.json"]


def test_quality_batch_observation_is_counted_once(tmp_path, monkeypatch):
    from backend.agents.quality_agent import QualityAgent
    from backend.rag.retriever import RetrievalResult, RetrievedPassage
    from backend.services.agent_coverage import Coverage, current
    from backend.services.agent_checkpoints import quality_checkpoints
    class Checkpoint:
        saved = None
        def quality_batch(self, batch):
            return self
        def load(self, name):
            return self.saved
        def save(self, name, payload):
            self.saved = payload
    checkpoint = Checkpoint()
    token = quality_checkpoints.set(checkpoint)
    (tmp_path / "app.py").write_text("def f():\n    return 1\n")
    diff = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,2 @@\n+def f():\n+    return 1\n"
    monkeypatch.setattr(QualityAgent, "_review_with_llm", lambda *a, **k: None)
    agent = QualityAgent(retriever_fn=lambda *a, **k: RetrievalResult(passages=[RetrievedPassage("Function rule", "rules.md", 0, "1")]))
    try:
        for reused in (False, True):
            coverage = Coverage(eligible_files=["app.py"])
            coverage_token = current.set(coverage)
            try:
                agent.run(diff, ["app.py"], str(tmp_path))
            finally:
                current.reset(coverage_token)
            assert coverage.batches == {"completed": 0 if reused else 1, "failed": 0, "reused": 1 if reused else 0}
    finally:
        quality_checkpoints.reset(token)


def test_optional_budget_preserves_success_and_skipped_counts(monkeypatch):
    from backend.agents.test_gap_agent import TestGapAgent
    from backend.agents.state import FunctionInfo, TestGap, TestGapAgentResult, DraftedTest
    from backend.services.agent_coverage import Coverage, current
    from backend.tools.llm_client import LLMBudgetError
    class LLM:
        calls = 0
        def complete(self, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise LLMBudgetError("Optional deadline")
            return "{}"
    agent = TestGapAgent(llm_client=LLM())
    monkeypatch.setattr(agent, "_validate_drafted_test", lambda *a: DraftedTest("f", "app.py", "def test_f(): pass"))
    targets = [TestGap(FunctionInfo("f", "app.py", 1, 2, "def f(): pass")) for _ in range(2)]
    coverage = Coverage()
    token = current.set(coverage)
    try:
        agent._draft_tests(targets, "", TestGapAgentResult())
    finally:
        current.reset(token)
    assert coverage.enrichment_counts == {"completed": 1, "skipped": 1, "failed": 0}
    assert coverage.enrichment == "skipped"


def test_summary_separates_execution_and_coverage():
    from backend.services.report_builder import AggregatedReport, AgentStatus, UnifiedFinding
    from backend.services.review_service import _build_summary
    from backend.tools.results import Severity
    from backend.agents.state import AgentOutcome
    status = AgentStatus("quality", AgentOutcome.OK, 1, coverage={"execution": "completed", "status": "partial"})
    report = AggregatedReport([UnifiedFinding("quality", Severity.HIGH, "Rule", "Evidence")], [status])
    summary = _build_summary(report)
    assert "1/1 agent executions completed" in summary
    assert "0/1 with complete applicable coverage" in summary
