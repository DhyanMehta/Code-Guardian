"""Semgrep runner.

Runs Semgrep against a target path, parsing its JSON output into structured
:class:`RawFinding` objects. Parsing is separated from execution so it can be unit
tested directly. Failures raise typed :class:`ScannerError` subclasses.

Falls back to Docker (``returntocorp/semgrep``) when the native binary is missing
or blocked (e.g. Windows AppControl policy).
"""

from __future__ import annotations

import json
import logging
import shutil
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

SCANNER = "semgrep"
DEFAULT_TIMEOUT = 300
_RULES_DIR = Path(__file__).resolve().parent / "semgrep_rules"
DEFAULT_CONFIG = str(_RULES_DIR)
_DOCKER_IMAGE = "returntocorp/semgrep:latest"
_DOCKER_MOUNT = "/src"


def _strip_mount_prefix(file_path: str | None, prefix: str) -> str | None:
    """Rewrite a container path to a workspace-relative one.

    The Docker fallback bind-mounts the target directory at ``/src``, so Semgrep
    reports e.g. ``/src/pkg/app.py``. Downstream consumers compare these paths
    against repo-relative diff headers, so the mount point has to come back off.
    """
    if not file_path or not prefix:
        return file_path
    normalized = file_path.replace("\\", "/")
    marker = prefix.rstrip("/") + "/"
    if normalized.startswith(marker):
        return normalized[len(marker):]
    return file_path


def parse_output(stdout: str, *, path_prefix: str = "") -> list[RawFinding]:
    """Parse Semgrep ``--json`` output into findings.

    Args:
        stdout: Raw ``--json`` output.
        path_prefix: Container mount point to strip from reported paths (used by the
            Docker fallback). Empty means paths are used as reported.

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
                    file_path=_strip_mount_prefix(item.get("path"), path_prefix),
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


def _run_native(
    target_path: str,
    config: str,
    timeout: int,
    executable: str,
) -> list[RawFinding]:
    """Attempt to run Semgrep natively."""
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

    if proc.returncode not in (0, 1):
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerOutputError(
            SCANNER, f"semgrep exited {proc.returncode}: {detail[:500]}"
        )

    findings = parse_output(proc.stdout)
    logger.info("Semgrep scan complete (native): %d finding(s).", len(findings))
    return findings


def _run_docker(
    target_path: str,
    config: str,
    timeout: int,
) -> list[RawFinding]:
    """Run Semgrep via Docker as a fallback."""
    target = Path(target_path).resolve().as_posix()
    config_path = Path(config).resolve().as_posix()

    command = [
        "docker", "run", "--rm",
        "-v", f"{target}:{_DOCKER_MOUNT}",
        "-v", f"{config_path}:/rules",
        _DOCKER_IMAGE,
        "semgrep",
        "--config", "/rules",
        "--json",
        "--quiet",
        "--disable-version-check",
        _DOCKER_MOUNT,
    ]
    proc = run_process(SCANNER, command, timeout=timeout)

    if proc.returncode not in (0, 1):
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise ScannerOutputError(
            SCANNER, f"semgrep (docker) exited {proc.returncode}: {detail[:500]}"
        )

    # Paths come back prefixed with the bind mount; make them workspace-relative
    # so they line up with the native runner's output.
    findings = parse_output(proc.stdout, path_prefix=_DOCKER_MOUNT)
    logger.info("Semgrep scan complete (docker): %d finding(s).", len(findings))
    return findings


def run(
    target_path: str,
    *,
    config: str = DEFAULT_CONFIG,
    timeout: int = DEFAULT_TIMEOUT,
    executable: str = "semgrep",
) -> list[RawFinding]:
    """Run Semgrep against ``target_path`` and return structured findings.

    An empty list means a clean scan. Falls back to Docker when the native binary
    is missing or blocked. Raises a :class:`ScannerError` subclass on any failure.
    """
    try:
        return _run_native(target_path, config, timeout, executable)
    except (ScannerNotFoundError, ScannerExecutionError) as exc:
        if not shutil.which("docker"):
            raise
        logger.info(
            "Native semgrep unavailable (%s); falling back to Docker.", exc
        )
        return _run_docker(target_path, config, timeout)
