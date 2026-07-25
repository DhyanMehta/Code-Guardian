"""Supervisor Agent — LangGraph StateGraph orchestrating four specialist agents.

Fans out to Security, Quality, Test-Gap, and Documentation agents in parallel via
LangGraph's Send API. Each agent node catches its own exceptions (partial-failure
tolerance). After all agents complete, the aggregate node merges results.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agents.state import ReviewState

logger = logging.getLogger(__name__)

AGENT_NAMES = ("security", "quality", "test_gap", "documentation")


def _run_security_node(state: ReviewState) -> dict[str, Any]:
    """Run the Security Agent; tolerates failure."""
    from backend.agents.security_agent import SecurityAgent

    workspace_path = state.get("workspace_path", "")
    agent_name = "security"
    try:
        agent = SecurityAgent()
        result = agent.run(workspace_path)
        return {
            "raw_findings": {agent_name: result.raw_findings},
            "triaged_findings": {agent_name: result.triaged_findings},
            "scanner_statuses": {agent_name: result.scanner_statuses},
            "agent_notes": {agent_name: result.notes},
        }
    except Exception as exc:
        logger.exception("Security agent failed: %s", exc)
        return {
            "raw_findings": {agent_name: []},
            "triaged_findings": {agent_name: []},
            "scanner_statuses": {agent_name: []},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
        }


def _run_quality_node(state: ReviewState) -> dict[str, Any]:
    """Run the Quality Agent; tolerates failure."""
    from backend.agents.quality_agent import QualityAgent

    diff = state.get("diff", "")
    pr = state.get("pr")
    changed_files = pr.changed_files if pr else []
    agent_name = "quality"
    try:
        agent = QualityAgent()
        result = agent.run(diff, changed_files)
        return {
            "quality_result": {agent_name: asdict(result)},
            "agent_notes": {agent_name: result.notes},
        }
    except Exception as exc:
        logger.exception("Quality agent failed: %s", exc)
        return {
            "quality_result": {agent_name: {"findings": [], "notes": []}},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
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
        }
    except Exception as exc:
        logger.exception("Test-gap agent failed: %s", exc)
        return {
            "test_gap_result": {agent_name: {"gaps": [], "drafted_tests": [], "notes": []}},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
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
        }
    except Exception as exc:
        logger.exception("Documentation agent failed: %s", exc)
        return {
            "doc_result": {agent_name: {"flagged_functions": [], "drafted_docstrings": [], "notes": []}},
            "agent_notes": {agent_name: [f"Agent failed: {exc}"]},
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
    succeeded = []
    failed = []
    for name in AGENT_NAMES:
        notes = state.get("agent_notes", {}).get(name, [])
        if any(n.startswith("Agent failed:") for n in notes):
            failed.append(name)
        else:
            succeeded.append(name)

    logger.info(
        "Aggregation complete: %d/%d agents succeeded (failed: %s)",
        len(succeeded),
        len(AGENT_NAMES),
        failed or "none",
    )
    return {}


def build_supervisor_graph() -> StateGraph:
    """Construct and compile the supervisor StateGraph."""
    graph = StateGraph(ReviewState)

    graph.add_node("security", _run_security_node)
    graph.add_node("quality", _run_quality_node)
    graph.add_node("test_gap", _run_test_gap_node)
    graph.add_node("documentation", _run_documentation_node)
    graph.add_node("aggregate", _aggregate)

    graph.add_conditional_edges(START, _fan_out)
    graph.add_edge("security", "aggregate")
    graph.add_edge("quality", "aggregate")
    graph.add_edge("test_gap", "aggregate")
    graph.add_edge("documentation", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()
