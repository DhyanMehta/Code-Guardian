"""Shared typed state for the CodeGuardian LangGraph graph.

Kept intentionally minimal for Session 2. The Supervisor (Session 5) will build a
``StateGraph`` over :class:`ReviewState`; each specialist agent reads the PR
metadata + diff and writes its raw findings and LLM-triaged findings into the
per-agent maps. Using a ``TypedDict`` with reducer-friendly dict fields keeps the
state compatible with LangGraph 1.x's Graph API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from backend.tools.results import RawFinding, Severity


@dataclass
class PRMetadata:
    """Identifying information for the pull request under review."""

    repo_full_name: str
    pr_number: int
    head_sha: str = ""
    changed_files: list[str] = field(default_factory=list)


@dataclass
class TriagedFinding:
    """An LLM-triaged view of a single raw finding.

    Always anchored to a real :class:`RawFinding` via ``fingerprint`` — the agent
    drops any LLM output whose fingerprint does not map to a raw finding.
    """

    fingerprint: str
    scanner: str
    rule_id: str
    file_path: str | None
    line: int | None
    original_severity: Severity
    triaged_severity: Severity
    explanation: str
    priority: int  # 1 = highest


@dataclass
class ScannerStatus:
    """Per-scanner outcome for one agent run (for partial-failure reporting)."""

    scanner: str
    ok: bool
    finding_count: int = 0
    error: str | None = None
    error_type: str | None = None


@dataclass
class SecurityAgentResult:
    """Typed output of the Security Agent."""

    raw_findings: list[RawFinding] = field(default_factory=list)
    triaged_findings: list[TriagedFinding] = field(default_factory=list)
    scanner_statuses: list[ScannerStatus] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def failed_scanners(self) -> list[str]:
        return [s.scanner for s in self.scanner_statuses if not s.ok]

    @property
    def succeeded_scanners(self) -> list[str]:
        return [s.scanner for s in self.scanner_statuses if s.ok]


class ReviewState(TypedDict, total=False):
    """Shared graph state read/written by the specialist agents + supervisor.

    ``total=False`` so agents can populate their slice incrementally.
    """

    pr: PRMetadata
    diff: str
    # Directory containing the checked-out changed files the scanners run against.
    workspace_path: str

    # Per-agent raw (deterministic) findings, keyed by agent name.
    raw_findings: dict[str, list[RawFinding]]
    # Per-agent LLM-triaged findings, keyed by agent name.
    triaged_findings: dict[str, list[TriagedFinding]]
    # Per-agent, per-scanner status for partial-failure transparency.
    scanner_statuses: dict[str, list[ScannerStatus]]
    # Free-form per-agent notes (e.g. "LLM triage skipped: no findings").
    agent_notes: dict[str, list[str]]
    # Quality Agent result (RAG-grounded findings).
    quality_result: dict  # QualityAgentResult serialized; avoids circular import.
