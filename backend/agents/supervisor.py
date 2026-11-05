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
import subprocess
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


def build_supervisor_graph(progress=None, *, analysis_deadline=None, checkpoints=None) -> StateGraph:
    """Construct and compile the supervisor StateGraph."""
    from threading import Event, Lock

    graph = StateGraph(ReviewState)
    core_done = Event()
    core_lock = Lock()
    core_pending = {"security", "quality"}

    def tracked(name, node):
        def execute(state):
            from backend.tools.review_budget import required_analysis_done

            token = required_analysis_done.set(
                core_done if analysis_deadline is not None and name in {"test_gap", "documentation"} else None
            )
            try:
                return run(state)
            finally:
                required_analysis_done.reset(token)
                if name in {"security", "quality"}:
                    with core_lock:
                        core_pending.discard(name)
                        if not core_pending:
                            core_done.set()

        def run(state):
            from backend.services.agent_checkpoints import quality_checkpoints
            from backend.tools.llm_metrics import agent_metrics
            from backend.tools.review_budget import deadline
            from backend.services.agent_coverage import classify, current
            if checkpoints:
                saved = checkpoints.load(name)
                if saved is not None:
                    if progress:
                        progress("agent", "reused", name)
                        progress("agent", saved["agent_outcomes"][name], name)
                    metadata = saved.get("agent_coverage", {}).get(name)
                    if metadata:
                        metadata["batches"]["reused"] += metadata["batches"]["completed"]
                        metadata["batches"]["completed"] = 0
                    return saved
            if progress:
                progress("agent", "started", name)
            pr = state.get("pr")
            with agent_metrics(name, repo=pr.repo_full_name if pr else None,
                               pr=pr.pr_number if pr else None, revision=pr.head_sha if pr else None, progress=progress):
                token = deadline.set(analysis_deadline)
                checkpoint_token = quality_checkpoints.set(
                    checkpoints if name == "quality" and hasattr(checkpoints, "quality_batch") else None
                )
                coverage = classify(pr.changed_files if pr else [], name)
                coverage_token = current.set(coverage)
                try:
                    result = node(state)
                    if name == "quality":
                        quality = result.get("quality_result", {}).get(name, {})
                        if (quality.get("failure_reason") or "").startswith("Python Quality batches exclude") and not coverage.batches["failed"]:
                            result["agent_outcomes"][name] = "ok"
                            quality["outcome"] = "ok"
                            quality["failure_reason"] = None
                    from backend.agents.frontend_analysis import extend_result
                    try:
                        extend_result(name, state, result)
                    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                        result["agent_outcomes"][name] = AgentOutcome.DEGRADED.value
                        coverage.batches["failed"] += 1
                        result["agent_notes"][name].append(f"Frontend analysis incomplete: {exc}")
                        if name == "quality":
                            result["quality_result"][name]["outcome"] = AgentOutcome.DEGRADED.value
                            result["quality_result"][name]["failure_reason"] = f"Frontend analysis incomplete: {exc}"
                    data_key = {"quality": ("quality_result", "findings"), "test_gap": ("test_gap_result", "gaps"),
                                "documentation": ("doc_result", "flagged_functions")}.get(name)
                    if data_key:
                        coverage.findings = len(result.get(data_key[0], {}).get(name, {}).get(data_key[1], []))
                    else:
                        coverage.findings = len(result.get("triaged_findings", {}).get(name, []))
                        statuses = result.get("scanner_statuses", {}).get(name, [])
                        for scanner in statuses:
                            supported = coverage.eligible_files
                            if scanner.scanner == "bandit":
                                supported = [p for p in supported if p.endswith(".py")]
                            elif scanner.scanner == "semgrep":
                                from pathlib import PurePosixPath
                                supported = [p for p in supported if PurePosixPath(p).suffix.lower() in
                                             {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"} and not p.endswith(".d.ts")]
                            coverage.scanners.append({"scanner": scanner.scanner, "completed": scanner.ok,
                                                      "eligible_files": supported})
                            if scanner.ok:
                                coverage.analyzed(supported)
                    coverage.finish(result["agent_outcomes"][name])
                    result["agent_coverage"] = {name: asdict(coverage)}
                finally:
                    current.reset(coverage_token)
                    quality_checkpoints.reset(checkpoint_token)
                    deadline.reset(token)
            if checkpoints and result["agent_outcomes"][name] == AgentOutcome.OK.value:
                checkpoints.save(name, result)
            if progress:
                progress("agent", result["agent_outcomes"][name], name)
            return result
        return execute
    graph.add_node("security", tracked("security", _run_security_node))
    graph.add_node("quality", tracked("quality", _run_quality_node))
    graph.add_node("test_gap", tracked("test_gap", _run_test_gap_node))
    graph.add_node("documentation", tracked("documentation", _run_documentation_node))
    graph.add_node("aggregate", _aggregate)

    def dispatch(state):
        with core_lock:
            core_pending.update(("security", "quality"))
            core_done.clear()
        return _fan_out(state)

    graph.add_conditional_edges(START, dispatch)
    graph.add_edge("security", "aggregate")
    graph.add_edge("quality", "aggregate")
    graph.add_edge("test_gap", "aggregate")
    graph.add_edge("documentation", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()
