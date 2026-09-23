"""Gitleaks runner.

Runs the Gitleaks binary (secrets scanner) against a target directory. Gitleaks is
a compiled binary rather than a Python package, so a missing/one-executable binary
is reported distinctly (:class:`ScannerNotFoundError`) from a clean scan that simply
found zero secrets (an empty finding list).

Falls back to Docker (``zricethezav/gitleaks``) when the native binary is missing.

Gitleaks exit-code convention used here:
    0  -> scan ran, no leaks found (clean)
    1  -> scan ran, leaks found (report written)
    >1 -> gitleaks itself errored
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from backend.tools.results import (
    RawFinding,
    ScannerExecutionError,
    ScannerNotFoundError,
    ScannerOutputError,
    Severity,
    run_process,
)

logger = logging.getLogger(__name__)

SCANNER = "gitleaks"
DEFAULT_TIMEOUT = 300
_SECRET_SEVERITY = Severity.HIGH
_DOCKER_IMAGE = "zricethezav/gitleaks:latest"
_DOCKER_MOUNT = "/src"


def _strip_mount_prefix(file_path: str | None, prefix: str) -> str | None:
    """Rewrite a container path to a workspace-relative one.

    The Docker fallback bind-mounts the target directory at ``/src``, so Gitleaks
    reports e.g. ``/src/pkg/app.py`` where the native binary would report a path
    under the real workspace. Downstream consumers compare these paths against
    repo-relative diff headers, so the mount point has to come back off.
    """
    if not file_path or not prefix:
        return file_path
    normalized = file_path.replace("\\", "/")
    marker = prefix.rstrip("/") + "/"
    if normalized.startswith(marker):
        return normalized[len(marker):]
    return file_path


def parse_output(report_json: str, *, path_prefix: str = "") -> list[RawFinding]:
    """Parse a Gitleaks JSON report (a JSON array) into findings.

    An empty/whitespace report or the literal ``null`` is treated as zero findings.

    Args:
        report_json: Raw JSON report text.
        path_prefix: Container mount point to strip from reported paths (used by the
            Docker fallback). Empty means paths are used as reported.

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
                    file_path=_strip_mount_prefix(item.get("File"), path_prefix),
                    line=item.get("StartLine"),
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ScannerOutputError(
                SCANNER, f"malformed finding entry: {exc}"
            ) from exc
    return findings


def _run_native(
    target_path: str,
    timeout: int,
    executable: str,
) -> list[RawFinding]:
    """Attempt to run Gitleaks natively."""
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
        proc = run_process(SCANNER, command, timeout=timeout)

        if proc.returncode == 0:
            logger.info("Gitleaks scan complete (native): no secrets found.")
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
            logger.info("Gitleaks scan complete (native): %d secret(s).", len(findings))
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


def _run_docker(
    target_path: str,
    timeout: int,
) -> list[RawFinding]:
    """Run Gitleaks via Docker as a fallback."""
    target = Path(target_path).resolve().as_posix()

    fd, report_path = tempfile.mkstemp(prefix="gitleaks_docker_", suffix=".json")
    os.close(fd)
    report_dir = Path(report_path).parent.as_posix()
    report_name = Path(report_path).name

    try:
        command = [
            "docker", "run", "--rm",
            "-v", f"{target}:{_DOCKER_MOUNT}",
            "-v", f"{report_dir}:/out",
            _DOCKER_IMAGE,
            "detect",
            "--source", _DOCKER_MOUNT,
            "--no-git",
            "--report-format", "json",
            "--report-path", f"/out/{report_name}",
            "--exit-code", "1",
            "--no-banner",
        ]
        proc = run_process(SCANNER, command, timeout=timeout)

        if proc.returncode == 0:
            logger.info("Gitleaks scan complete (docker): no secrets found.")
            return []

        if proc.returncode == 1:
            try:
                with open(report_path, encoding="utf-8") as fh:
                    report = fh.read()
            except OSError as exc:
                raise ScannerOutputError(
                    SCANNER, f"could not read docker report file: {exc}"
                ) from exc
            # Paths come back prefixed with the bind mount; make them
            # workspace-relative so they line up with the native runner's output.
            findings = parse_output(report, path_prefix=_DOCKER_MOUNT)
            logger.info("Gitleaks scan complete (docker): %d secret(s).", len(findings))
            return findings

        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerExecutionError(
            SCANNER, f"gitleaks (docker) exited {proc.returncode}: {detail[:500]}"
        )
    finally:
        try:
            os.remove(report_path)
        except OSError:
            pass


def run(
    target_path: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    executable: str = "gitleaks",
) -> list[RawFinding]:
    """Run Gitleaks against ``target_path`` and return findings.

    An empty list means a clean scan (zero secrets). Falls back to Docker when the
    native binary is missing. Raises a :class:`ScannerError` subclass on failure.
    """
    try:
        return _run_native(target_path, timeout, executable)
    except (ScannerNotFoundError, ScannerExecutionError) as exc:
        if not shutil.which("docker"):
            raise
        logger.info(
            "Native gitleaks unavailable (%s); falling back to Docker.", exc
        )
        return _run_docker(target_path, timeout)
