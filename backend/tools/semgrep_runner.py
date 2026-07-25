"""Semgrep runner.

Runs Semgrep against a target path, parsing its JSON output into structured
:class:`RawFinding` objects. Parsing is separated from execution so it can be unit
tested directly. Failures raise typed :class:`ScannerError` subclasses.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.tools.results import (
    RawFinding,
    ScannerOutputError,
    Severity,
    run_process,
)

logger = logging.getLogger(__name__)

SCANNER = "semgrep"
DEFAULT_TIMEOUT = 300
_RULES_DIR = Path(__file__).resolve().parent / "semgrep_rules"
DEFAULT_CONFIG = str(_RULES_DIR)


def parse_output(stdout: str) -> list[RawFinding]:
    """Parse Semgrep ``--json`` output into findings.

    Raises:
        ScannerOutputError: the output is not valid Semgrep JSON.
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
            extra = item.get("extra", {}) or {}
            start = item.get("start", {}) or {}
            findings.append(
                RawFinding(
                    scanner=SCANNER,
                    rule_id=str(item.get("check_id", "unknown")),
                    message=str(extra.get("message", "")).strip(),
                    severity=Severity.normalize(extra.get("severity")),
                    file_path=item.get("path"),
                    line=start.get("line"),
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            # A single malformed result should not corrupt the whole parse, but we
            # must not silently drop it — surface it as a parse error.
            raise ScannerOutputError(
                SCANNER, f"malformed result entry: {exc}"
            ) from exc
    return findings


def run(
    target_path: str,
    *,
    config: str = DEFAULT_CONFIG,
    timeout: int = DEFAULT_TIMEOUT,
    executable: str = "semgrep",
) -> list[RawFinding]:
    """Run Semgrep against ``target_path`` and return structured findings.

    An empty list means a clean scan. Raises a :class:`ScannerError` subclass on
    any failure (executable missing, timeout, non-parseable output, or a fatal
    scanner error).
    """
    command = [
        executable,
        "--config",
        config,
        "--json",
        "--quiet",
        "--disable-version-check",
        target_path,
    ]
    proc = run_process(SCANNER, command, timeout=timeout)

    # Semgrep exits 0 (no findings) or 1 (findings found); both carry JSON on
    # stdout. Higher codes indicate a real error.
    if proc.returncode not in (0, 1):
        # Prefer a parseable JSON error message if present.
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerOutputError(
            SCANNER, f"semgrep exited {proc.returncode}: {detail[:500]}"
        )

    findings = parse_output(proc.stdout)
    logger.info("Semgrep scan complete: %d finding(s).", len(findings))
    return findings
