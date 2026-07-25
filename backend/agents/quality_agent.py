"""Quality Agent.

Checks PR diffs against the team's coding standards retrieved via RAG (ChromaDB).
The LLM is grounded ONLY on retrieved standards passages — if retrieval returns
nothing relevant, the agent explicitly says so rather than letting the LLM invent
generic advice not backed by the team's standards.

Anti-hallucination principle (same as Security Agent): every quality finding must
cite which specific retrieved passage justifies it. Findings without a valid citation
are dropped.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from backend.rag.retriever import RetrievalResult, retrieve
from backend.tools.llm_client import LLMClient, LLMConfigError, LLMError

logger = logging.getLogger(__name__)

AGENT_NAME = "quality"

_SYSTEM_PROMPT = (
    "You are a code quality reviewer. You will be given:\n"
    "1. A PR diff (code changes).\n"
    "2. A set of RETRIEVED coding-standards passages from the team's style guide.\n\n"
    "Your ONLY job is to check the diff against THESE SPECIFIC passages. You must:\n"
    "- ONLY report violations of rules explicitly stated in the provided passages.\n"
    "- NEVER invent rules, best practices, or advice not grounded in the passages.\n"
    "- For each finding, cite the passage_index (0-based) that justifies it.\n"
    "- If no violations are found, return an empty findings list.\n\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{"findings": [{"passage_index": <int>, "file_path": "<from diff>", '
    '"line": <int or null>, "rule_violated": "<short rule name>", '
    '"explanation": "<how the diff violates the cited passage>", '
    '"severity": "high|medium|low|info"}]}\n'
    "Do not include any prose outside the JSON object."
)


@dataclass
class QualityFinding:
    """A single quality finding grounded in a retrieved standards passage."""

    file_path: str | None
    line: int | None
    rule_violated: str
    explanation: str
    severity: str
    cited_passage: str
    source_file: str


@dataclass
class QualityAgentResult:
    """Typed output of the Quality Agent."""

    findings: list[QualityFinding] = field(default_factory=list)
    retrieval_context: RetrievalResult | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0


class QualityAgent:
    """The Quality Agent node."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        retriever_fn=None,
        persist_dir: str | None = None,
    ) -> None:
        self._llm = llm_client
        self._llm_provided = llm_client is not None
        self._retriever_fn = retriever_fn or retrieve
        self._persist_dir = persist_dir

    def run(self, diff: str, changed_files: list[str] | None = None) -> QualityAgentResult:
        """Analyze the diff against retrieved coding standards.

        Args:
            diff: the full PR diff text.
            changed_files: list of changed file paths (used to enhance retrieval query).

        Returns:
            QualityAgentResult with grounded findings or explanatory notes.
        """
        result = QualityAgentResult()

        if not diff.strip():
            result.notes.append("Empty diff; nothing to review.")
            return result

        query_text = self._build_retrieval_query(diff, changed_files)
        retrieval = self._retriever_fn(query_text, persist_dir=self._persist_dir)
        result.retrieval_context = retrieval

        if not retrieval.has_context:
            result.notes.append(
                "No relevant coding-standards passages retrieved. "
                "Cannot perform grounded quality review. "
                f"Reason: {retrieval.error or 'unknown'}"
            )
            return result

        self._review_with_llm(diff, retrieval, result)
        return result

    def _build_retrieval_query(
        self, diff: str, changed_files: list[str] | None
    ) -> str:
        """Build a retrieval query from the diff and file context."""
        parts = []
        if changed_files:
            parts.append("Files changed: " + ", ".join(changed_files[:20]))
        diff_preview = diff[:3000] if len(diff) > 3000 else diff
        parts.append(diff_preview)
        return "\n".join(parts)

    def _get_llm(self) -> LLMClient | None:
        if self._llm is not None:
            return self._llm
        try:
            self._llm = LLMClient()
        except LLMConfigError as exc:
            logger.warning("LLM not configured; skipping quality review: %s", exc)
            return None
        return self._llm

    def _review_with_llm(
        self,
        diff: str,
        retrieval: RetrievalResult,
        result: QualityAgentResult,
    ) -> None:
        llm = self._get_llm()
        if llm is None:
            result.notes.append("LLM not configured; quality review skipped.")
            return

        passages_text = self._format_passages_for_prompt(retrieval)
        user_prompt = (
            "## Retrieved Coding Standards Passages\n\n"
            f"{passages_text}\n\n"
            "## PR Diff\n\n"
            f"```diff\n{diff[:8000]}\n```"
        )

        try:
            raw_response = llm.complete(
                system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt
            )
        except LLMError as exc:
            logger.warning("LLM quality review failed: %s", exc)
            result.notes.append(
                f"LLM review failed ({type(exc).__name__}); no quality findings produced."
            )
            return

        parsed = self._parse_llm_findings(raw_response)
        if parsed is None:
            result.notes.append(
                "LLM response could not be parsed; no quality findings produced."
            )
            return

        self._validate_and_collect(parsed, retrieval, result)

    def _format_passages_for_prompt(self, retrieval: RetrievalResult) -> str:
        lines = []
        for i, passage in enumerate(retrieval.passages):
            lines.append(
                f"[Passage {i}] (source: {passage.source_file})\n{passage.text}"
            )
        return "\n\n".join(lines)

    def _validate_and_collect(
        self,
        parsed: list[dict],
        retrieval: RetrievalResult,
        result: QualityAgentResult,
    ) -> None:
        """Validate each LLM finding against the retrieved passages.

        Findings that cite a passage_index outside the valid range are dropped
        (same anti-hallucination principle as Security Agent's fingerprint check).
        """
        dropped = 0
        passage_count = len(retrieval.passages)

        for item in parsed:
            passage_index = item.get("passage_index")
            if not isinstance(passage_index, int) or passage_index < 0 or passage_index >= passage_count:
                dropped += 1
                logger.warning(
                    "Dropping quality finding with invalid passage_index=%r "
                    "(valid range: 0-%d).",
                    passage_index,
                    passage_count - 1,
                )
                continue

            cited = retrieval.passages[passage_index]
            result.findings.append(
                QualityFinding(
                    file_path=item.get("file_path"),
                    line=self._coerce_line(item.get("line")),
                    rule_violated=str(item.get("rule_violated", "")).strip() or "unspecified",
                    explanation=str(item.get("explanation", "")).strip(),
                    severity=self._normalize_severity(item.get("severity")),
                    cited_passage=cited.text[:200],
                    source_file=cited.source_file,
                )
            )

        if dropped:
            result.notes.append(
                f"Dropped {dropped} ungrounded finding(s) citing invalid passage references."
            )

    @staticmethod
    def _coerce_line(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_severity(value: object) -> str:
        valid = {"high", "medium", "low", "info"}
        v = str(value).strip().lower() if value else "info"
        return v if v in valid else "info"

    @staticmethod
    def _parse_llm_findings(raw_response: str) -> list[dict] | None:
        """Extract the findings list from the LLM response JSON."""
        text = raw_response.strip()
        if text.startswith("```"):
            text = text.split("```", 2)
            text = text[1] if len(text) > 1 else raw_response
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
            text = text.rsplit("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Quality LLM response was not valid JSON: %s", exc)
            return None

        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            return [i for i in data["findings"] if isinstance(i, dict)]
        if isinstance(data, list):
            return [i for i in data if isinstance(i, dict)]
        logger.warning("Quality LLM response JSON had unexpected shape.")
        return None


def run_quality_agent(
    diff: str, changed_files: list[str] | None = None
) -> QualityAgentResult:
    """Convenience entry point using default retriever + LLM client."""
    return QualityAgent().run(diff, changed_files)
