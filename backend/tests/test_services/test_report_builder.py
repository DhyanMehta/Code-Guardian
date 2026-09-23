"""Tests for the Report Builder (aggregation + PR comment formatting)."""

from __future__ import annotations

import pytest

from backend.agents.state import (
    AgentOutcome,
    PRMetadata,
    ReviewState,
    TriagedFinding,
    ScannerStatus,
)
from backend.services.report_builder import (
    UnifiedFinding,
    AgentStatus,
    AggregatedReport,
    aggregate,
    format_pr_comment,
    _sort_key,
)
from backend.tools.results import Severity


def _state_with_all_agents() -> ReviewState:
    """A state populated by all four agents with representative findings."""
    return {
        "review_id": 1,
        "pr": PRMetadata(
            repo_full_name="owner/repo",
            pr_number=99,
            head_sha="deadbeef",
            changed_files=["src/app.py", "src/utils.py"],
        ),
        "diff": "",
        "workspace_path": "/tmp/ws",
        "raw_findings": {"security": []},
        "triaged_findings": {
            "security": [
                TriagedFinding(
                    fingerprint="fp1",
                    scanner="semgrep",
                    rule_id="sql-injection",
                    file_path="src/app.py",
                    line=42,
                    original_severity=Severity.HIGH,
                    triaged_severity=Severity.HIGH,
                    explanation="User input in raw SQL query",
                    priority=1,
                ),
                TriagedFinding(
                    fingerprint="fp2",
                    scanner="bandit",
                    rule_id="B105",
                    file_path="src/auth.py",
                    line=18,
                    original_severity=Severity.MEDIUM,
                    triaged_severity=Severity.MEDIUM,
                    explanation="Hardcoded password string",
                    priority=2,
                ),
            ],
        },
        "scanner_statuses": {
            "security": [
                ScannerStatus(scanner="semgrep", ok=True, finding_count=1),
                ScannerStatus(scanner="bandit", ok=True, finding_count=1),
                ScannerStatus(scanner="gitleaks", ok=False, error="timeout", error_type="timeout"),
            ],
        },
        "agent_notes": {
            "security": ["Triage complete"],
            "quality": ["1 finding"],
            "test_gap": ["2 gaps found"],
            "documentation": ["1 docstring missing"],
        },
        "agent_outcomes": {
            "security": AgentOutcome.OK.value,
            "quality": AgentOutcome.OK.value,
            "test_gap": AgentOutcome.OK.value,
            "documentation": AgentOutcome.OK.value,
        },
        "quality_result": {
            "quality": {
                "findings": [
                    {
                        "file_path": "src/utils.py",
                        "line": 55,
                        "rule_violated": "max-function-length",
                        "explanation": "Function exceeds 50 lines",
                        "severity": "medium",
                        "cited_passage": "Functions must not exceed 50 lines",
                        "source_file": "standards.md",
                        "symbol": "long_helper",
                    }
                ],
                "notes": ["1 finding"],
                "outcome": AgentOutcome.OK.value,
                "failure_reason": None,
            }
        },
        "test_gap_result": {
            "test_gap": {
                "gaps": [
                    {
                        "function": {
                            "name": "execute_query",
                            "file_path": "src/app.py",
                            "start_line": 40,
                            "end_line": 60,
                            "source": "def execute_query(): ...",
                            "is_method": False,
                            "class_name": None,
                            "complexity": 5,
                            "params": ["query"],
                            "return_annotation": None,
                        },
                        "risk_score": 8,
                    },
                    {
                        "function": {
                            "name": "helper",
                            "file_path": "src/utils.py",
                            "start_line": 10,
                            "end_line": 15,
                            "source": "def helper(): ...",
                            "is_method": False,
                            "class_name": None,
                            "complexity": 1,
                            "params": [],
                            "return_annotation": None,
                        },
                        "risk_score": 3,
                    },
                ],
                "drafted_tests": [
                    {
                        "target_function": "execute_query",
                        "target_file": "src/app.py",
                        "test_code": "def test_execute_query(): pass",
                        "imports_valid": True,
                    }
                ],
                "notes": ["2 gaps found"],
            }
        },
        "doc_result": {
            "documentation": {
                "flagged_functions": [
                    {
                        "function": {
                            "name": "calculate",
                            "file_path": "src/utils.py",
                            "start_line": 20,
                            "end_line": 30,
                            "source": "def calculate(x, y): ...",
                            "is_method": False,
                            "class_name": None,
                            "complexity": 2,
                            "params": ["x", "y"],
                            "return_annotation": None,
                        },
                        "reason": "missing",
                        "existing_docstring": None,
                    }
                ],
                "drafted_docstrings": [
                    {
                        "target_function": "calculate",
                        "target_file": "src/utils.py",
                        "docstring": "Calculate result from x and y.",
                        "params_valid": True,
                    }
                ],
                "notes": ["1 docstring missing"],
            }
        },
    }


def _quality_row(md: str) -> str:
    """The Agent Status table row for the Quality agent."""
    return next(
        line for line in md.splitlines()
        if line.startswith("| Quality ")
    )


class TestAggregation:
    def test_all_agents_produce_findings(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        # 2 security + 1 quality + 2 test_gap + 1 documentation = 6
        assert len(report.findings) == 6
        assert len(report.agent_statuses) == 4

    def test_severity_ranking_order(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        severities = [f.severity for f in report.findings]
        # High findings first, then medium, then low
        assert severities[0] == Severity.HIGH
        # All high should come before medium
        high_idx = [i for i, s in enumerate(severities) if s == Severity.HIGH]
        med_idx = [i for i, s in enumerate(severities) if s == Severity.MEDIUM]
        low_idx = [i for i, s in enumerate(severities) if s == Severity.LOW]
        if high_idx and med_idx:
            assert max(high_idx) < min(med_idx)
        if med_idx and low_idx:
            assert max(med_idx) < min(low_idx)

    def test_agent_priority_within_same_severity(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        # Among medium findings: security (B105) should come before quality, which
        # comes before test_gap
        medium_findings = [f for f in report.findings if f.severity == Severity.MEDIUM]
        agents_in_order = [f.agent for f in medium_findings]
        # security < quality < test_gap < documentation
        for i in range(len(agents_in_order) - 1):
            from backend.services.report_builder import _AGENT_PRIORITY
            assert _AGENT_PRIORITY[agents_in_order[i]] <= _AGENT_PRIORITY[agents_in_order[i + 1]]

    def test_fixable_findings_marked(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        fixable = [f for f in report.findings if f.fixable]
        # execute_query has a valid drafted test, calculate has a valid docstring
        assert len(fixable) == 2
        fixable_titles = {f.title for f in fixable}
        assert "Untested: execute_query" in fixable_titles
        assert "Docstring missing: calculate" in fixable_titles

    def test_unfixable_when_imports_invalid(self):
        state = _state_with_all_agents()
        # Override: mark the drafted test as having invalid imports
        state["test_gap_result"]["test_gap"]["drafted_tests"][0]["imports_valid"] = False
        report = aggregate(state)

        fixable = [f for f in report.findings if f.fixable]
        # Only the docstring should be fixable now
        assert len(fixable) == 1
        assert fixable[0].title == "Docstring missing: calculate"

    def test_fixable_count_property(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        assert report.fixable_count == 2

    def test_agent_status_captures_scanner_info(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        sec_status = next(s for s in report.agent_statuses if s.name == "security")
        assert sec_status.succeeded is True
        assert "gitleaks failed" in sec_status.scanner_info

    def test_failed_agent_status(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.FAILED.value
        state["agent_notes"]["quality"] = ["Agent failed: ChromaDB unreachable"]
        state["quality_result"]["quality"]["findings"] = []
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.FAILED.value
        state["quality_result"]["quality"]["failure_reason"] = "ChromaDB unreachable"
        report = aggregate(state)

        qual_status = next(s for s in report.agent_statuses if s.name == "quality")
        assert qual_status.outcome is AgentOutcome.FAILED
        assert qual_status.succeeded is False
        assert "ChromaDB unreachable" in qual_status.error_message

    def test_empty_state_no_findings(self):
        state: ReviewState = {
            "review_id": 1,
            "pr": PRMetadata("owner/repo", 1, "sha123"),
            "diff": "",
            "workspace_path": "/tmp/ws",
            "raw_findings": {},
            "triaged_findings": {},
            "scanner_statuses": {},
            "agent_notes": {},
            "quality_result": {},
            "test_gap_result": {},
            "doc_result": {},
        }
        report = aggregate(state)
        assert report.findings == []
        assert len(report.agent_statuses) == 4
        for s in report.agent_statuses:
            assert s.succeeded is True
            assert s.finding_count == 0

    def test_test_gap_risk_score_to_severity(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        tg_findings = [f for f in report.findings if f.agent == "test_gap"]
        # execute_query risk=8 → HIGH, helper risk=3 → LOW
        by_title = {f.title: f for f in tg_findings}
        assert by_title["Untested: execute_query"].severity == Severity.HIGH
        assert by_title["Untested: helper"].severity == Severity.LOW

    def test_documentation_reason_to_severity(self):
        state = _state_with_all_agents()
        report = aggregate(state)

        doc_findings = [f for f in report.findings if f.agent == "documentation"]
        # "missing" → MEDIUM
        assert doc_findings[0].severity == Severity.MEDIUM


# --------------------------------------------------------------------------- #
# Agent status accuracy
#
# "0 findings" is ambiguous: clean for an agent that ran, unknown for one that
# could not. The status must come from the structured outcome, never from note
# text, which is written for humans and will be rephrased.
# --------------------------------------------------------------------------- #


class TestAgentStatusAccuracy:
    def test_degraded_agent_is_not_reported_as_succeeded(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["findings"] = []
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["failure_reason"] = (
            "No coding-standards context retrieved: collection missing"
        )
        report = aggregate(state)

        qual = next(s for s in report.agent_statuses if s.name == "quality")
        assert qual.outcome is AgentOutcome.DEGRADED
        assert qual.succeeded is False
        assert "collection missing" in qual.error_message

    def test_degraded_agent_never_renders_a_check_mark(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["findings"] = []
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["failure_reason"] = "ChromaDB unreachable"
        md = format_pr_comment(aggregate(state), pr_number=99)

        row = _quality_row(md)
        assert "\u2705" not in row  # no check mark
        assert "\u26a0" in row  # warning sign
        assert "could not run" in row
        assert "ChromaDB unreachable" in row
        # A count of 0 would read as "clean"; it must not be shown as a number.
        assert "| 0 |" not in row

    def test_failed_agent_never_renders_a_check_mark(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.FAILED.value
        state["quality_result"]["quality"]["findings"] = []
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.FAILED.value
        md = format_pr_comment(aggregate(state), pr_number=99)

        row = _quality_row(md)
        assert "\u2705" not in row
        assert "\u274c" in row
        assert "failed" in row

    def test_agent_that_ran_clean_shows_check_mark_and_zero(self):
        state = _state_with_all_agents()
        state["quality_result"]["quality"]["findings"] = []
        md = format_pr_comment(aggregate(state), pr_number=99)

        row = _quality_row(md)
        assert "\u2705" in row
        assert "| 0 |" in row
        assert "could not run" not in row

    def test_note_wording_alone_does_not_mark_an_agent_failed(self):
        """Status is structural: rephrasing a note must not change the outcome."""
        state = _state_with_all_agents()
        state["agent_notes"]["quality"] = ["Agent failed: totally different wording"]
        report = aggregate(state)

        qual = next(s for s in report.agent_statuses if s.name == "quality")
        assert qual.outcome is AgentOutcome.OK
        assert qual.succeeded is True

    def test_status_line_distinguishes_degraded_from_failed(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.DEGRADED.value
        state["agent_outcomes"]["test_gap"] = AgentOutcome.FAILED.value
        md = format_pr_comment(aggregate(state), pr_number=99)

        assert "2/4 agents succeeded" in md
        assert "1 could not run" in md
        assert "1 failed" in md

    def test_incomplete_review_is_called_out_next_to_the_counts(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["quality"] = AgentOutcome.DEGRADED.value
        state["quality_result"]["quality"]["outcome"] = AgentOutcome.DEGRADED.value
        md = format_pr_comment(aggregate(state), pr_number=99)

        assert "Incomplete review" in md
        assert "Quality" in md

    def test_all_ok_has_no_incomplete_banner(self):
        state = _state_with_all_agents()
        md = format_pr_comment(aggregate(state), pr_number=99)
        assert "Incomplete review" not in md

    def test_security_degraded_when_every_scanner_failed(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["security"] = AgentOutcome.DEGRADED.value
        state["triaged_findings"]["security"] = []
        state["scanner_statuses"]["security"] = [
            ScannerStatus(scanner="semgrep", ok=False, error="x", error_type="E"),
            ScannerStatus(scanner="bandit", ok=False, error="x", error_type="E"),
            ScannerStatus(scanner="gitleaks", ok=False, error="x", error_type="E"),
        ]
        md = format_pr_comment(aggregate(state), pr_number=99)

        row = next(l for l in md.splitlines() if l.startswith("| Security "))
        assert "\u2705" not in row
        assert "\u26a0" in row


class TestFormatPRComment:
    def test_contains_pr_number(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99, commit_sha="deadbeef")
        assert "PR #99" in md

    def test_contains_commit_sha(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99, commit_sha="deadbeef")
        assert "`deadbee`" in md

    def test_contains_agent_status_table(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "### Agent Status" in md
        assert "Security" in md
        assert "Quality" in md
        assert "Test Gap" in md
        assert "Documentation" in md

    def test_contains_findings_table(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "### Findings" in md
        assert "sql-injection" in md

    def test_contains_autofix_section_when_fixable(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "Auto-Fix Available" in md

    def test_no_autofix_section_when_nothing_fixable(self):
        state = _state_with_all_agents()
        # Remove all drafted tests/docstrings
        state["test_gap_result"]["test_gap"]["drafted_tests"] = []
        state["doc_result"]["documentation"]["drafted_docstrings"] = []
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "Auto-Fix Available" not in md

    def test_no_findings_message(self):
        state: ReviewState = {
            "review_id": 1,
            "pr": PRMetadata("owner/repo", 1, "sha123"),
            "diff": "",
            "workspace_path": "/tmp/ws",
            "raw_findings": {},
            "triaged_findings": {},
            "scanner_statuses": {},
            "agent_notes": {},
            "quality_result": {},
            "test_gap_result": {},
            "doc_result": {},
        }
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=1)
        assert "No issues found" in md

    def test_partial_failure_shows_in_status(self):
        state = _state_with_all_agents()
        state["agent_outcomes"]["security"] = AgentOutcome.FAILED.value
        state["agent_notes"]["security"] = ["Agent failed: semgrep not installed"]
        state["triaged_findings"]["security"] = []
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "\u274c" in md

    def test_summary_counts_by_severity(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "high-severity" in md
        assert "medium-severity" in md

    def test_generated_by_footer(self):
        state = _state_with_all_agents()
        report = aggregate(state)
        md = format_pr_comment(report, pr_number=99)
        assert "Generated by CodeGuardian AI" in md


class TestSortKey:
    def test_critical_before_high(self):
        critical = UnifiedFinding(agent="security", severity=Severity.CRITICAL, title="a", detail="")
        high = UnifiedFinding(agent="security", severity=Severity.HIGH, title="b", detail="")
        assert _sort_key(critical) < _sort_key(high)

    def test_same_severity_security_before_quality(self):
        sec = UnifiedFinding(agent="security", severity=Severity.MEDIUM, title="a", detail="")
        qual = UnifiedFinding(agent="quality", severity=Severity.MEDIUM, title="b", detail="")
        assert _sort_key(sec) < _sort_key(qual)

    def test_same_severity_same_agent_sort_by_file(self):
        a = UnifiedFinding(agent="security", severity=Severity.HIGH, title="x", detail="", file_path="a.py", line=1)
        b = UnifiedFinding(agent="security", severity=Severity.HIGH, title="y", detail="", file_path="b.py", line=1)
        assert _sort_key(a) < _sort_key(b)

    def test_same_file_sort_by_line(self):
        a = UnifiedFinding(agent="security", severity=Severity.HIGH, title="x", detail="", file_path="a.py", line=5)
        b = UnifiedFinding(agent="security", severity=Severity.HIGH, title="y", detail="", file_path="a.py", line=10)
        assert _sort_key(a) < _sort_key(b)
