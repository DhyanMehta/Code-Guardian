"""Tests for the Semgrep runner."""

from __future__ import annotations

import json
import subprocess

import pytest

from backend.tools import semgrep_runner
from backend.tools.results import (
    ProcessOutput,
    ScannerNotFoundError,
    ScannerOutputError,
    ScannerTimeoutError,
    Severity,
)

_SAMPLE = {
    "results": [
        {
            "check_id": "python.lang.security.audit.dangerous-exec",
            "path": "app/x.py",
            "start": {"line": 12},
            "extra": {"message": "Detected exec usage", "severity": "ERROR"},
        }
    ],
    "errors": [],
}


def test_parse_findings() -> None:
    findings = semgrep_runner.parse_output(json.dumps(_SAMPLE))
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner == "semgrep"
    assert f.rule_id.endswith("dangerous-exec")
    assert f.file_path == "app/x.py"
    assert f.line == 12
    assert f.severity is Severity.HIGH  # ERROR -> HIGH
    assert f.fingerprint  # auto-computed


def test_parse_empty_results_is_clean() -> None:
    findings = semgrep_runner.parse_output(json.dumps({"results": [], "errors": []}))
    assert findings == []


def test_parse_malformed_json_raises() -> None:
    with pytest.raises(ScannerOutputError):
        semgrep_runner.parse_output("this is not json {")


def test_parse_wrong_shape_raises() -> None:
    with pytest.raises(ScannerOutputError):
        semgrep_runner.parse_output(json.dumps({"unexpected": True}))


def test_parse_empty_string_raises() -> None:
    with pytest.raises(ScannerOutputError):
        semgrep_runner.parse_output("   ")


def test_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semgrep_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(1, json.dumps(_SAMPLE), ""),
    )
    findings = semgrep_runner.run("some/path")
    assert len(findings) == 1


def test_run_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **k):
        raise ScannerNotFoundError("semgrep", "not found")

    monkeypatch.setattr(semgrep_runner, "run_process", _raise)
    with pytest.raises(ScannerNotFoundError):
        semgrep_runner.run("some/path")


def test_run_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **k):
        raise ScannerTimeoutError("semgrep", "timed out")

    monkeypatch.setattr(semgrep_runner, "run_process", _raise)
    with pytest.raises(ScannerTimeoutError):
        semgrep_runner.run("some/path")


def test_run_fatal_exit_code_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semgrep_runner,
        "run_process",
        lambda *a, **k: ProcessOutput(2, "", "fatal: bad config"),
    )
    with pytest.raises(ScannerOutputError):
        semgrep_runner.run("some/path")


def test_run_process_real_missing_binary() -> None:
    """The shared helper maps FileNotFoundError to ScannerNotFoundError."""
    from backend.tools.results import run_process

    with pytest.raises(ScannerNotFoundError):
        run_process("semgrep", ["definitely-not-a-real-binary-xyz"], timeout=5)


def test_run_docker_fallback_on_output_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves Docker fallback triggers when native semgrep fails with ScannerOutputError."""
    calls = []

    def _mock_run_native(*a, **k):
        raise ScannerOutputError("semgrep", "empty output (expected JSON document)")

    def _mock_run_docker(*a, **k):
        calls.append("docker")
        return []

    monkeypatch.setattr(semgrep_runner, "_run_native", _mock_run_native)
    monkeypatch.setattr(semgrep_runner, "_run_docker", _mock_run_docker)
    monkeypatch.setattr(semgrep_runner.shutil, "which", lambda x: "/usr/bin/docker")

    findings = semgrep_runner.run("some/path")
    assert findings == []
    assert calls == ["docker"]
