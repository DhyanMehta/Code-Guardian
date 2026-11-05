"""Explicit observations of agent work, independent of legacy outcome labels."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass
class Coverage:
    eligible_files: list[str] = field(default_factory=list)
    analyzed_files: list[str] = field(default_factory=list)
    excluded_files: list[dict] = field(default_factory=list)
    batches: dict = field(default_factory=lambda: {"completed": 0, "failed": 0, "reused": 0})
    execution: str = "running"
    status: str = "unknown"
    enrichment: str = "skipped"
    enrichment_counts: dict = field(default_factory=lambda: {"completed": 0, "skipped": 0, "failed": 0})
    findings: int = 0
    scanners: list[dict] = field(default_factory=list)

    def analyzed(self, paths):
        self.analyzed_files = sorted(set(self.analyzed_files).union(paths))

    def finish(self, outcome):
        self.execution = "failed" if outcome == "failed" else "completed"
        if self.execution == "failed":
            self.status = "partial" if self.analyzed_files else "unknown"
        elif not self.eligible_files:
            self.status = "not_applicable"
        elif (set(self.eligible_files) <= set(self.analyzed_files)
              and not self.batches["failed"] and outcome == "ok"):
            self.status = "partial" if self.excluded_files else "complete"
        else:
            self.status = "partial"


current: ContextVar[Coverage | None] = ContextVar("agent_coverage", default=None)


def observed(paths):
    coverage = current.get()
    if coverage:
        coverage.analyzed(paths)


def enrichment_failed():
    enrichment_observed("failed")


def enrichment_observed(status, count=1):
    coverage = current.get()
    if coverage:
        coverage.enrichment_counts[status] += count
        counts = coverage.enrichment_counts
        coverage.enrichment = "failed" if counts["failed"] else "skipped" if counts["skipped"] else "completed"


def batches_failed(count=1):
    coverage = current.get()
    if coverage:
        coverage.batches["failed"] += count


def classify(paths, agent):
    coverage = Coverage()
    for path in sorted(set(paths)):
        parts = PurePosixPath(path).parts
        suffix = PurePosixPath(path).suffix.lower()
        if agent == "security":
            # Gitleaks also scans non-code artifacts. Per-scanner source-language
            # applicability is recorded independently by the supervisor.
            coverage.eligible_files.append(path)
            continue
        if {"vendor", "node_modules", "generated"}.intersection(parts):
            reason = "Generated declaration or generated/vendor directory"
        elif path.endswith(".d.ts"):
            reason = "Type declaration file outside executable-source checks"
        elif agent == "test_gap" and (PurePosixPath(path).name.startswith("test_") or PurePosixPath(path).name.endswith("_test.py") or ".test." in path or ".spec." in path):
            reason = "Test source is reference input, not a production test-gap target"
        elif suffix not in {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            reason = "Artifact outside supported source-language checks"
        else:
            coverage.eligible_files.append(path)
            continue
        coverage.excluded_files.append({"path": path, "reason": reason})
    return coverage
