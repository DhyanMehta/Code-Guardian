"""Tests for the Gitleaks runner."""

from __future__ import annotations

import json

import pytest

from backend.tools import gitleaks_runner
from backend.tools.results import (
    ProcessOutput,
    ScannerExecutionError,
    ScannerNotFoundError,
    ScannerOutputError,
    Severity,
)

_SAMPLE = [
    {
        "RuleID": "generic-api-key",
        "Description": "Generic API Key",
        "File": "config/settings.py",
        "StartLine": 8,
        "Secret": "AKIA....",
    }
]


def test_parse_findings() -> None:
    findings = gitleaks_runner.parse_output(json.dumps(_SAMPLE))
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner == "gitleaks"
    assert f.rule_id == "generic-api-key"
    assert f.file_path == "config/settings.py"
    assert f.line == 8
    assert f.severity is Severity.HIGH  # secrets are treated as high


def test_parse_empty_and_null_are_clean() -> None:
    assert gitleaks_runner.parse_output("") == []
    assert gitleaks_runner.parse_output("   ") == []
    assert gitleaks_runner.parse_output("null") == []
    assert gitleaks_runner.parse_output("[]") == []


def test_parse_malformed_raises() -> None:
    with pytest.raises(ScannerOutputError):
        gitleaks_runner.parse_output("{not json")


def test_parse_wrong_shape_raises() -> None:
    with pytest.raises(ScannerOutputError):
        gitleaks_runner.parse_output(json.dumps({"findings": []}))


def test_run_clean_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gitleaks_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(0, "", ""),
    )
    assert gitleaks_runner.run("path") == []


def test_run_findings_exit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_process(scanner, command, *, timeout, cwd=None):
        # Emulate gitleaks writing its JSON report to the --report-path target.
        report_path = command[command.index("--report-path") + 1]
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(_SAMPLE, fh)
        return ProcessOutput(1, "", "")

    monkeypatch.setattr(gitleaks_runner, "run_process", _fake_run_process)
    findings = gitleaks_runner.run("path")
    assert len(findings) == 1
    assert findings[0].rule_id == "generic-api-key"


def test_run_missing_binary_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **k):
        raise ScannerNotFoundError("gitleaks", "binary not found")

    monkeypatch.setattr(gitleaks_runner, "run_process", _raise)
    with pytest.raises(ScannerNotFoundError):
        gitleaks_runner.run("path")


def test_run_error_exit_code_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gitleaks_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(2, "", "fatal error"),
    )
    with pytest.raises(ScannerExecutionError):
        gitleaks_runner.run("path")
