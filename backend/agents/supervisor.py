"""Supervisor Agent — LangGraph StateGraph orchestrating four specialist agents.

Fans out to Security, Quality, Test-Gap, and Documentation agents in parallel via
LangGraph's Send API. Each agent node catches its own exceptions (partial-failure
tolerance). After all agents complete, the aggregate node merges results.

Every node also reports a structured :class:`AgentOutcome` into ``agent_outcomes``.
That is the single source of truth for whether an agent actually ran; downstream
consumers must not infer it from note wording, which is written for humans and will
drift.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agents.state import AgentOutcome, ReviewState

logger = logging.getLogger(__name__)

AGENT_NAMES = ("security", "quality", "test_gap", "documentation")


def _run_security_node(state: ReviewState) -> dict[str, Any]:
    """Run the Security Agent; tolerates failure."""
    from backend.agents.security_agent import SecurityAgent

    workspace_path = state.get("workspace_path", "")
    diff = state.get("diff", "")
    agent_name = "security"
    try:
        agent = SecurityAgent()
        result = agent.run(workspace_path, diff)
        # The agent reports its own outcome (it knows whether triage succeeded).
        outcome = result.outcome
        # Every scanner failing also means no security signal at all, which must not
        # be reported as a clean run even though triage was never attempted.
        if result.failed_scanners and not result.succeeded_scanners:
            outcome = AgentOutcome.DEGRADED
        return {
            "raw_findings": {agent_name: result.raw_findings},
            "triaged_findings": {agent_name: result.triaged_findings},
            "scanner_statuses": {agent_name: result.scanner_statuses},
            "agent_notes": {agent_name: result.notes},
            "agent_outcomes": {agent_name: outcome.value},
        }
    except Exception as exc:
        logger.exception("Security agent failed: %s", exc)
        return {
            "raw_findings": {agent_name: []},
            "triaged_findings": {agent_name: []},
            "scanner_statuses": {agent_name: []},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
            "agent_outcomes": {agent_name: AgentOutcome.FAILED.value},
        }


def _run_quality_node(state: ReviewState) -> dict[str, Any]:
    """Run the Quality Agent; tolerates failure."""
    from backend.agents.quality_agent import QualityAgent

    diff = state.get("diff", "")
    pr = state.get("pr")
    changed_files = pr.changed_files if pr else []
    workspace_path = state.get("workspace_path", "")
    installation_id = state.get("installation_id")
    agent_name = "quality"
    try:
        agent = QualityAgent(installation_id=installation_id, standards_version=state.get("standards_version"))
        # workspace_path enables the AST symbol-existence gates.
        result = agent.run(
            diff,
            changed_files,
            workspace_path,
            installation_id=installation_id,
        )
        serialized = asdict(result)
        serialized["outcome"] = result.outcome.value
        serialized["failure_reason"] = result.failure_reason
        return {
            "quality_result": {agent_name: serialized},
            "agent_notes": {agent_name: result.notes},
            "agent_outcomes": {agent_name: result.outcome.value},
        }
    except Exception as exc:
        logger.exception("Quality agent failed: %s", exc)
        return {
            "quality_result": {
                agent_name: {
                    "findings": [],
                    "notes": [],
                    "outcome": AgentOutcome.FAILED.value,
                    "failure_reason": str(exc),
                }
            },
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
            "agent_outcomes": {agent_name: AgentOutcome.FAILED.value},
        }


def _run_test_gap_node(state: ReviewState) -> dict[str, Any]:
    """Run the Test-Gap Agent; tolerates failure."""
    from backend.agents.test_gap_agent import TestGapAgent

    diff = state.get("diff", "")
    pr = state.get("pr")
    changed_files = pr.changed_files if pr else []
    workspace_path = state.get("workspace_path", "")
    agent_name = "test_gap"
    try:
        agent = TestGapAgent()
        result = agent.run(diff, changed_files, workspace_path)
        serialized = {
            "gaps": [asdict(g) for g in result.gaps],
            "drafted_tests": [asdict(d) for d in result.drafted_tests],
            "notes": result.notes,
        }
        return {
            "test_gap_result": {agent_name: serialized},
            "agent_notes": {agent_name: result.notes},
            "agent_outcomes": {agent_name: result.outcome.value},
        }
    except Exception as exc:
        logger.exception("Test-gap agent failed: %s", exc)
        return {
            "test_gap_result": {agent_name: {"gaps": [], "drafted_tests": [], "notes": []}},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
            "agent_outcomes": {agent_name: AgentOutcome.FAILED.value},
        }


def _run_documentation_node(state: ReviewState) -> dict[str, Any]:
    """Run the Documentation Agent; tolerates failure."""
    from backend.agents.documentation_agent import DocumentationAgent

    diff = state.get("diff", "")
    pr = state.get("pr")
    changed_files = pr.changed_files if pr else []
    workspace_path = state.get("workspace_path", "")
    agent_name = "documentation"
    try:
        agent = DocumentationAgent()
        result = agent.run(diff, changed_files, workspace_path)
        serialized = {
            "flagged_functions": [asdict(f) for f in result.flagged_functions],
            "drafted_docstrings": [asdict(d) for d in result.drafted_docstrings],
            "notes": result.notes,
        }
        return {
            "doc_result": {agent_name: serialized},
            "agent_notes": {agent_name: result.notes},
            "agent_outcomes": {agent_name: result.outcome.value},
        }
    except Exception as exc:
        logger.exception("Documentation agent failed: %s", exc)
        return {
            "doc_result": {agent_name: {"flagged_functions": [], "drafted_docstrings": [], "notes": []}},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
            "agent_outcomes": {agent_name: AgentOutcome.FAILED.value},
        }


def _fan_out(state: ReviewState) -> list[Send]:
    """Conditional edge that dispatches all four agents in parallel."""
    return [
        Send("security", state),
        Send("quality", state),
        Send("test_gap", state),
        Send("documentation", state),
    ]


def _aggregate(state: ReviewState) -> dict[str, Any]:
    """Fan-in convergence point.

    All per-agent state is already merged via the Annotated reducers by the time
    this node executes. This node logs status and passes through.
    """
    outcomes = state.get("agent_outcomes", {})
    by_outcome: dict[AgentOutcome, list[str]] = {}
    for name in AGENT_NAMES:
        outcome = AgentOutcome.coerce(outcomes.get(name, AgentOutcome.OK.value))
        by_outcome.setdefault(outcome, []).append(name)

    logger.info(
        "Aggregation complete: %d/%d agents OK (degraded: %s, failed: %s)",
        len(by_outcome.get(AgentOutcome.OK, [])),
        len(AGENT_NAMES),
        by_outcome.get(AgentOutcome.DEGRADED) or "none",
        by_outcome.get(AgentOutcome.FAILED) or "none",
    )
    return {}


def build_supervisor_graph(progress=None) -> StateGraph:
    """Construct and compile the supervisor StateGraph."""
    graph = StateGraph(ReviewState)

    def tracked(name, node):
        def execute(state):
            from backend.tools.llm_metrics import agent_metrics
            if progress:
                progress("agent", "started", name)
            pr = state.get("pr")
            with agent_metrics(name, repo=pr.repo_full_name if pr else None,
                               pr=pr.pr_number if pr else None, revision=pr.head_sha if pr else None):
                result = node(state)
            if progress:
                progress("agent", result["agent_outcomes"][name], name)
            return result
        return execute
    graph.add_node("security", tracked("security", _run_security_node))
    graph.add_node("quality", tracked("quality", _run_quality_node))
    graph.add_node("test_gap", tracked("test_gap", _run_test_gap_node))
    graph.add_node("documentation", tracked("documentation", _run_documentation_node))
    graph.add_node("aggregate", _aggregate)

    graph.add_conditional_edges(START, _fan_out)
    graph.add_edge("security", "aggregate")
    graph.add_edge("quality", "aggregate")
    graph.add_edge("test_gap", "aggregate")
    graph.add_edge("documentation", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()
