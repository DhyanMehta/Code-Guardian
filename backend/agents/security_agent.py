"""Security Agent.

Runs the three deterministic scanners (Semgrep, Bandit, Gitleaks) against a PR's
changed files, then uses the LLM ONLY to triage / explain / severity-rank the raw
scanner output. Hard rules enforced here (see ``RULES.md`` #5, #6, #9):

* Only the raw scanner findings are sent to the LLM.
* Any LLM "finding" whose fingerprint does not map back to a real raw finding is
  dropped and logged — unverifiable findings never reach the output.
* If a scanner fails, the agent still returns the results of the scanners that
  succeeded, clearly marking which failed and why. One broken tool never fails the
  whole review.

The scanners themselves are directory-oriented and always cover the whole workspace.
Their raw findings are then narrowed to the diff hunks of the PR under review:
without that, reviewing a PR against any repository that already contains code
reports the entire pre-existing backlog as though this PR had introduced it. Findings
outside the diff are simply out of scope for this review — they are not errors, and
they never fail the run.

Scanner paths are also normalized to workspace-relative form as soon as they arrive.
Bandit and Semgrep echo back the absolute path they were handed, which is a
throwaway temp checkout directory; left alone it is persisted to the database and
published in a public PR comment, where it is both meaningless to readers and a
needless disclosure of the review host's filesystem layout.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from backend.agents._diff_utils import function_overlaps_diff, parse_diff_hunks
from backend.agents.state import (
    ScannerStatus,
    SecurityAgentResult,
    TriagedFinding,
)
from backend.tools import bandit_runner, gitleaks_runner, semgrep_runner
from backend.tools.llm_client import LLMClient, LLMConfigError, LLMError
from backend.tools.results import RawFinding, ScannerError, Severity

logger = logging.getLogger(__name__)

AGENT_NAME = "security"

RunnerFn = Callable[[str], list[RawFinding]]

_SYSTEM_PROMPT = (
    "You are a security triage assistant for a code review system. You will be "
    "given a JSON array of RAW findings produced by deterministic security scanners "
    "(Semgrep, Bandit, Gitleaks). Your ONLY job is to triage, explain, and "
    "severity-rank these findings.\n\n"
    "STRICT RULES:\n"
    "1. You MUST NOT invent, infer, or add any finding that is not in the input.\n"
    "2. Every object you return MUST reuse a 'fingerprint' value exactly as given in "
    "the input. Never fabricate a fingerprint.\n"
    "3. If you are unsure about a finding, keep it but explain the uncertainty.\n\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{"findings": [{"fingerprint": "<from input>", "triaged_severity": '
    '"critical|high|medium|low|info", "explanation": "<short plain-text>", '
    '"priority": <integer, 1=highest>}]}\n'
    "Do not include any prose outside the JSON object."
)


class SecurityAgent:
    """The Security Agent node."""

    def __init__(
        self,
        *,
        semgrep_run: RunnerFn = semgrep_runner.run,
        bandit_run: RunnerFn = bandit_runner.run,
        gitleaks_run: RunnerFn = gitleaks_runner.run,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._runners: dict[str, RunnerFn] = {
            "semgrep": semgrep_run,
            "bandit": bandit_run,
            "gitleaks": gitleaks_run,
        }
        self._llm = llm_client
        self._llm_provided = llm_client is not None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self, workspace_path: str, diff: str = "") -> SecurityAgentResult:
        """Scan ``workspace_path`` and return a triaged, typed result.

        Args:
            workspace_path: Root of the PR checkout, handed to every scanner as-is.
            diff: Unified diff for the PR. When supplied, raw findings are narrowed
                to the diff's hunks so only issues this PR actually touched are
                reported. When empty, no narrowing is applied.
        """
        result = SecurityAgentResult()
        hunks_by_file = self._parse_scope(diff)

        # 1. Run every scanner, tolerating individual failures.
        for scanner, runner in self._runners.items():
            try:
                findings = runner(workspace_path)
            except ScannerError as exc:
                logger.warning("Scanner '%s' failed: %s", scanner, exc)
                result.scanner_statuses.append(
                    ScannerStatus(
                        scanner=scanner,
                        ok=False,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                )
                continue

            # 2. Normalize paths before anything downstream sees, stores, or
            #    publishes them.
            findings = self._normalize_finding_paths(findings, workspace_path)

            # 3. Narrow to the PR's diff hunks.
            if hunks_by_file is not None:
                findings = self._scope_to_diff(
                    scanner, findings, workspace_path, hunks_by_file
                )

            result.raw_findings.extend(findings)
            result.scanner_statuses.append(
                ScannerStatus(scanner=scanner, ok=True, finding_count=len(findings))
            )

        if result.failed_scanners:
            result.notes.append(
                "Scanner(s) failed and were skipped: "
                + ", ".join(result.failed_scanners)
            )
            if len(result.failed_scanners) > len(result.succeeded_scanners):
                result.mark_degraded(
                    f"{len(result.failed_scanners)}/{len(self._runners)} scanners "
                    f"failed ({', '.join(result.failed_scanners)}); security coverage "
                    f"is incomplete."
                )

        # 4. Nothing to triage -> return raw results (no LLM call).
        if not result.raw_findings:
            result.notes.append("No raw findings; LLM triage skipped.")
            return result

        # 5. Triage the raw findings with the LLM (never fail the review on error).
        self._triage(result)
        return result

    # ------------------------------------------------------------------ #
    # Path normalization
    # ------------------------------------------------------------------ #
    @classmethod
    def _normalize_finding_paths(
        cls,
        findings: list[RawFinding],
        workspace_path: str,
    ) -> list[RawFinding]:
        """Rewrite every finding's path to workspace-relative POSIX form.

        Only the path changes; the finding is otherwise the scanner's verbatim
        output. The fingerprint is recomputed because it is derived from the path,
        and this runs before triage so the fingerprints the LLM sees stay
        self-consistent.
        """
        normalized: list[RawFinding] = []
        for finding in findings:
            rel_path = cls._workspace_relative(finding.file_path, workspace_path)
            if rel_path == finding.file_path:
                normalized.append(finding)
                continue
            normalized.append(
                replace(finding, file_path=rel_path, fingerprint="")
            )
        return normalized

    # ------------------------------------------------------------------ #
    # Diff scoping
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_scope(diff: str) -> dict[str, list[tuple[int, int]]] | None:
        """Parse ``diff`` into per-file hunk ranges, or ``None`` for no scoping.

        ``None`` means "report everything the scanners found". That is deliberate for
        a missing or unparseable diff: an empty scope would silently suppress every
        finding, whereas an unscoped result is noisy but never hides a real issue.
        """
        if not diff.strip():
            logger.warning(
                "No diff supplied to the Security Agent; findings will not be "
                "narrowed to the PR and may include pre-existing repository issues."
            )
            return None

        hunks = parse_diff_hunks(diff)
        if not hunks:
            logger.warning(
                "Diff supplied but no hunks could be parsed; skipping diff scoping."
            )
            return None
        return hunks

    @classmethod
    def _scope_to_diff(
        cls,
        scanner: str,
        findings: list[RawFinding],
        workspace_path: str,
        hunks_by_file: dict[str, list[tuple[int, int]]],
    ) -> list[RawFinding]:
        """Keep only the findings that land inside the PR's changed hunks.

        Findings are filtered, never rewritten or synthesised, so everything that
        survives is still verbatim scanner output (``RULES.md`` #5).
        """
        in_scope: list[RawFinding] = []
        for finding in findings:
            rel_path = cls._workspace_relative(finding.file_path, workspace_path)
            hunks = hunks_by_file.get(rel_path) if rel_path else None
            if not hunks:
                continue
            # A finding occupies a single line; reuse the shared overlap check by
            # treating it as a one-line range.
            if finding.line is None or function_overlaps_diff(
                finding.line, finding.line, hunks
            ):
                in_scope.append(finding)

        excluded = len(findings) - len(in_scope)
        if excluded:
            logger.info(
                "Scanner '%s': %d finding(s) fall outside this PR's diff and are out "
                "of scope for this review; %d retained.",
                scanner,
                excluded,
                len(in_scope),
            )
        return in_scope

    @staticmethod
    def _workspace_relative(file_path: str | None, workspace_path: str) -> str | None:
        """Normalize a scanner path to workspace-relative POSIX form.

        Scanners disagree on path shape: Bandit and Semgrep echo back the absolute
        path they were handed, while Gitleaks-in-Docker reports paths relative to its
        bind mount. Diff headers are always repo-relative, so both are converted to
        that form. Already-relative paths pass through unchanged, making this safe to
        apply more than once.
        """
        if not file_path:
            return None

        candidate = Path(file_path)
        if candidate.is_absolute() and workspace_path:
            try:
                candidate = Path(os.path.relpath(str(candidate), workspace_path))
            except (ValueError, OSError):
                # Different drive or an otherwise unusable path — use the raw value.
                pass

        return candidate.as_posix().lstrip("./")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _get_llm(self) -> LLMClient | None:
        if self._llm is not None:
            return self._llm
        try:
            self._llm = LLMClient()
        except LLMConfigError as exc:
            logger.warning("LLM not configured; skipping triage: %s", exc)
            return None
        return self._llm

    def _triage(self, result: SecurityAgentResult) -> None:
        llm = self._get_llm()
        if llm is None:
            result.mark_degraded("LLM client is not configured; findings untriaged.")
            result.notes.append(
                "LLM triage skipped: client not configured. "
                f"{self._untriaged_note(result)}"
            )
            return

        by_fingerprint = {f.fingerprint: f for f in result.raw_findings}
        user_prompt = json.dumps(
            [f.to_prompt_dict() for f in result.raw_findings], indent=2
        )

        try:
            raw_response = llm.complete(
                system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt
            )
        except LLMError as exc:
            logger.warning("LLM triage failed: %s", exc)
            result.mark_degraded(
                f"LLM triage failed ({type(exc).__name__}); "
                f"{len(result.raw_findings)} scanner finding(s) left untriaged."
            )
            result.notes.append(
                f"LLM triage failed ({type(exc).__name__}); "
                f"{self._untriaged_note(result)}"
            )
            return

        parsed = self._parse_llm_findings(raw_response)
        if parsed is None:
            result.mark_degraded(
                "LLM triage response was not usable JSON; "
                f"{len(result.raw_findings)} scanner finding(s) left untriaged."
            )
            result.notes.append(
                "LLM triage response could not be parsed; "
                f"{self._untriaged_note(result)}"
            )
            return

        dropped = 0
        for item in parsed:
            fingerprint = item.get("fingerprint")
            raw = by_fingerprint.get(fingerprint) if fingerprint else None
            if raw is None:
                # Hallucinated / unmapped finding: drop it (hard rule).
                dropped += 1
                logger.warning(
                    "Dropping unmapped LLM finding (fingerprint=%r) — not present in "
                    "raw scanner output.",
                    fingerprint,
                )
                continue
            result.triaged_findings.append(
                TriagedFinding(
                    fingerprint=raw.fingerprint,
                    scanner=raw.scanner,
                    rule_id=raw.rule_id,
                    file_path=raw.file_path,
                    line=raw.line,
                    original_severity=raw.severity,
                    triaged_severity=Severity.normalize(item.get("triaged_severity")),
                    explanation=str(item.get("explanation", "")).strip(),
                    priority=self._coerce_priority(item.get("priority")),
                )
            )

        if dropped:
            result.notes.append(
                f"Dropped {dropped} unverifiable LLM finding(s) not present in raw "
                "scanner output."
            )

    @staticmethod
    def _untriaged_note(result: SecurityAgentResult) -> str:
        """Describe the raw findings that exist but are not being reported.

        They stay in ``raw_findings`` as context and are deliberately *not* promoted
        to reported findings: they never went through triage, so they carry no
        explanation or reviewed severity. Surfacing them as findings anyway is a
        separate, larger change (see CONTEXT.md known limitations).
        """
        count = len(result.raw_findings)
        if not count:
            return "no raw scanner findings to report."
        scanners = sorted({f.scanner for f in result.raw_findings})
        return (
            f"{count} raw scanner finding(s) from {', '.join(scanners)} are available "
            "as context but are NOT reported as findings because they were never "
            "triaged. This review does not cover security."
        )

    @staticmethod
    def _coerce_priority(value: object) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 99

    @staticmethod
    def _parse_llm_findings(raw_response: str) -> list[dict] | None:
        """Extract the ``findings`` list from the LLM response.

        Tolerates markdown code fences. Returns ``None`` if the response is not
        usable JSON of the expected shape.
        """
        text = raw_response.strip()
        if text.startswith("```"):
            # Strip a leading ```json / ``` fence and trailing ```.
            text = text.split("```", 2)
            text = text[1] if len(text) > 1 else raw_response
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
            text = text.rsplit("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("LLM response was not valid JSON: %s", exc)
            return None

        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            return [i for i in data["findings"] if isinstance(i, dict)]
        if isinstance(data, list):  # tolerate a bare array
            return [i for i in data if isinstance(i, dict)]
        logger.warning("LLM response JSON had unexpected shape; ignoring.")
        return None


def run_security_agent(workspace_path: str, diff: str = "") -> SecurityAgentResult:
    """Convenience entry point using default (real) runners + LLM client."""
    return SecurityAgent().run(workspace_path, diff)
