
"""Shared typed state for the CodeGuardian LangGraph graph.

The Supervisor (Session 5) builds a ``StateGraph`` over :class:`ReviewState`; each
specialist agent reads the PR metadata + diff and writes its results into the
per-agent maps. Using ``Annotated`` fields with dict-merge reducers lets LangGraph
merge parallel writes from the fan-out nodes without conflicts.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, TypedDict

from backend.tools.results import RawFinding, Severity


def _merge_dicts(left: dict, right: dict) -> dict:
    """Reducer that shallow-merges two dicts (right wins on key conflict)."""
    merged = left.copy()
    merged.update(right)
    return merged


class AgentOutcome(str, Enum):
    """Structured run outcome for a single specialist agent.

    Reported by the agent (or by the supervisor node that wrapped it) rather than
    inferred from note wording, so consumers can tell "ran cleanly and found
    nothing" apart from "could not run at all". Note text is for humans; this field
    is the contract.
    """

    OK = "ok"
    """The agent completed its analysis. Zero findings is a real, clean result."""

    DEGRADED = "degraded"
    """The agent ran but could not complete its analysis (missing RAG context,
    LLM unavailable, unusable model response). Zero findings here means
    "unknown", not "clean"."""

    FAILED = "failed"
    UNKNOWN = "unknown"
    """The agent raised an unhandled exception and produced nothing."""

    @classmethod
    def coerce(cls, value: object) -> "AgentOutcome":
        """Best-effort conversion from a serialized value, defaulting to OK."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError:
            return cls.UNKNOWN


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

    # Structured run outcome, same contract as the Quality Agent's. Scanners
    # succeeding is not enough: if triage fails, real raw findings exist but none are
    # reported, and calling that OK with a count of zero reads as "clean".
    outcome: AgentOutcome = AgentOutcome.OK
    failure_reason: str | None = None

    @property
    def failed_scanners(self) -> list[str]:
        return [s.scanner for s in self.scanner_statuses if not s.ok]

    @property
    def succeeded_scanners(self) -> list[str]:
        return [s.scanner for s in self.scanner_statuses if s.ok]

    def mark_degraded(self, reason: str) -> None:
        """Record that the agent ran but could not complete its analysis."""
        self.outcome = AgentOutcome.DEGRADED
        self.failure_reason = reason


@dataclass
class FunctionInfo:
    """A function/method extracted from a source file via AST."""

    name: str
    file_path: str
    start_line: int
    end_line: int
    source: str
    is_method: bool = False
    class_name: str | None = None
    complexity: int = 0  # count of branching nodes (if/for/while/try/except)
    params: list[str] = field(default_factory=list)
    return_annotation: str | None = None


@dataclass
class TestGap:
    """A function identified as lacking direct test coverage."""

    function: FunctionInfo
    risk_score: int = 0


@dataclass
class DraftedTest:
    """A starter unit test drafted by the LLM for a test gap."""

    target_function: str
    target_file: str
    test_code: str
    imports_valid: bool = True


@dataclass
class TestGapAgentResult:
    """Typed output of the Test-Gap Agent."""

    gaps: list[TestGap] = field(default_factory=list)
    drafted_tests: list[DraftedTest] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    outcome: AgentOutcome = AgentOutcome.OK

    @property
    def has_gaps(self) -> bool:
        return len(self.gaps) > 0


@dataclass
class DocTarget:
    """A function flagged for missing or outdated documentation."""

    function: FunctionInfo
    reason: str  # "missing" | "outdated" | "incomplete"
    existing_docstring: str | None = None


@dataclass
class DraftedDocstring:
    """A replacement docstring drafted by the LLM."""

    target_function: str
    target_file: str
    docstring: str
    params_valid: bool = True


@dataclass
class DocAgentResult:
    """Typed output of the Documentation Agent."""

    flagged_functions: list[DocTarget] = field(default_factory=list)
    drafted_docstrings: list[DraftedDocstring] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    outcome: AgentOutcome = AgentOutcome.OK

    @property
    def has_findings(self) -> bool:
        return len(self.flagged_functions) > 0


class ReviewState(TypedDict, total=False):
    """Shared graph state read/written by the specialist agents + supervisor.

    ``total=False`` so agents can populate their slice incrementally.
    Annotated fields use dict-merge reducers so parallel fan-out nodes can each
    write their keyed slice without conflicting.
    """

    review_id: int
    pr: PRMetadata
    diff: str
    workspace_path: str
    installation_id: int | None
    standards_version: str | None

    # Per-agent results, keyed by agent name — merged via _merge_dicts reducer.
    raw_findings: Annotated[dict[str, list[RawFinding]], _merge_dicts]
    triaged_findings: Annotated[dict[str, list[TriagedFinding]], _merge_dicts]
    scanner_statuses: Annotated[dict[str, list[ScannerStatus]], _merge_dicts]
    agent_notes: Annotated[dict[str, list[str]], _merge_dicts]
    quality_result: Annotated[dict[str, Any], _merge_dicts]
    test_gap_result: Annotated[dict[str, Any], _merge_dicts]
    doc_result: Annotated[dict[str, Any], _merge_dicts]

    # Structured per-agent run outcome (an :class:`AgentOutcome` value), keyed by
    # agent name. The report builder reads this instead of pattern-matching notes.
    agent_outcomes: Annotated[dict[str, str], _merge_dicts]
