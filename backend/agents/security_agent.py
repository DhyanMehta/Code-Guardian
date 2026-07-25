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
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

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
    def run(self, workspace_path: str) -> SecurityAgentResult:
        """Scan ``workspace_path`` and return a triaged, typed result."""
        result = SecurityAgentResult()

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
            result.raw_findings.extend(findings)
            result.scanner_statuses.append(
                ScannerStatus(scanner=scanner, ok=True, finding_count=len(findings))
            )

        if result.failed_scanners:
            result.notes.append(
                "Scanner(s) failed and were skipped: "
                + ", ".join(result.failed_scanners)
            )

        # 2. Nothing to triage -> return raw results (no LLM call).
        if not result.raw_findings:
            result.notes.append("No raw findings; LLM triage skipped.")
            return result

        # 3. Triage the raw findings with the LLM (never fail the review on error).
        self._triage(result)
        return result

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
            result.notes.append("LLM triage skipped: client not configured.")
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
            result.notes.append(f"LLM triage failed ({type(exc).__name__}); "
                                "returning raw findings only.")
            return

        parsed = self._parse_llm_findings(raw_response)
        if parsed is None:
            result.notes.append(
                "LLM triage response could not be parsed; raw findings only."
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


def run_security_agent(workspace_path: str) -> SecurityAgentResult:
    """Convenience entry point using default (real) runners + LLM client."""
    return SecurityAgent().run(workspace_path)
