"""Shared typed results and errors for the deterministic security scanners.

Every scanner runner returns a list of :class:`RawFinding` on success (an empty
list is a valid "clean scan" result) and raises a typed :class:`ScannerError`
subclass on failure. Nothing is ever swallowed silently (see ``RULES.md`` #9).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    """Normalized severity levels across all scanners."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"

    @classmethod
    def normalize(cls, value: str | None) -> "Severity":
        """Map a scanner-specific severity string onto a :class:`Severity`."""
        if not value:
            return cls.UNKNOWN
        v = value.strip().lower()
        mapping = {
            "critical": cls.CRITICAL,
            "error": cls.HIGH,
            "high": cls.HIGH,
            "warning": cls.MEDIUM,
            "medium": cls.MEDIUM,
            "moderate": cls.MEDIUM,
            "low": cls.LOW,
            "note": cls.LOW,
            "info": cls.INFO,
            "informational": cls.INFO,
        }
        return mapping.get(v, cls.UNKNOWN)


@dataclass(frozen=True)
class RawFinding:
    """A single deterministic finding produced by a scanner.

    ``fingerprint`` is a stable identifier used to map an LLM's triage response
    back to a real finding; the LLM must never produce a fingerprint that is not
    present in the raw set.
    """

    scanner: str
    rule_id: str
    message: str
    severity: Severity
    file_path: str | None = None
    line: int | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:  # compute fingerprint if not supplied
        if not self.fingerprint:
            basis = f"{self.scanner}|{self.rule_id}|{self.file_path}|{self.line}|{self.message}"
            digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
            object.__setattr__(self, "fingerprint", digest)

    def to_prompt_dict(self) -> dict:
        """Compact, LLM-facing representation (only raw, factual fields)."""
        return {
            "fingerprint": self.fingerprint,
            "scanner": self.scanner,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class ScanResult:
    """Outcome of running one scanner: either succeeded (with findings) or failed."""

    scanner: str
    ok: bool
    findings: list[RawFinding] = field(default_factory=list)
    error: str | None = None
    error_type: str | None = None

    @classmethod
    def success(cls, scanner: str, findings: list[RawFinding]) -> "ScanResult":
        return cls(scanner=scanner, ok=True, findings=findings)

    @classmethod
    def failure(cls, scanner: str, error: "ScannerError") -> "ScanResult":
        return cls(
            scanner=scanner,
            ok=False,
            error=str(error),
            error_type=type(error).__name__,
        )


# --------------------------------------------------------------------------- #
# Typed exception hierarchy
# --------------------------------------------------------------------------- #
class ScannerError(Exception):
    """Base class for all scanner failures."""

    def __init__(self, scanner: str, message: str) -> None:
        self.scanner = scanner
        super().__init__(f"[{scanner}] {message}")


class ScannerNotFoundError(ScannerError):
    """The scanner executable/binary is not installed or not on PATH."""


class ScannerTimeoutError(ScannerError):
    """The scan exceeded its allotted time budget."""


class ScannerOutputError(ScannerError):
    """The scanner produced output that could not be parsed."""

    def __init__(self, scanner, message, *, partial_findings=None):
        super().__init__(scanner, message)
        self.partial_findings = partial_findings or []


class ScannerExecutionError(ScannerError):
    """The scanner exited with an unexpected/error status."""


# --------------------------------------------------------------------------- #
# Subprocess helper
# --------------------------------------------------------------------------- #
@dataclass
class ProcessOutput:
    """Result of a completed subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str


def _resolve_executable(name: str) -> str:
    """Resolve a scanner executable, preferring the active venv's Scripts dir.

    On Windows, subprocess.run won't find executables in the venv unless the full
    path is given or the venv is activated in the shell environment. This resolves
    pip-installed tools (bandit, semgrep) from the same interpreter prefix.
    """
    if Path(name).is_absolute():
        return name
    if shutil.which(name):
        return name
    # Look in the same Scripts/bin directory as the running Python
    scripts_dir = Path(sys.executable).parent
    for suffix in ("", ".exe"):
        candidate = scripts_dir / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)
    return name


def run_process(
    scanner: str,
    command: list[str],
    *,
    timeout: int,
    cwd: str | None = None,
) -> ProcessOutput:
    """Run ``command`` and return its output, translating failures to typed errors.

    Raises:
        ScannerNotFoundError: the executable was not found.
        ScannerTimeoutError: the process exceeded ``timeout`` seconds.
        ScannerExecutionError: the process could not be executed (OS error).
    """
    command = list(command)
    command[0] = _resolve_executable(command[0])
    try:
        completed = subprocess.run(  # noqa: S603 - command is built internally
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ScannerNotFoundError(
            scanner, f"executable not found: {command[0]!r} ({exc})"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ScannerTimeoutError(
            scanner, f"scan timed out after {timeout}s"
        ) from exc
    except OSError as exc:  # permission denied, not executable, etc.
        raise ScannerExecutionError(
            scanner, f"failed to execute {command[0]!r}: {exc}"
        ) from exc

    return ProcessOutput(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
