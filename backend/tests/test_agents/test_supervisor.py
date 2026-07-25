"""Tests for the Supervisor Agent (LangGraph graph)."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

import pytest

from backend.agents.state import (
    PRMetadata,
    ReviewState,
    SecurityAgentResult,
    TriagedFinding,
    ScannerStatus,
    TestGapAgentResult,
    TestGap,
    DraftedTest,
    FunctionInfo,
    DocAgentResult,
    DocTarget,
    DraftedDocstring,
)
from backend.agents.supervisor import (
    AGENT_NAMES,
    _run_security_node,
    _run_quality_node,
    _run_test_gap_node,
    _run_documentation_node,
    _fan_out,
    _aggregate,
    build_supervisor_graph,
)
from backend.tools.results import RawFinding, Severity


def _base_state() -> ReviewState:
    return {
        "review_id": 1,
        "pr": PRMetadata(
            repo_full_name="owner/repo",
            pr_number=42,
            head_sha="abc1234",
            changed_files=["src/app.py"],
        ),
        "diff": "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,1 +1,2 @@\n+print('hello')\n",
        "workspace_path": "/tmp/test_workspace",
        "raw_findings": {},
        "triaged_findings": {},
        "scanner_statuses": {},
        "agent_notes": {},
        "quality_result": {},
        "test_gap_result": {},
        "doc_result": {},
    }


# --- Individual node tests ---


class TestSecurityNode:
    def test_success(self):
        finding = RawFinding(
            scanner="semgrep",
            rule_id="sql-injection",
            message="SQL injection",
            severity=Severity.HIGH,
            file_path="src/app.py",
            line=10,
        )
        triaged = TriagedFinding(
            fingerprint=finding.fingerprint,
            scanner="semgrep",
            rule_id="sql-injection",
            file_path="src/app.py",
            line=10,
            original_severity=Severity.HIGH,
            triaged_severity=Severity.HIGH,
            explanation="Direct SQL injection risk",
            priority=1,
        )
        result = SecurityAgentResult(
            raw_findings=[finding],
            triaged_findings=[triaged],
            scanner_statuses=[ScannerStatus(scanner="semgrep", ok=True, finding_count=1)],
            notes=["Triage complete"],
        )

        with patch("backend.agents.security_agent.SecurityAgent") as MockAgent:
            MockAgent.return_value.run.return_value = result
            output = _run_security_node(_base_state())

        assert output["triaged_findings"]["security"] == [triaged]
        assert output["raw_findings"]["security"] == [finding]
        assert output["scanner_statuses"]["security"][0].ok is True
        assert output["agent_notes"]["security"] == ["Triage complete"]

    def test_failure_is_caught(self):
        with patch("backend.agents.security_agent.SecurityAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("scanner crashed")
            output = _run_security_node(_base_state())

        assert output["triaged_findings"]["security"] == []
        assert output["raw_findings"]["security"] == []
        assert "Agent failed:" in output["agent_notes"]["security"][0]


class TestQualityNode:
    def test_success(self):
        from backend.agents.quality_agent import QualityAgentResult, QualityFinding

        qf = QualityFinding(
            file_path="src/app.py",
            line=5,
            rule_violated="max-line-length",
            explanation="Line exceeds 120 chars",
            severity="medium",
            cited_passage="Lines must not exceed 120 characters",
            source_file="standards.md",
        )
        result = QualityAgentResult(findings=[qf], notes=["1 finding"])

        with patch("backend.agents.quality_agent.QualityAgent") as MockAgent:
            MockAgent.return_value.run.return_value = result
            output = _run_quality_node(_base_state())

        data = output["quality_result"]["quality"]
        assert len(data["findings"]) == 1
        assert data["findings"][0]["rule_violated"] == "max-line-length"

    def test_failure_is_caught(self):
        with patch("backend.agents.quality_agent.QualityAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("RAG down")
            output = _run_quality_node(_base_state())

        assert output["quality_result"]["quality"]["findings"] == []
        assert "Agent failed:" in output["agent_notes"]["quality"][0]


class TestTestGapNode:
    def test_success(self):
        func = FunctionInfo(
            name="process_data",
            file_path="src/app.py",
            start_line=10,
            end_line=25,
            source="def process_data(): ...",
        )
        gap = TestGap(function=func, risk_score=7)
        draft = DraftedTest(
            target_function="process_data",
            target_file="src/app.py",
            test_code="def test_process_data(): pass",
            imports_valid=True,
        )
        result = TestGapAgentResult(gaps=[gap], drafted_tests=[draft], notes=["1 gap found"])

        with patch("backend.agents.test_gap_agent.TestGapAgent") as MockAgent:
            MockAgent.return_value.run.return_value = result
            output = _run_test_gap_node(_base_state())

        data = output["test_gap_result"]["test_gap"]
        assert len(data["gaps"]) == 1
        assert data["gaps"][0]["function"]["name"] == "process_data"
        assert len(data["drafted_tests"]) == 1

    def test_failure_is_caught(self):
        with patch("backend.agents.test_gap_agent.TestGapAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("AST parse error")
            output = _run_test_gap_node(_base_state())

        assert output["test_gap_result"]["test_gap"]["gaps"] == []
        assert "Agent failed:" in output["agent_notes"]["test_gap"][0]


class TestDocumentationNode:
    def test_success(self):
        func = FunctionInfo(
            name="calculate",
            file_path="src/math.py",
            start_line=5,
            end_line=15,
            source="def calculate(x, y): ...",
            params=["x", "y"],
        )
        target = DocTarget(function=func, reason="missing")
        draft = DraftedDocstring(
            target_function="calculate",
            target_file="src/math.py",
            docstring="Calculate the result.",
            params_valid=True,
        )
        result = DocAgentResult(
            flagged_functions=[target],
            drafted_docstrings=[draft],
            notes=["1 docstring missing"],
        )

        with patch("backend.agents.documentation_agent.DocumentationAgent") as MockAgent:
            MockAgent.return_value.run.return_value = result
            output = _run_documentation_node(_base_state())

        data = output["doc_result"]["documentation"]
        assert len(data["flagged_functions"]) == 1
        assert len(data["drafted_docstrings"]) == 1

    def test_failure_is_caught(self):
        with patch("backend.agents.documentation_agent.DocumentationAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("workspace gone")
            output = _run_documentation_node(_base_state())

        assert output["doc_result"]["documentation"]["flagged_functions"] == []
        assert "Agent failed:" in output["agent_notes"]["documentation"][0]


# --- Fan-out / Aggregate tests ---


class TestFanOut:
    def test_returns_four_sends(self):
        sends = _fan_out(_base_state())
        assert len(sends) == 4
        nodes = [s.node for s in sends]
        assert set(nodes) == {"security", "quality", "test_gap", "documentation"}


class TestAggregate:
    def test_all_succeed(self):
        state = _base_state()
        state["agent_notes"] = {
            "security": ["Done"],
            "quality": ["Done"],
            "test_gap": ["Done"],
            "documentation": ["Done"],
        }
        result = _aggregate(state)
        assert result == {}

    def test_partial_failure_detected(self):
        state = _base_state()
        state["agent_notes"] = {
            "security": ["Agent failed: timeout"],
            "quality": ["Done"],
            "test_gap": ["Agent failed: parse error"],
            "documentation": ["Done"],
        }
        result = _aggregate(state)
        assert result == {}


# --- Full graph compilation + invocation tests ---


class TestFullGraph:
    def test_graph_compiles(self):
        graph = build_supervisor_graph()
        assert graph is not None

    @patch("backend.agents.documentation_agent.DocumentationAgent")
    @patch("backend.agents.test_gap_agent.TestGapAgent")
    @patch("backend.agents.quality_agent.QualityAgent")
    @patch("backend.agents.security_agent.SecurityAgent")
    def test_graph_invokes_all_agents(self, MockSec, MockQual, MockTG, MockDoc):
        MockSec.return_value.run.return_value = SecurityAgentResult(
            notes=["sec done"],
        )
        from backend.agents.quality_agent import QualityAgentResult
        MockQual.return_value.run.return_value = QualityAgentResult(notes=["qual done"])

        MockTG.return_value.run.return_value = TestGapAgentResult(notes=["tg done"])
        MockDoc.return_value.run.return_value = DocAgentResult(notes=["doc done"])

        graph = build_supervisor_graph()
        initial_state = _base_state()
        result = graph.invoke(initial_state)

        assert "security" in result.get("agent_notes", {})
        assert "quality" in result.get("agent_notes", {})
        assert "test_gap" in result.get("agent_notes", {})
        assert "documentation" in result.get("agent_notes", {})

    @patch("backend.agents.documentation_agent.DocumentationAgent")
    @patch("backend.agents.test_gap_agent.TestGapAgent")
    @patch("backend.agents.quality_agent.QualityAgent")
    @patch("backend.agents.security_agent.SecurityAgent")
    def test_graph_tolerates_all_agents_failing(self, MockSec, MockQual, MockTG, MockDoc):
        MockSec.return_value.run.side_effect = RuntimeError("sec fail")
        MockQual.return_value.run.side_effect = RuntimeError("qual fail")
        MockTG.return_value.run.side_effect = RuntimeError("tg fail")
        MockDoc.return_value.run.side_effect = RuntimeError("doc fail")

        graph = build_supervisor_graph()
        result = graph.invoke(_base_state())

        notes = result.get("agent_notes", {})
        for name in AGENT_NAMES:
            assert name in notes
            assert any("Agent failed:" in n for n in notes[name])

    @patch("backend.agents.documentation_agent.DocumentationAgent")
    @patch("backend.agents.test_gap_agent.TestGapAgent")
    @patch("backend.agents.quality_agent.QualityAgent")
    @patch("backend.agents.security_agent.SecurityAgent")
    def test_graph_tolerates_two_agents_failing(self, MockSec, MockQual, MockTG, MockDoc):
        MockSec.return_value.run.side_effect = RuntimeError("sec fail")
        MockQual.return_value.run.side_effect = RuntimeError("qual fail")
        MockTG.return_value.run.return_value = TestGapAgentResult(notes=["tg done"])
        MockDoc.return_value.run.return_value = DocAgentResult(notes=["doc done"])

        graph = build_supervisor_graph()
        result = graph.invoke(_base_state())

        notes = result.get("agent_notes", {})
        assert "Agent failed:" in notes["security"][0]
        assert "Agent failed:" in notes["quality"][0]
        assert "tg done" in notes["test_gap"]
        assert "doc done" in notes["documentation"]
