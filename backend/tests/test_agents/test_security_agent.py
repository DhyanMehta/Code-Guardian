"""Tests for the Security Agent."""

from __future__ import annotations

import json

from backend.agents.security_agent import SecurityAgent
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


class _FakeLLM:
    """Fake LLM client returning a preset completion; records call count."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.calls = 0

    def complete(self, **kwargs) -> str:
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


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
