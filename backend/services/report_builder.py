"""Report builder — aggregation, severity ranking, and PR comment formatting.

Normalizes findings from all four specialist agents into a unified schema, ranks
them by severity, and renders a single PR-comment markdown string.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.agents.state import ReviewState
from backend.agents.supervisor import AGENT_NAMES
from backend.tools.results import Severity

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
    Severity.UNKNOWN: 5,
}

_AGENT_PRIORITY = {
    "security": 0,
    "quality": 1,
    "test_gap": 2,
    "documentation": 3,
}

_SEVERITY_LABELS = {
    Severity.CRITICAL: "\U0001f534 Critical",
    Severity.HIGH: "\U0001f534 High",
    Severity.MEDIUM: "\U0001f7e1 Medium",
    Severity.LOW: "⚪ Low",
    Severity.INFO: "ℹ️ Info",
    Severity.UNKNOWN: "❓ Unknown",
}


@dataclass
class UnifiedFinding:
    """A single finding normalized across all agent types."""

    agent: str
    severity: Severity
    title: str
    detail: str
    file_path: str | None = None
    line: int | None = None
    category: str = ""
    fixable: bool = False
    fix_data: dict | None = None


@dataclass
class AgentStatus:
    """Summary status for one agent's run."""

    name: str
    succeeded: bool = True
    finding_count: int = 0
    error_message: str | None = None
    scanner_info: str | None = None


@dataclass
class AggregatedReport:
    """The fully aggregated review report."""

    findings: list[UnifiedFinding] = field(default_factory=list)
    agent_statuses: list[AgentStatus] = field(default_factory=list)

    @property
    def fixable_count(self) -> int:
        return sum(1 for f in self.findings if f.fixable)


def aggregate(state: ReviewState) -> AggregatedReport:
    """Normalize and rank findings from all agents into a single report."""
    findings: list[UnifiedFinding] = []
    statuses: list[AgentStatus] = []

    # Security agent
    _aggregate_security(state, findings, statuses)
    # Quality agent
    _aggregate_quality(state, findings, statuses)
    # Test-gap agent
    _aggregate_test_gap(state, findings, statuses)
    # Documentation agent
    _aggregate_documentation(state, findings, statuses)

    findings.sort(key=_sort_key)
    return AggregatedReport(findings=findings, agent_statuses=statuses)


def _sort_key(f: UnifiedFinding) -> tuple[int, int, str, int]:
    return (
        _SEVERITY_ORDER.get(f.severity, 99),
        _AGENT_PRIORITY.get(f.agent, 99),
        f.file_path or "",
        f.line or 0,
    )


def _aggregate_security(
    state: ReviewState,
    findings: list[UnifiedFinding],
    statuses: list[AgentStatus],
) -> None:
    agent_name = "security"
    notes = state.get("agent_notes", {}).get(agent_name, [])
    is_failed = any(n.startswith("Agent failed:") for n in notes)

    triaged = state.get("triaged_findings", {}).get(agent_name, [])
    scanner_statuses = state.get("scanner_statuses", {}).get(agent_name, [])

    scanner_parts = []
    for ss in scanner_statuses:
        if ss.ok:
            scanner_parts.append(f"{ss.scanner} OK")
        else:
            scanner_parts.append(f"{ss.scanner} failed ({ss.error_type or 'unknown'})")

    statuses.append(AgentStatus(
        name=agent_name,
        succeeded=not is_failed,
        finding_count=len(triaged),
        error_message=notes[0] if is_failed and notes else None,
        scanner_info=", ".join(scanner_parts) if scanner_parts else None,
    ))

    for tf in triaged:
        findings.append(UnifiedFinding(
            agent=agent_name,
            severity=tf.triaged_severity if isinstance(tf.triaged_severity, Severity) else Severity.normalize(str(tf.triaged_severity)),
            title=tf.rule_id,
            detail=tf.explanation,
            file_path=tf.file_path,
            line=tf.line,
            category=tf.rule_id,
        ))


def _aggregate_quality(
    state: ReviewState,
    findings: list[UnifiedFinding],
    statuses: list[AgentStatus],
) -> None:
    agent_name = "quality"
    notes = state.get("agent_notes", {}).get(agent_name, [])
    is_failed = any(n.startswith("Agent failed:") for n in notes)

    quality_data = state.get("quality_result", {}).get(agent_name, {})
    quality_findings = quality_data.get("findings", [])

    statuses.append(AgentStatus(
        name=agent_name,
        succeeded=not is_failed,
        finding_count=len(quality_findings),
        error_message=notes[0] if is_failed and notes else None,
    ))

    for qf in quality_findings:
        if isinstance(qf, dict):
            sev = Severity.normalize(qf.get("severity", "medium"))
            findings.append(UnifiedFinding(
                agent=agent_name,
                severity=sev,
                title=qf.get("rule_violated", "quality issue"),
                detail=qf.get("explanation", ""),
                file_path=qf.get("file_path"),
                line=qf.get("line"),
                category=qf.get("rule_violated", ""),
            ))


def _aggregate_test_gap(
    state: ReviewState,
    findings: list[UnifiedFinding],
    statuses: list[AgentStatus],
) -> None:
    agent_name = "test_gap"
    notes = state.get("agent_notes", {}).get(agent_name, [])
    is_failed = any(n.startswith("Agent failed:") for n in notes)

    tg_data = state.get("test_gap_result", {}).get(agent_name, {})
    gaps = tg_data.get("gaps", [])
    drafted_tests = tg_data.get("drafted_tests", [])

    drafted_by_func: dict[str, dict] = {}
    for dt in drafted_tests:
        if isinstance(dt, dict) and dt.get("imports_valid", False):
            drafted_by_func[dt.get("target_function", "")] = dt

    statuses.append(AgentStatus(
        name=agent_name,
        succeeded=not is_failed,
        finding_count=len(gaps),
        error_message=notes[0] if is_failed and notes else None,
    ))

    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        func_info = gap.get("function", {})
        func_name = func_info.get("name", "unknown")
        risk_score = gap.get("risk_score", 0)

        if risk_score >= 8:
            sev = Severity.HIGH
        elif risk_score >= 5:
            sev = Severity.MEDIUM
        else:
            sev = Severity.LOW

        draft = drafted_by_func.get(func_name)
        findings.append(UnifiedFinding(
            agent=agent_name,
            severity=sev,
            title=f"Untested: {func_name}",
            detail=f"Risk score: {risk_score}/10",
            file_path=func_info.get("file_path"),
            line=func_info.get("start_line"),
            category="missing-tests",
            fixable=draft is not None,
            fix_data=draft,
        ))


def _aggregate_documentation(
    state: ReviewState,
    findings: list[UnifiedFinding],
    statuses: list[AgentStatus],
) -> None:
    agent_name = "documentation"
    notes = state.get("agent_notes", {}).get(agent_name, [])
    is_failed = any(n.startswith("Agent failed:") for n in notes)

    doc_data = state.get("doc_result", {}).get(agent_name, {})
    flagged = doc_data.get("flagged_functions", [])
    drafted_docs = doc_data.get("drafted_docstrings", [])

    drafted_by_func: dict[str, dict] = {}
    for dd in drafted_docs:
        if isinstance(dd, dict) and dd.get("params_valid", False):
            drafted_by_func[dd.get("target_function", "")] = dd

    statuses.append(AgentStatus(
        name=agent_name,
        succeeded=not is_failed,
        finding_count=len(flagged),
        error_message=notes[0] if is_failed and notes else None,
    ))

    for target in flagged:
        if not isinstance(target, dict):
            continue
        func_info = target.get("function", {})
        func_name = func_info.get("name", "unknown")
        reason = target.get("reason", "missing")

        sev = Severity.MEDIUM if reason == "missing" else Severity.LOW
        draft = drafted_by_func.get(func_name)

        findings.append(UnifiedFinding(
            agent=agent_name,
            severity=sev,
            title=f"Docstring {reason}: {func_name}",
            detail=f"Function at {func_info.get('file_path', '?')}:{func_info.get('start_line', '?')}",
            file_path=func_info.get("file_path"),
            line=func_info.get("start_line"),
            category=f"docstring-{reason}",
            fixable=draft is not None,
            fix_data=draft,
        ))


def format_pr_comment(
    report: AggregatedReport,
    pr_number: int,
    commit_sha: str = "",
) -> str:
    """Render the aggregated report as a GitHub PR-comment markdown string."""
    lines: list[str] = []
    lines.append(f"## CodeGuardian Review — PR #{pr_number}")
    lines.append("")

    # Status line
    succeeded = sum(1 for s in report.agent_statuses if s.succeeded)
    total = len(report.agent_statuses)
    if succeeded == total:
        status_text = f"Completed ({total}/{total} agents succeeded)"
    else:
        status_text = f"Completed ({succeeded}/{total} agents succeeded, {total - succeeded} failed)"
    lines.append(f"**Status**: {status_text}")
    if commit_sha:
        lines.append(f"**Commit**: `{commit_sha[:7]}`")
    lines.append("")

    # Summary counts
    lines.append("### Summary")
    if not report.findings:
        lines.append("No issues found.")
    else:
        by_sev: dict[Severity, list[UnifiedFinding]] = {}
        for f in report.findings:
            by_sev.setdefault(f.severity, []).append(f)

        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            group = by_sev.get(sev, [])
            if group:
                agents_summary = _agent_breakdown(group)
                lines.append(f"- {len(group)} {sev.value}-severity ({agents_summary})")

        if report.fixable_count:
            lines.append(f"- Auto-fix available for {report.fixable_count} finding(s)")
    lines.append("")

    # Findings table by severity
    if report.findings:
        lines.append("---")
        lines.append("")
        lines.append("### Findings")
        lines.append("")

        by_sev_ordered: list[tuple[Severity, list[UnifiedFinding]]] = []
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            group = [f for f in report.findings if f.severity == sev]
            if group:
                by_sev_ordered.append((sev, group))

        idx = 1
        for sev, group in by_sev_ordered:
            lines.append(f"#### {_SEVERITY_LABELS.get(sev, sev.value)}")
            lines.append("")
            lines.append("| # | Agent | File | Finding |")
            lines.append("|---|-------|------|---------|")
            for f in group:
                loc = _format_location(f)
                lines.append(f"| {idx} | {f.agent.replace('_', ' ').title()} | {loc} | {f.title}: {f.detail} |")
                idx += 1
            lines.append("")

    # Agent status table
    lines.append("---")
    lines.append("")
    lines.append("### Agent Status")
    lines.append("")
    lines.append("| Agent | Status | Findings |")
    lines.append("|-------|--------|----------|")
    for s in report.agent_statuses:
        status_icon = "✅" if s.succeeded else "❌"
        extra = ""
        if s.scanner_info:
            extra = f" ({s.scanner_info})"
        elif s.error_message:
            extra = f" ({s.error_message[:60]})"
        lines.append(f"| {s.name.replace('_', ' ').title()} | {status_icon}{extra} | {s.finding_count} |")
    lines.append("")

    # Auto-fix note
    if report.fixable_count:
        lines.append("---")
        lines.append("")
        lines.append("### Auto-Fix Available")
        lines.append("")
        lines.append(
            f"{report.fixable_count} finding(s) have auto-generated fixes (test drafts, docstrings). "
            "No code is pushed without your explicit approval."
        )
        lines.append("")

    lines.append("---")
    lines.append("*Generated by CodeGuardian AI*")
    return "\n".join(lines)


def _agent_breakdown(findings: list[UnifiedFinding]) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.agent] = counts.get(f.agent, 0) + 1
    parts = [f"{c} {a.replace('_', ' ')}" for a, c in sorted(counts.items())]
    return ", ".join(parts)


def _format_location(f: UnifiedFinding) -> str:
    if f.file_path and f.line:
        return f"`{f.file_path}:{f.line}`"
    if f.file_path:
        return f"`{f.file_path}`"
    return "-"
