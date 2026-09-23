"""Tests for the Security Agent."""

from __future__ import annotations

import json
import os

from backend.agents.security_agent import SecurityAgent
from backend.agents.state import PRMetadata
from backend.services.report_builder import aggregate, format_pr_comment
from backend.tools.llm_client import LLMError
from backend.tools.results import RawFinding, ScannerOutputError, Severity


def _finding(scanner: str, rule: str, line: int) -> RawFinding:
    return RawFinding(
        scanner=scanner,
        rule_id=rule,
        message=f"{rule} issue",
        severity=Severity.MEDIUM,
        file_path=f"{scanner}.py",
        line=line,
    )


def _finding_at(rule: str, file_path: str, line: int) -> RawFinding:
    """A finding at an explicit path/line, for diff-scoping tests."""
    return RawFinding(
        scanner="bandit",
        rule_id=rule,
        message=f"{rule} issue",
        severity=Severity.MEDIUM,
        file_path=file_path,
        line=line,
    )


class _FakeLLM:
    """Fake LLM client returning a preset completion.

    Records the call count and every prompt it received, so tests can assert on
    exactly what was — and was not — sent for triage.
    """

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.calls = 0
        self.prompts: list[dict] = []

    def complete(self, **kwargs) -> str:
        self.calls += 1
        self.prompts.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _EchoTriageLLM:
    """Triages whatever it is handed, reusing the real fingerprints it received.

    Needed wherever the agent rewrites finding paths: the fingerprint is derived
    from the path, so a test cannot know it in advance.
    """

    def __init__(self, severity: str = "high") -> None:
        self.severity = severity
        self.calls = 0
        self.prompts: list[dict] = []

    def complete(self, **kwargs) -> str:
        self.calls += 1
        self.prompts.append(kwargs)
        incoming = json.loads(kwargs["user_prompt"])
        return json.dumps({
            "findings": [
                {
                    "fingerprint": item["fingerprint"],
                    "triaged_severity": self.severity,
                    "explanation": "echoed",
                    "priority": 1,
                }
                for item in incoming
            ]
        })


def _agent(*, semgrep=None, bandit=None, gitleaks=None, llm=None) -> SecurityAgent:
    return SecurityAgent(
        semgrep_run=semgrep if semgrep is not None else (lambda p: []),
        bandit_run=bandit if bandit is not None else (lambda p: []),
        gitleaks_run=gitleaks if gitleaks is not None else (lambda p: []),
        llm_client=llm,
    )


def test_happy_path_triages_all_findings() -> None:
    f1 = _finding("semgrep", "rule-a", 1)
    f2 = _finding("bandit", "B101", 2)
    llm_response = json.dumps(
        {
            "findings": [
                {"fingerprint": f1.fingerprint, "triaged_severity": "high",
                 "explanation": "real risk", "priority": 1},
                {"fingerprint": f2.fingerprint, "triaged_severity": "low",
                 "explanation": "minor", "priority": 3},
            ]
        }
    )
    llm = _FakeLLM(llm_response)
    agent = _agent(semgrep=lambda p: [f1], bandit=lambda p: [f2], llm=llm)

    result = agent.run("workspace")

    assert llm.calls == 1
    assert len(result.raw_findings) == 2
    assert len(result.triaged_findings) == 2
    fps = {t.fingerprint for t in result.triaged_findings}
    assert fps == {f1.fingerprint, f2.fingerprint}
    high = next(t for t in result.triaged_findings if t.fingerprint == f1.fingerprint)
    assert high.triaged_severity is Severity.HIGH
    assert high.original_severity is Severity.MEDIUM


def test_hallucinated_finding_is_dropped() -> None:
    f1 = _finding("semgrep", "rule-a", 1)
    llm_response = json.dumps(
        {
            "findings": [
                {"fingerprint": f1.fingerprint, "triaged_severity": "high",
                 "explanation": "real", "priority": 1},
                {"fingerprint": "deadbeefcafe", "triaged_severity": "critical",
                 "explanation": "INVENTED", "priority": 1},
            ]
        }
    )
    llm = _FakeLLM(llm_response)
    agent = _agent(semgrep=lambda p: [f1], llm=llm)

    result = agent.run("workspace")

    # Only the real finding survives; the invented one is dropped.
    assert len(result.triaged_findings) == 1
    assert result.triaged_findings[0].fingerprint == f1.fingerprint
    assert any("unverifiable" in n.lower() or "dropped" in n.lower() for n in result.notes)


def test_partial_scanner_failure_still_returns_results() -> None:
    f_ok = _finding("bandit", "B101", 5)

    def _failing_semgrep(_path):
        raise ScannerOutputError("semgrep", "malformed output")

    llm = _FakeLLM(json.dumps({"findings": [
        {"fingerprint": f_ok.fingerprint, "triaged_severity": "medium",
         "explanation": "ok", "priority": 2}
    ]}))
    agent = _agent(semgrep=_failing_semgrep, bandit=lambda p: [f_ok], llm=llm)

    result = agent.run("workspace")

    assert "semgrep" in result.failed_scanners
    assert "bandit" in result.succeeded_scanners
    # The review still produced findings despite one scanner failing.
    assert len(result.raw_findings) == 1
    assert len(result.triaged_findings) == 1
    # A failed scanner is clearly recorded with its error type.
    semgrep_status = next(s for s in result.scanner_statuses if s.scanner == "semgrep")
    assert semgrep_status.ok is False
    assert semgrep_status.error_type == "ScannerOutputError"


def test_no_findings_skips_llm() -> None:
    llm = _FakeLLM("should not be called")
    agent = _agent(llm=llm)  # all scanners return []

    result = agent.run("workspace")

    assert llm.calls == 0
    assert result.raw_findings == []
    assert result.triaged_findings == []
    assert any("triage skipped" in n.lower() for n in result.notes)


def test_llm_failure_keeps_raw_findings() -> None:
    f1 = _finding("semgrep", "rule-a", 1)
    llm = _FakeLLM(LLMError("groq exploded"))
    agent = _agent(semgrep=lambda p: [f1], llm=llm)

    result = agent.run("workspace")

    # Review is not failed; raw findings preserved, no triaged findings.
    assert len(result.raw_findings) == 1
    assert result.triaged_findings == []
    assert any("triage failed" in n.lower() for n in result.notes)


def test_llm_response_with_code_fence_is_parsed() -> None:
    f1 = _finding("semgrep", "rule-a", 1)
    fenced = (
        "```json\n"
        + json.dumps({"findings": [
            {"fingerprint": f1.fingerprint, "triaged_severity": "high",
             "explanation": "x", "priority": 1}
        ]})
        + "\n```"
    )
    agent = _agent(semgrep=lambda p: [f1], llm=_FakeLLM(fenced))
    result = agent.run("workspace")
    assert len(result.triaged_findings) == 1


# --------------------------------------------------------------------------- #
# Diff scoping
#
# The scanners are directory-oriented and always cover the whole workspace, so on
# any repository that already contains code most of what they return predates the
# PR. Only findings landing inside the PR's diff hunks belong to this review.
# --------------------------------------------------------------------------- #

# Touches changed.py lines 10-12 only. old.py does not appear in the diff at all.
_DIFF = """diff --git a/changed.py b/changed.py
--- a/changed.py
+++ b/changed.py
@@ -9,3 +10,3 @@ def existing():
-    old_line()
+    new_line_one()
+    new_line_two()
+    new_line_three()
"""


def test_findings_outside_diff_never_reach_llm_or_result() -> None:
    in_scope = _finding_at("B608", "changed.py", 11)
    outside_hunk = _finding_at("B101", "changed.py", 400)
    other_file = _finding_at("B105", "old.py", 11)

    llm = _FakeLLM(
        json.dumps(
            {
                "findings": [
                    {"fingerprint": in_scope.fingerprint, "triaged_severity": "high",
                     "explanation": "introduced by this PR", "priority": 1},
                ]
            }
        )
    )
    agent = _agent(bandit=lambda p: [in_scope, outside_hunk, other_file], llm=llm)

    result = agent.run("workspace", _DIFF)

    # Only the in-scope finding survives the filter.
    assert [f.fingerprint for f in result.raw_findings] == [in_scope.fingerprint]
    assert [t.fingerprint for t in result.triaged_findings] == [in_scope.fingerprint]

    # The out-of-scope findings were never offered to the LLM for triage.
    payload = llm.prompts[0]["user_prompt"]
    assert in_scope.fingerprint in payload
    assert outside_hunk.fingerprint not in payload
    assert other_file.fingerprint not in payload

    # Scanner status reflects what this review actually reports, and being out of
    # scope is not an error.
    bandit_status = next(s for s in result.scanner_statuses if s.scanner == "bandit")
    assert bandit_status.ok is True
    assert bandit_status.finding_count == 1
    assert result.failed_scanners == []


def test_absolute_scanner_paths_are_matched_against_the_diff() -> None:
    """Bandit/Semgrep echo absolute paths; diff headers are repo-relative."""
    workspace = os.path.abspath(os.path.join(os.sep, "ws"))
    abs_finding = _finding_at("B608", os.path.join(workspace, "changed.py"), 11)
    agent = _agent(bandit=lambda p: [abs_finding], llm=_FakeLLM("{}"))

    result = agent.run(workspace, _DIFF)

    # The finding is retained (matched against the diff) and its path is rewritten,
    # so identity is asserted on the rule/line rather than the path-derived
    # fingerprint.
    assert len(result.raw_findings) == 1
    assert result.raw_findings[0].rule_id == "B608"
    assert result.raw_findings[0].line == 11
    assert result.raw_findings[0].file_path == "changed.py"


def test_all_findings_out_of_scope_skips_llm_without_failing() -> None:
    llm = _FakeLLM("should not be called")
    agent = _agent(bandit=lambda p: [_finding_at("B101", "untouched.py", 3)], llm=llm)

    result = agent.run("workspace", _DIFF)

    assert result.raw_findings == []
    assert llm.calls == 0
    # Out-of-scope findings are not a scanner failure.
    assert result.failed_scanners == []


def test_missing_diff_disables_scoping() -> None:
    """No diff means report everything rather than silently suppress everything."""
    f1 = _finding_at("B101", "anywhere.py", 999)
    agent = _agent(bandit=lambda p: [f1], llm=_FakeLLM("{}"))

    result = agent.run("workspace")

    assert [f.fingerprint for f in result.raw_findings] == [f1.fingerprint]


# --------------------------------------------------------------------------- #
# Path normalization
#
# Bandit and Semgrep echo back the absolute temp-checkout path they were handed.
# Left alone it is persisted and published in a public PR comment, where it is
# meaningless to readers and needlessly discloses the review host's filesystem.
# --------------------------------------------------------------------------- #


def test_absolute_paths_are_normalized_to_workspace_relative() -> None:
    workspace = os.path.abspath(os.path.join(os.sep, "tmp", "codeguardian_abc123"))
    bandit_finding = _finding_at(
        "B608", os.path.join(workspace, "pkg", "app.py"), 21
    )
    # Gitleaks already reports workspace-relative paths; they must pass through.
    gitleaks_finding = RawFinding(
        scanner="gitleaks",
        rule_id="aws-access-token",
        message="secret",
        severity=Severity.HIGH,
        file_path="pkg/app.py",
        line=11,
    )
    llm = _EchoTriageLLM()
    agent = _agent(
        bandit=lambda p: [bandit_finding],
        gitleaks=lambda p: [gitleaks_finding],
        llm=llm,
    )

    result = agent.run(workspace)

    paths = sorted(f.file_path for f in result.raw_findings)
    assert paths == ["pkg/app.py", "pkg/app.py"]
    for finding in result.raw_findings:
        assert not os.path.isabs(finding.file_path)
        assert workspace not in finding.file_path

    # The normalized path is what reaches triage, and therefore the report/DB.
    assert len(result.triaged_findings) == 2
    for triaged in result.triaged_findings:
        assert triaged.file_path == "pkg/app.py"

    # The absolute path is never even shown to the LLM.
    assert workspace not in llm.prompts[0]["user_prompt"]


def test_no_absolute_path_reaches_the_final_report() -> None:
    """End-to-end guard: absolute paths must not survive into the PR comment."""
    workspace = os.path.abspath(os.path.join(os.sep, "tmp", "codeguardian_xyz789"))
    findings = [
        _finding_at("B608", os.path.join(workspace, "pkg", "app.py"), 21),
        RawFinding(
            scanner="semgrep",
            rule_id="python-dangerous-eval",
            message="eval",
            severity=Severity.HIGH,
            file_path=os.path.join(workspace, "pkg", "app.py"),
            line=28,
        ),
    ]
    agent = _agent(
        bandit=lambda p: [findings[0]],
        semgrep=lambda p: [findings[1]],
        llm=_EchoTriageLLM(),
    )
    result = agent.run(workspace)

    state = {
        "review_id": 1,
        "pr": PRMetadata("owner/repo", 7, "sha", ["pkg/app.py"]),
        "diff": "",
        "workspace_path": workspace,
        "raw_findings": {"security": result.raw_findings},
        "triaged_findings": {"security": result.triaged_findings},
        "scanner_statuses": {"security": result.scanner_statuses},
        "agent_notes": {"security": result.notes},
        "quality_result": {},
        "test_gap_result": {},
        "doc_result": {},
    }
    report = aggregate(state)
    markdown = format_pr_comment(report, pr_number=7, commit_sha="deadbeef")

    assert workspace not in markdown
    assert "codeguardian_xyz789" not in markdown
    # Windows drive-letter and POSIX temp roots must both be absent.
    assert ":\\" not in markdown
    assert "/tmp/" not in markdown
    # The findings themselves are still reported, at relative locations.
    assert "`pkg/app.py:21`" in markdown
    assert "`pkg/app.py:28`" in markdown


# --------------------------------------------------------------------------- #
# Structured outcome
#
# Scanners succeeding is not the same as the agent succeeding. If triage fails,
# real raw findings exist but none are reported, and "OK / 0" reads as "clean".
# Observed for real: Groq's free-tier TPM cap rate-limited the triage call while
# four agents ran in parallel, all three scanners had succeeded, and the review
# reported zero security findings under a green check.
# --------------------------------------------------------------------------- #

from backend.agents.state import AgentOutcome, SecurityAgentResult  # noqa: E402
from backend.tools.llm_client import LLMRateLimitError  # noqa: E402


def _seven_raw_findings() -> list[RawFinding]:
    """A realistic scanner haul: the shape review 9 actually produced."""
    return [
        _finding_at("B608", "pkg/app.py", 21),
        _finding_at("B307", "pkg/app.py", 28),
        _finding_at("B105", "pkg/app.py", 12),
        _finding_at("B105", "pkg/app.py", 13),
        RawFinding(scanner="semgrep", rule_id="python-dangerous-eval",
                   message="eval", severity=Severity.HIGH,
                   file_path="pkg/app.py", line=28),
        RawFinding(scanner="gitleaks", rule_id="aws-access-token",
                   message="aws key", severity=Severity.HIGH,
                   file_path="pkg/app.py", line=11),
        RawFinding(scanner="gitleaks", rule_id="generic-api-key",
                   message="api key", severity=Severity.HIGH,
                   file_path="pkg/app.py", line=13),
    ]


class TestSecurityAgentOutcome:
    def test_successful_triage_is_ok(self) -> None:
        f1 = _finding("semgrep", "rule-a", 1)
        llm = _FakeLLM(json.dumps({"findings": [
            {"fingerprint": f1.fingerprint, "triaged_severity": "high",
             "explanation": "x", "priority": 1}
        ]}))
        result = _agent(semgrep=lambda p: [f1], llm=llm).run("workspace")

        assert result.outcome is AgentOutcome.OK
        assert result.failure_reason is None

    def test_rate_limited_triage_is_degraded_not_ok(self) -> None:
        """Replay of the real failure: 7 scanner findings, triage 429, 0 reported."""
        raw = _seven_raw_findings()
        llm = _FakeLLM(LLMRateLimitError(
            "rate limited after 4 attempts: Error code: 429 - tokens per minute"
        ))
        agent = _agent(bandit=lambda p: raw, llm=llm)

        result = agent.run("workspace")

        # Nothing is reported, because nothing was triaged.
        assert result.triaged_findings == []
        # But the scanners did succeed, so the raw evidence is retained as context.
        assert len(result.raw_findings) == 7
        assert result.failed_scanners == []
        # And the outcome must say so rather than claiming a clean run.
        assert result.outcome is AgentOutcome.DEGRADED
        assert "LLMRateLimitError" in result.failure_reason
        assert "7 scanner finding(s) left untriaged" in result.failure_reason
        note = " ".join(result.notes).lower()
        assert "not reported as findings" in note
        assert "does not cover security" in note

    def test_unparseable_triage_response_is_degraded(self) -> None:
        raw = _seven_raw_findings()
        result = _agent(bandit=lambda p: raw, llm=_FakeLLM("not json at all")).run("ws")

        assert result.outcome is AgentOutcome.DEGRADED
        assert "usable JSON" in result.failure_reason
        assert result.triaged_findings == []
        assert len(result.raw_findings) == 7

    def test_unconfigured_llm_is_degraded(self, monkeypatch) -> None:
        from backend.tools.llm_client import LLMConfigError

        def _no_key(*_args, **_kwargs):
            raise LLMConfigError("No Groq API key configured")

        # Patch the constructor rather than relying on the ambient environment: a
        # real GROQ_API_KEY in .env would otherwise make this test hit the network.
        monkeypatch.setattr(
            "backend.agents.security_agent.LLMClient", _no_key
        )
        raw = _seven_raw_findings()

        result = _agent(bandit=lambda p: raw, llm=None).run("workspace")

        assert result.outcome is AgentOutcome.DEGRADED
        assert "not configured" in result.failure_reason

    def test_clean_scan_with_no_findings_stays_ok(self) -> None:
        """Zero raw findings is a genuine clean result, not a degraded one."""
        result = _agent(llm=_FakeLLM("unused")).run("workspace")

        assert result.raw_findings == []
        assert result.outcome is AgentOutcome.OK

    def test_partial_scanner_failure_alone_stays_ok(self) -> None:
        """One scanner down is already reported per-scanner; the agent still ran."""
        f_ok = _finding("bandit", "B101", 5)
        llm = _FakeLLM(json.dumps({"findings": [
            {"fingerprint": f_ok.fingerprint, "triaged_severity": "medium",
             "explanation": "ok", "priority": 2}
        ]}))

        def _failing_semgrep(_path):
            raise ScannerOutputError("semgrep", "malformed output")

        result = _agent(
            semgrep=_failing_semgrep, bandit=lambda p: [f_ok], llm=llm
        ).run("workspace")

        assert result.outcome is AgentOutcome.OK


class TestSecurityNodeOutcome:
    """The supervisor must propagate the agent's own outcome, not assume OK."""

    def _run_node(self, agent_result):
        from unittest.mock import patch

        from backend.agents.supervisor import _run_security_node

        with patch("backend.agents.security_agent.SecurityAgent") as fake_cls:
            fake_cls.return_value.run.return_value = agent_result
            return _run_security_node({"workspace_path": "ws", "diff": "d"})

    def test_degraded_triage_propagates_to_agent_outcomes(self) -> None:
        raw = _seven_raw_findings()
        result = _agent(bandit=lambda p: raw, llm=_FakeLLM(
            LLMRateLimitError("429"))).run("workspace")
        assert result.outcome is AgentOutcome.DEGRADED

        state_update = self._run_node(result)

        assert state_update["agent_outcomes"]["security"] == "degraded"
        # Raw findings still flow into state as context.
        assert len(state_update["raw_findings"]["security"]) == 7
        assert state_update["triaged_findings"]["security"] == []

    def test_all_scanners_failing_is_degraded_even_without_triage(self) -> None:
        from backend.agents.state import ScannerStatus

        result = SecurityAgentResult(
            scanner_statuses=[
                ScannerStatus(scanner="semgrep", ok=False, error="x", error_type="E"),
                ScannerStatus(scanner="bandit", ok=False, error="x", error_type="E"),
                ScannerStatus(scanner="gitleaks", ok=False, error="x", error_type="E"),
            ]
        )

        state_update = self._run_node(result)

        assert state_update["agent_outcomes"]["security"] == "degraded"

    def test_healthy_run_propagates_ok(self) -> None:
        f1 = _finding("semgrep", "rule-a", 1)
        result = _agent(semgrep=lambda p: [f1], llm=_FakeLLM(json.dumps({
            "findings": [{"fingerprint": f1.fingerprint,
                          "triaged_severity": "high",
                          "explanation": "x", "priority": 1}]
        }))).run("workspace")

        state_update = self._run_node(result)

        assert state_update["agent_outcomes"]["security"] == "ok"
