"""Gitleaks runner.

Runs the Gitleaks binary (secrets scanner) against a target directory. Gitleaks is
a compiled binary rather than a Python package, so a missing/one-executable binary
is reported distinctly (:class:`ScannerNotFoundError`) from a clean scan that simply
found zero secrets (an empty finding list).

Gitleaks exit-code convention used here:
    0  -> scan ran, no leaks found (clean)
    1  -> scan ran, leaks found (report written)
    >1 -> gitleaks itself errored
"""

from __future__ import annotations

import json
import logging
import os
import tempfile

from backend.tools.results import (
    RawFinding,
    ScannerExecutionError,
    ScannerOutputError,
    Severity,
    run_process,
)

logger = logging.getLogger(__name__)

SCANNER = "gitleaks"
DEFAULT_TIMEOUT = 300
# Gitleaks does not assign severities; a leaked secret is treated as high severity.
_SECRET_SEVERITY = Severity.HIGH


def parse_output(report_json: str) -> list[RawFinding]:
    """Parse a Gitleaks JSON report (a JSON array) into findings.

    An empty/whitespace report or the literal ``null`` is treated as zero findings.
    Raises:
        ScannerOutputError: the report is not valid Gitleaks JSON.
    """
    text = report_json.strip()
    if not text or text == "null":
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScannerOutputError(SCANNER, f"invalid JSON report: {exc}") from exc

    if not isinstance(data, list):
        raise ScannerOutputError(
            SCANNER, "unexpected JSON shape (expected a list of findings)"
        )

    findings: list[RawFinding] = []
    for item in data:
        try:
            rule = str(item.get("RuleID") or item.get("Rule") or "secret")
            desc = str(item.get("Description", "") or "Potential secret detected")
            findings.append(
                RawFinding(
                    scanner=SCANNER,
                    rule_id=rule,
                    message=desc.strip(),
                    severity=_SECRET_SEVERITY,
                    file_path=item.get("File"),
                    line=item.get("StartLine"),
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ScannerOutputError(
                SCANNER, f"malformed finding entry: {exc}"
            ) from exc
    return findings


def run(
    target_path: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    executable: str = "gitleaks",
) -> list[RawFinding]:
    """Run Gitleaks against ``target_path`` and return findings.

    An empty list means a clean scan (zero secrets). Raises:
        ScannerNotFoundError: the gitleaks binary is not present/executable.
        ScannerTimeoutError: the scan timed out.
        ScannerExecutionError: gitleaks exited with an error status (>1).
        ScannerOutputError: the JSON report could not be parsed.
    """
    fd, report_path = tempfile.mkstemp(prefix="gitleaks_", suffix=".json")
    os.close(fd)
    try:
        command = [
            executable,
            "detect",
            "--source",
            target_path,
            "--no-git",
            "--report-format",
            "json",
            "--report-path",
            report_path,
            "--exit-code",
            "1",
            "--no-banner",
        ]
        # A missing binary raises ScannerNotFoundError from run_process — distinct
        # from a clean scan below.
        proc = run_process(SCANNER, command, timeout=timeout)

        if proc.returncode == 0:
            logger.info("Gitleaks scan complete: no secrets found.")
            return []

        if proc.returncode == 1:
            try:
                with open(report_path, encoding="utf-8") as fh:
                    report = fh.read()
            except OSError as exc:
                raise ScannerOutputError(
                    SCANNER, f"could not read report file: {exc}"
                ) from exc
            findings = parse_output(report)
            logger.info("Gitleaks scan complete: %d secret(s).", len(findings))
            return findings

        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerExecutionError(
            SCANNER, f"gitleaks exited {proc.returncode}: {detail[:500]}"
        )
    finally:
        try:
            os.remove(report_path)
        except OSError:
            logger.debug("Could not remove gitleaks temp report %s", report_path)
