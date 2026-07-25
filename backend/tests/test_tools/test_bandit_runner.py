"""Tests for the Bandit runner."""

from __future__ import annotations

import json

import pytest

from backend.tools import bandit_runner
from backend.tools.results import ProcessOutput, ScannerOutputError, Severity

_SAMPLE = {
    "results": [
        {
            "test_id": "B602",
            "filename": "app/shell.py",
            "line_number": 5,
            "issue_text": "subprocess call with shell=True",
            "issue_severity": "HIGH",
            "issue_confidence": "HIGH",
        }
    ],
    "errors": [],
}


def test_parse_findings() -> None:
    findings = bandit_runner.parse_output(json.dumps(_SAMPLE))
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner == "bandit"
    assert f.rule_id == "B602"
    assert f.file_path == "app/shell.py"
    assert f.line == 5
    assert f.severity is Severity.HIGH


def test_parse_empty_results_is_clean() -> None:
    assert bandit_runner.parse_output(json.dumps({"results": []})) == []


def test_parse_malformed_raises() -> None:
    with pytest.raises(ScannerOutputError):
        bandit_runner.parse_output("<not json>")


def test_parse_wrong_shape_raises() -> None:
    with pytest.raises(ScannerOutputError):
        bandit_runner.parse_output(json.dumps([1, 2, 3]))


def test_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bandit_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(1, json.dumps(_SAMPLE), ""),
    )
    assert len(bandit_runner.run("path")) == 1


def test_run_clean_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bandit_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(0, json.dumps({"results": []}), ""),
    )
    assert bandit_runner.run("path") == []


def test_run_fatal_exit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bandit_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(2, "", "usage error"),
    )
    with pytest.raises(ScannerOutputError):
        bandit_runner.run("path")
