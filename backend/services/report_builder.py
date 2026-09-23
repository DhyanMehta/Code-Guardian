"""Report builder — aggregation, severity ranking, and PR comment formatting.

Normalizes findings from all four specialist agents into a unified schema, ranks
them by severity, and renders a single PR-comment markdown string.

Agent status comes from the structured ``agent_outcomes`` slice of the graph state,
never from note text. A count of zero findings is ambiguous on its own: it means
"clean" for an agent that ran and "unknown" for one that could not, and reporting
the latter as a success hides a broken review.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from backend.agents.state import AgentOutcome, ReviewState
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

_OUTCOME_DISPLAY = {
    AgentOutcome.OK: ("✅", ""),
    AgentOutcome.DEGRADED: ("⚠️", " could not run"),
    AgentOutcome.FAILED: ("❌", " failed"),
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
    record_id: int | None = None
    """Database id when this finding was rebuilt from a persisted row. Lets callers
    map a ranked result back to the ORM record without re-deriving the order."""


@dataclass
class AgentStatus:
    """Summary status for one agent's run."""

    name: str
    outcome: AgentOutcome = AgentOutcome.OK
    finding_count: int = 0
    error_message: str | None = None
    scanner_info: str | None = None

    @property
    def succeeded(self) -> bool:
        """True only when the agent actually completed its analysis."""
        return self.outcome is AgentOutcome.OK


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


def _agent_outcome(state: ReviewState, agent_name: str) -> AgentOutcome:
    """Read an agent's structured outcome, defaulting to OK when unreported."""
    outcomes = state.get("agent_outcomes", {}) or {}
    return AgentOutcome.coerce(outcomes.get(agent_name, AgentOutcome.OK.value))


def _first_note(notes: list[str]) -> str | None:
    return notes[0] if notes else None


def format_scanner_info(scanner_statuses: Iterable[Any]) -> str | None:
    """Render per-scanner outcomes as the compact string used in Agent Status.

    Shared by the live-review path (which has ``ScannerStatus`` dataclasses) and the
    replay-from-database path (which has dicts), so a report re-rendered from
    persisted rows is identical to the comment that was posted.
    """
    parts: list[str] = []
    for status in scanner_statuses or []:
        if isinstance(status, dict):
            scanner = status.get("scanner", "unknown")
            ok = bool(status.get("ok"))
            error_type = status.get("error_type")
        else:
            scanner = status.scanner
            ok = status.ok
            error_type = status.error_type
        parts.append(
            f"{scanner} OK" if ok else f"{scanner} failed ({error_type or 'unknown'})"
        )
    return ", ".join(parts) if parts else None


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
    outcome = _agent_outcome(state, agent_name)

    triaged = state.get("triaged_findings", {}).get(agent_name, [])
    scanner_statuses = state.get("scanner_statuses", {}).get(agent_name, [])

    statuses.append(AgentStatus(
        name=agent_name,
        outcome=outcome,
        finding_count=len(triaged),
        error_message=_first_note(notes) if outcome is not AgentOutcome.OK else None,
        scanner_info=format_scanner_info(scanner_statuses),
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
    quality_data = state.get("quality_result", {}).get(agent_name, {})
    quality_findings = quality_data.get("findings", [])

    # The agent reports its own outcome; prefer that over the graph-level default so
    # a degraded run (no RAG context, unusable LLM response) is never shown as clean.
    outcome = _agent_outcome(state, agent_name)
    if "outcome" in quality_data:
        outcome = AgentOutcome.coerce(quality_data.get("outcome"))

    error_message = quality_data.get("failure_reason")
    if not error_message and outcome is not AgentOutcome.OK:
        error_message = _first_note(notes)

    statuses.append(AgentStatus(
        name=agent_name,
        outcome=outcome,
        finding_count=len(quality_findings),
        error_message=error_message,
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
    outcome = _agent_outcome(state, agent_name)

    tg_data = state.get("test_gap_result", {}).get(agent_name, {})
    gaps = tg_data.get("gaps", [])
    drafted_tests = tg_data.get("drafted_tests", [])

    drafted_by_func: dict[str, dict] = {}
    for dt in drafted_tests:
        if isinstance(dt, dict) and dt.get("imports_valid", False):
            drafted_by_func[dt.get("target_function", "")] = dt

    statuses.append(AgentStatus(
        name=agent_name,
        outcome=outcome,
        finding_count=len(gaps),
        error_message=_first_note(notes) if outcome is not AgentOutcome.OK else None,
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
    outcome = _agent_outcome(state, agent_name)

    doc_data = state.get("doc_result", {}).get(agent_name, {})
    flagged = doc_data.get("flagged_functions", [])
    drafted_docs = doc_data.get("drafted_docstrings", [])

    drafted_by_func: dict[str, dict] = {}
    for dd in drafted_docs:
        if isinstance(dd, dict) and dd.get("params_valid", False):
            drafted_by_func[dd.get("target_function", "")] = dd

    statuses.append(AgentStatus(
        name=agent_name,
        outcome=outcome,
        finding_count=len(flagged),
        error_message=_first_note(notes) if outcome is not AgentOutcome.OK else None,
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
    total = len(report.agent_statuses)
    succeeded = sum(1 for s in report.agent_statuses if s.succeeded)
    degraded = sum(
        1 for s in report.agent_statuses if s.outcome is AgentOutcome.DEGRADED
    )
    failed = sum(1 for s in report.agent_statuses if s.outcome is AgentOutcome.FAILED)

    if succeeded == total:
        status_text = f"Completed ({total}/{total} agents succeeded)"
    else:
        detail_parts = [f"{succeeded}/{total} agents succeeded"]
        if degraded:
            detail_parts.append(f"{degraded} could not run")
        if failed:
            detail_parts.append(f"{failed} failed")
        status_text = f"Completed ({', '.join(detail_parts)})"
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

    # An agent that could not run makes the whole report incomplete; say so next to
    # the counts rather than only in the status table further down.
    incomplete = [s for s in report.agent_statuses if not s.succeeded]
    if incomplete:
        names = ", ".join(s.name.replace("_", " ").title() for s in incomplete)
        lines.append("")
        lines.append(
            f"> **Incomplete review**: {names} did not run, so this report does not "
            "cover that area. Counts above are a lower bound."
        )
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
        icon, label = _OUTCOME_DISPLAY.get(s.outcome, _OUTCOME_DISPLAY[AgentOutcome.OK])
        extra = ""
        if s.scanner_info:
            extra = f" ({s.scanner_info})"
        elif s.error_message:
            extra = f" ({s.error_message[:80]})"
        count = s.finding_count if s.succeeded else "—"
        lines.append(
            f"| {s.name.replace('_', ' ').title()} | {icon}{label}{extra} | {count} |"
        )
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


def aggregate_from_records(records: Iterable[Any]) -> AggregatedReport:
    """Rank already-persisted findings using the same ordering as a live review.

    ``aggregate()`` works from graph state, which only exists during a run. The
    dashboard and the report endpoint work from database rows, and they must present
    findings in exactly the order the PR comment used — so the ordering stays here,
    in the module that defines it, rather than being reimplemented per consumer.

    Args:
        records: ORM ``Finding`` rows (anything exposing agent/severity/title/
            detail/file_path/line/fix_data/id).

    Returns:
        An :class:`AggregatedReport` with ranked findings and no agent statuses;
        callers supply statuses from their own source of truth.
    """
    findings: list[UnifiedFinding] = []
    for record in records:
        raw_fix = getattr(record, "fix_data", None)
        if isinstance(raw_fix, str) and raw_fix:
            try:
                fix_data = json.loads(raw_fix)
            except json.JSONDecodeError:
                logger.warning(
                    "Finding %s has unparseable fix_data; treating as not fixable.",
                    getattr(record, "id", "?"),
                )
                fix_data = None
        elif isinstance(raw_fix, dict):
            fix_data = raw_fix
        else:
            fix_data = None

        findings.append(
            UnifiedFinding(
                agent=record.agent,
                severity=Severity.normalize(record.severity),
                title=record.title,
                detail=record.detail or "",
                file_path=record.file_path,
                line=record.line,
                category=record.title,
                fixable=fix_data is not None,
                fix_data=fix_data,
                record_id=getattr(record, "id", None),
            )
        )

    findings.sort(key=_sort_key)
    return AggregatedReport(findings=findings, agent_statuses=[])
