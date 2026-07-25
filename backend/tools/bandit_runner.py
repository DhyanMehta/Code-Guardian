"""Bandit runner.

Runs Bandit (Python security linter) against a target path, parsing its JSON
output into structured :class:`RawFinding` objects. Parsing is separated from
execution for testability. Failures raise typed :class:`ScannerError` subclasses.
"""

from __future__ import annotations

import json
import logging

from backend.tools.results import (
    RawFinding,
    ScannerOutputError,
    Severity,
    run_process,
)

logger = logging.getLogger(__name__)

SCANNER = "bandit"
DEFAULT_TIMEOUT = 300


def parse_output(stdout: str) -> list[RawFinding]:
    """Parse Bandit ``-f json`` output into findings.

    Raises:
        ScannerOutputError: the output is not valid Bandit JSON.
    """
    if not stdout.strip():
        raise ScannerOutputError(SCANNER, "empty output (expected JSON document)")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ScannerOutputError(SCANNER, f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict) or "results" not in data:
        raise ScannerOutputError(
            SCANNER, "unexpected JSON shape (missing 'results' key)"
        )

    findings: list[RawFinding] = []
    for item in data.get("results", []):
        try:
            findings.append(
                RawFinding(
                    scanner=SCANNER,
                    rule_id=str(item.get("test_id", "unknown")),
                    message=str(item.get("issue_text", "")).strip(),
                    severity=Severity.normalize(item.get("issue_severity")),
                    file_path=item.get("filename"),
                    line=item.get("line_number"),
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ScannerOutputError(
                SCANNER, f"malformed result entry: {exc}"
            ) from exc
    return findings


def run(
    target_path: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    executable: str = "bandit",
) -> list[RawFinding]:
    """Run Bandit recursively against ``target_path`` and return findings.

    An empty list means a clean scan. Raises a :class:`ScannerError` subclass on
    failure. Bandit exits 0 when no issues are found and 1 when issues are found;
    both produce JSON. Exit code 2 indicates a usage/internal error.
    """
    command = [executable, "-r", target_path, "-f", "json", "-q"]
    proc = run_process(SCANNER, command, timeout=timeout)

    if proc.returncode not in (0, 1):
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerOutputError(
            SCANNER, f"bandit exited {proc.returncode}: {detail[:500]}"
        )

    findings = parse_output(proc.stdout)
    logger.info("Bandit scan complete: %d finding(s).", len(findings))
    return findings
