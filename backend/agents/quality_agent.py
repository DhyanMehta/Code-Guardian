"""Quality Agent.

Checks PR diffs against the team's coding standards retrieved via RAG (ChromaDB).
The LLM is grounded ONLY on retrieved standards passages — if retrieval returns
nothing relevant, the agent explicitly says so rather than letting the LLM invent
generic advice not backed by the team's standards.

Anti-hallucination: a quality finding must survive three independent checks before
it is accepted.

1. **Rule anchoring** — it must cite the ``passage_index`` of a passage that was
   actually retrieved. This proves the *rule* is real.
2. **Code anchoring** — it must name the exact ``symbol`` it concerns, and that
   symbol must exist in the target file's AST, in a file this PR actually changed.
   This proves the *code* is real.
3. **Countable-claim anchoring** — if the finding asserts a parameter count or a
   function length, that number is recomputed from the AST and the finding is
   dropped when the real value clearly contradicts it. This proves the two
   *measurable* claims are real.

Check 2 exists because check 1 alone is not enough: a real Groq run cited a valid
naming-conventions passage and attached it to ``class TimeoutError`` in a file that
contains no classes at all, twenty-one times over. Check 3 exists because check 2
alone is not enough either: a later run correctly named ``process_data`` and
``build_report`` but claimed both "accept more than 5 positional parameters" when
they take 1 and 4. Accepted findings also take their line number from the AST rather
than from the model, so the location is deterministic too.

Findings that fail any check are dropped and logged, never surfaced — the same
treatment the Security Agent gives an LLM finding whose fingerprint maps to no real
scanner output (``RULES.md`` #5).

**Known limitation (deliberate scope boundary).** Only symbol existence, parameter
count, and length are verified. Free-form assertions — "this reads as a question",
"the complexity is high", stylistic or behavioural judgements — are not checked
against anything, because doing so would mean reimplementing each rule's semantics
deterministically, which is a redesign of this agent rather than a guard on it. Such
findings are grounded in a real rule and attached to real code, but their reasoning
is the model's and is not independently verified.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents._validation import (
    SymbolInfo,
    collect_defined_symbols,
    get_function_params,
    validate_naming_convention,
)
from backend.agents.state import AgentOutcome
from backend.rag.retriever import RetrievalResult, retrieve
from backend.tools.llm_client import LLMClient, LLMConfigError, LLMError

logger = logging.getLogger(__name__)

AGENT_NAME = "quality"

MODULE_SYMBOL = "<module>"
"""Reserved ``symbol`` value for a violation about a file as a whole rather than one
definition (module naming, file length). Without an explicit escape hatch the model
would be pushed into inventing a symbol name to satisfy the schema."""

# Characters of raw diff included in the *retrieval* query. Kept short so the
# AST-derived structural facts are not drowned out by diff noise when embedding;
# the LLM still receives the much larger diff window below.
_DIFF_QUERY_CHARS = 800
_DIFF_PROMPT_CHARS = 8000

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}

# Countable-claim extraction. A finding asserts a *violation* of a threshold, so
# whichever way the text is phrased ("exceeds 40 lines", "should not exceed 40
# lines", "the 40-line limit"), the assertion about the code is the same: the real
# value is above the threshold.
_PARAM_CLAIM_RE = re.compile(
    r"(\d+)[\s-]*(?:positional|keyword|function|input|required)?[\s-]*"
    r"(?:parameters?|params?|arguments?|args)\b",
    re.IGNORECASE,
)
_LENGTH_CLAIM_RE = re.compile(
    r"(\d+)[\s-]*(?:source|logical|logic|physical)?[\s-]*lines?\b",
    re.IGNORECASE,
)

# Parameter counting is exact, so any shortfall is a real contradiction.
_PARAM_CLAIM_MARGIN = 1
# Line counting is not: standards talk about "lines of logic" while the AST measures
# physical span including the signature, decorators, and docstring. Only reject when
# the real span falls clearly below the claimed threshold.
_LENGTH_CLAIM_TOLERANCE = 0.75

_NAMING_CLAIM_RE = re.compile(
    r"(?:does not|doesn't|doesn't|not)\s+(?:follow|conform|adhere|use|match)"
    r".*?\b(snake[_\s]?case|camel[_\s]?case|pascal[_\s]?case|UPPER[_\s]?CASE"
    r"|SCREAMING[_\s]?SNAKE)\b",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = (
    "You are a code quality reviewer. You will be given:\n"
    "1. A PR diff (code changes).\n"
    "2. A set of RETRIEVED coding-standards passages from the team's style guide.\n\n"
    "Your ONLY job is to check the diff against THESE SPECIFIC passages. You must:\n"
    "- ONLY report violations of rules explicitly stated in the provided passages.\n"
    "- NEVER invent rules, best practices, or advice not grounded in the passages.\n"
    "- For each finding, cite the passage_index (0-based) that justifies it.\n"
    "- For each finding, set 'symbol' to the EXACT name of the function, class, or "
    "module-level variable the violation is about, copied verbatim from the diff. "
    f'Use "{MODULE_SYMBOL}" ONLY when the violation is about the file as a whole '
    "and concerns no single definition.\n"
    "- NEVER name a symbol that does not literally appear in the diff. Findings "
    "naming symbols that do not exist in the file are discarded.\n"
    "- If you state a parameter count or a line count, it MUST be accurate for the "
    "code in the diff. Findings whose counts contradict the code are discarded.\n"
    "- Report each distinct violation EXACTLY ONCE. Never repeat the same "
    "symbol + rule combination.\n"
    "- If no violations are found, return an empty findings list.\n\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{"findings": [{"passage_index": <int>, "file_path": "<from diff>", '
    '"symbol": "<exact name from the diff>", '
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
    symbol: str = MODULE_SYMBOL


@dataclass
class QualityAgentResult:
    """Typed output of the Quality Agent."""

    findings: list[QualityFinding] = field(default_factory=list)
    retrieval_context: RetrievalResult | None = None
    notes: list[str] = field(default_factory=list)

    # Structured run outcome. Consumers must use this rather than inspecting note
    # text: zero findings with outcome OK is a clean result, zero findings with
    # outcome DEGRADED means the agent could not actually check anything.
    outcome: AgentOutcome = AgentOutcome.OK
    failure_reason: str | None = None

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0

    def mark_degraded(self, reason: str) -> None:
        """Record that the agent ran but could not complete its analysis."""
        self.outcome = AgentOutcome.DEGRADED
        self.failure_reason = reason


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

    def run(
        self,
        diff: str,
        changed_files: list[str] | None = None,
        workspace_path: str = "",
    ) -> QualityAgentResult:
        """Analyze the diff against retrieved coding standards.

        Args:
            diff: the full PR diff text.
            changed_files: changed file paths, used both to bias retrieval and to
                bound which files a finding may be reported against.
            workspace_path: root of the PR checkout. Required for AST verification;
                when absent the symbol-existence gates cannot run and are skipped
                with a warning.

        Returns:
            QualityAgentResult with grounded findings or explanatory notes.
        """
        result = QualityAgentResult()

        if not diff.strip():
            # A genuinely empty diff is a clean result, not a degraded run.
            result.notes.append("Empty diff; nothing to review.")
            return result

        query_text = self._build_retrieval_query(diff, changed_files, workspace_path)
        retrieval = self._retriever_fn(query_text, persist_dir=self._persist_dir)
        result.retrieval_context = retrieval

        if not retrieval.has_context:
            reason = retrieval.error or "unknown"
            result.mark_degraded(f"No coding-standards context retrieved: {reason}")
            result.notes.append(
                "No relevant coding-standards passages retrieved. "
                "Cannot perform grounded quality review. "
                f"Reason: {reason}"
            )
            return result

        self._review_with_llm(diff, retrieval, result, changed_files, workspace_path)
        return result

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def _build_retrieval_query(
        self,
        diff: str,
        changed_files: list[str] | None,
        workspace_path: str = "",
    ) -> str:
        """Build a retrieval query from structural facts plus diff context.

        Raw diff text alone is a poor query for standards about *structure*: a diff
        that adds a 114-line function never says "114 lines" anywhere, so the
        function-length passage does not embed close to it. Measured on the real E2E
        PR against the real collection, the length rule sat at distance 1.903 for a
        diff-only query — far outside the 1.5 relevance cutoff — which made the
        violation unreportable no matter how well the rest of the agent behaved.

        The query is therefore the AST-derived facts alone when they are available:
        definition names and their measured line counts, nothing inferred or
        generated. Appending anything else measurably *hurts*, because the embedding
        model truncates long inputs, so diff text crowds the facts out of the encoded
        window. Measured distances for the length rule on the same PR:

            facts only .................. 1.462  (retrieved)
            facts + "Files changed:" .... 1.531  (cut)
            facts + 400..3000 diff chars  1.590  (cut, identical => truncation)
            diff only (original) ........ 1.903  (cut)

        The relevance cutoff and top_k are deliberately left alone; loosening either
        would admit noise rather than improve relevance. The LLM still receives the
        full diff window — this shortening applies only to the retrieval query.
        """
        facts = self._structural_facts(changed_files, workspace_path)
        if facts:
            return facts

        # No workspace or no parseable Python: fall back to diff-based context.
        parts = []
        if changed_files:
            parts.append("Files changed: " + ", ".join(changed_files[:20]))
        parts.append(diff[:_DIFF_QUERY_CHARS])
        return "\n".join(parts)

    @staticmethod
    def _structural_facts(
        changed_files: list[str] | None,
        workspace_path: str,
    ) -> str:
        """Describe the changed code's structure using measured AST facts."""
        if not changed_files or not workspace_path:
            return ""

        lines: list[str] = []
        for rel_path in changed_files[:20]:
            if not rel_path.endswith(".py"):
                continue
            table = collect_defined_symbols(os.path.join(workspace_path, rel_path))
            if not table:
                continue

            functions = [i for i in table.values() if i.kind == "function"]
            classes = [i for i in table.values() if i.kind == "class"]
            lines.append(
                f"{rel_path} defines {len(functions)} function(s) and "
                f"{len(classes)} class(es)."
            )
            # Longest first: the worst offender against any length rule leads.
            for info in sorted(functions, key=lambda i: i.line_count, reverse=True)[:15]:
                lines.append(
                    f"function {info.name} in {rel_path} is "
                    f"{info.line_count} lines long"
                )
            for info in sorted(classes, key=lambda i: i.line_count, reverse=True)[:10]:
                lines.append(
                    f"class {info.name} in {rel_path} is {info.line_count} lines long"
                )

        if not lines:
            return ""
        return "Structure of the changed code (measured):\n" + "\n".join(lines)

    # ------------------------------------------------------------------ #
    # LLM review
    # ------------------------------------------------------------------ #
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
        changed_files: list[str] | None,
        workspace_path: str,
    ) -> None:
        llm = self._get_llm()
        if llm is None:
            result.mark_degraded("LLM client is not configured.")
            result.notes.append("LLM not configured; quality review skipped.")
            return

        passages_text = self._format_passages_for_prompt(retrieval)
        user_prompt = (
            "## Retrieved Coding Standards Passages\n\n"
            f"{passages_text}\n\n"
            "## PR Diff\n\n"
            f"```diff\n{diff[:_DIFF_PROMPT_CHARS]}\n```"
        )

        try:
            # json_mode is required here: without it a real Groq run returned 160
            # lines of malformed JSON and every finding was discarded. It is only
            # safe to accept well-formed output because the gates below verify the
            # content against the AST.
            raw_response = llm.complete(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
        except LLMError as exc:
            logger.warning("LLM quality review failed: %s", exc)
            result.mark_degraded(f"LLM review failed: {type(exc).__name__}")
            result.notes.append(
                f"LLM review failed ({type(exc).__name__}); no quality findings produced."
            )
            return

        parsed = self._parse_llm_findings(raw_response)
        if parsed is None:
            result.mark_degraded("LLM response was not usable JSON.")
            result.notes.append(
                "LLM response could not be parsed; no quality findings produced."
            )
            return

        self._validate_and_collect(
            parsed, retrieval, result, changed_files, workspace_path
        )

    def _format_passages_for_prompt(self, retrieval: RetrievalResult) -> str:
        lines = []
        for i, passage in enumerate(retrieval.passages):
            lines.append(
                f"[Passage {i}] (source: {passage.source_file})\n{passage.text}"
            )
        return "\n\n".join(lines)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def _validate_and_collect(
        self,
        parsed: list[dict],
        retrieval: RetrievalResult,
        result: QualityAgentResult,
        changed_files: list[str] | None = None,
        workspace_path: str = "",
    ) -> None:
        """Accept only findings anchored to both a real passage and real code.

        Every rejection is counted by reason, logged at WARNING with the offending
        symbol, and summarized in ``result.notes`` — a fabricating model stays
        visible instead of silently producing nothing (``RULES.md`` #9). Rejections
        never fail the agent.
        """
        passage_count = len(retrieval.passages)
        verify_code = bool(workspace_path)
        if not verify_code:
            logger.warning(
                "No workspace_path supplied to the Quality Agent; symbol-existence "
                "verification is disabled and findings cannot be anchored to real code."
            )

        changed_set = {
            self._normalize_path(p) for p in (changed_files or []) if p
        }
        symbol_tables: dict[str, dict[str, SymbolInfo] | None] = {}
        rejected: dict[str, int] = {}
        accepted: list[QualityFinding] = []

        def _reject(reason: str, item: dict) -> None:
            rejected[reason] = rejected.get(reason, 0) + 1
            logger.warning(
                "Dropping quality finding that %s: symbol=%r file=%r rule=%r",
                reason,
                item.get("symbol"),
                item.get("file_path"),
                item.get("rule_violated"),
            )

        for item in parsed:
            # Gate 1: the cited rule must be a passage we actually retrieved.
            passage_index = item.get("passage_index")
            if (
                not isinstance(passage_index, int)
                or passage_index < 0
                or passage_index >= passage_count
            ):
                _reject("cites a passage that was not retrieved", item)
                continue

            rel_path = self._normalize_path(item.get("file_path"))
            symbol = str(item.get("symbol") or "").strip()
            line = self._coerce_line(item.get("line"))

            if verify_code:
                # Gate 2: the finding must name what it is about.
                if not symbol:
                    _reject("name no symbol", item)
                    continue

                # Gate 3: it must concern a file this PR actually changed.
                if changed_set and rel_path not in changed_set:
                    _reject("target a file outside the PR's changed files", item)
                    continue

                abs_path = os.path.join(workspace_path, rel_path) if rel_path else ""
                if rel_path not in symbol_tables:
                    symbol_tables[rel_path] = (
                        collect_defined_symbols(abs_path) if rel_path else None
                    )
                table = symbol_tables.get(rel_path)
                if table is None:
                    _reject("target a file that could not be parsed", item)
                    continue

                if symbol == MODULE_SYMBOL:
                    # The escape hatch is a bypass risk: a real run labelled three
                    # findings "<module>" while their explanations named
                    # `process_data`, dodging the symbol gate and losing the line
                    # number. If the claim itself names a definition in this file,
                    # anchor to that definition instead of accepting file scope.
                    named = self._first_symbol_mentioned(
                        str(item.get("explanation", "")), table
                    )
                    if named is None:
                        info = None
                        line = None
                    else:
                        logger.info(
                            "Re-anchoring '<module>' quality finding to symbol %r "
                            "named in its own explanation (rule=%r).",
                            named,
                            item.get("rule_violated"),
                        )
                        symbol = named
                        info = table[named]
                        line = info.start_line
                else:
                    # Gate 4: the symbol must really exist, and its line comes from
                    # the AST rather than from the model.
                    info = table.get(symbol)
                    if info is None:
                        _reject("name a symbol that does not exist in the file", item)
                        continue
                    line = info.start_line

                # Gate 5: any countable claim must survive recomputation.
                if info is not None:
                    contradiction = self._contradicted_numeric_claim(
                        item, symbol, info, abs_path
                    )
                    if contradiction is not None:
                        _reject(contradiction, item)
                        continue

                # Gate 6: naming-convention claims must match the symbol's actual case.
                if info is not None and self._is_naming_claim(item):
                    violates, reason = validate_naming_convention(symbol, info)
                    if not violates:
                        _reject(
                            f"claim a naming violation but {reason}", item
                        )
                        continue

            cited = retrieval.passages[passage_index]
            accepted.append(
                QualityFinding(
                    file_path=rel_path or item.get("file_path"),
                    line=line,
                    rule_violated=str(item.get("rule_violated", "")).strip()
                    or "unspecified",
                    explanation=str(item.get("explanation", "")).strip(),
                    severity=self._normalize_severity(item.get("severity")),
                    cited_passage=cited.text[:200],
                    source_file=cited.source_file,
                    symbol=symbol or MODULE_SYMBOL,
                )
            )

        result.findings = self._deduplicate(accepted, result)

        for reason, count in sorted(rejected.items()):
            result.notes.append(f"Dropped {count} finding(s) that {reason}.")

    # ------------------------------------------------------------------ #
    # Countable-claim verification
    # ------------------------------------------------------------------ #
    @classmethod
    def _contradicted_numeric_claim(
        cls,
        item: dict,
        symbol: str,
        info: SymbolInfo,
        file_path: str,
    ) -> str | None:
        """Return a rejection reason if a countable claim contradicts the code.

        Only two claim types are checked, both already computable from the AST data
        this module collects: parameter count and definition length. Everything else
        the model asserts is left alone (see the module docstring's scope boundary).
        """
        text = f"{item.get('rule_violated', '')} {item.get('explanation', '')}"

        claimed_lines = cls._claimed_threshold(_LENGTH_CLAIM_RE, text)
        if claimed_lines:
            real_lines = info.line_count
            if real_lines < claimed_lines * _LENGTH_CLAIM_TOLERANCE:
                logger.warning(
                    "Quality finding claims %r breaches a %d-line threshold, but %r "
                    "spans %d line(s) (%d-%d).",
                    symbol,
                    claimed_lines,
                    symbol,
                    real_lines,
                    info.start_line,
                    info.end_line,
                )
                return "claim a line count the code contradicts"

        claimed_params = cls._claimed_threshold(_PARAM_CLAIM_RE, text)
        if claimed_params and file_path:
            params = get_function_params(symbol, file_path)
            # ``None`` means the symbol is not a function (class, constant), so
            # there is no parameter count to contradict.
            if params is not None and (
                claimed_params - len(params) >= _PARAM_CLAIM_MARGIN
            ):
                logger.warning(
                    "Quality finding claims %r breaches a %d-parameter threshold, but "
                    "%r takes %d: %s.",
                    symbol,
                    claimed_params,
                    symbol,
                    len(params),
                    sorted(params),
                )
                return "claim a parameter count the code contradicts"

        return None

    @staticmethod
    def _claimed_threshold(pattern: re.Pattern[str], text: str) -> int | None:
        """Smallest number the text associates with a metric, or ``None``.

        The smallest is used deliberately. A finding may cite both the real value and
        the limit ("is 114 lines long, exceeding the 40-line limit"); the limit is the
        threshold being breached, and taking the minimum makes the check reject only
        when the code falls below even the most lenient number mentioned.
        """
        values = [int(m.group(1)) for m in pattern.finditer(text)]
        return min(values) if values else None

    @staticmethod
    def _is_naming_claim(item: dict) -> bool:
        """Return True if the finding asserts a naming-convention violation."""
        text = f"{item.get('rule_violated', '')} {item.get('explanation', '')}"
        return _NAMING_CLAIM_RE.search(text) is not None

    @staticmethod
    def _first_symbol_mentioned(
        explanation: str,
        table: dict[str, SymbolInfo],
    ) -> str | None:
        """Return the first defined symbol named in ``explanation``, if any.

        Used to re-anchor a finding that claimed module scope while actually
        describing one definition. Matches whole identifiers only, so a substring of
        a longer word cannot trigger a false anchor.
        """
        if not explanation or not table:
            return None
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", explanation):
            name = match.group(0)
            if name in table:
                return name
        return None

    @staticmethod
    def _deduplicate(
        findings: list[QualityFinding],
        result: QualityAgentResult,
    ) -> list[QualityFinding]:
        """Collapse findings repeating the same rule for the same symbol.

        Keeps the first occurrence (preserving order) and the highest severity seen
        across the duplicates, so collapsing never downgrades a finding.
        """
        by_key: dict[tuple[str, str, str], QualityFinding] = {}
        collapsed = 0

        for finding in findings:
            key = (finding.file_path or "", finding.symbol, finding.rule_violated)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = finding
                continue
            collapsed += 1
            if _SEVERITY_RANK.get(finding.severity, 99) < _SEVERITY_RANK.get(
                existing.severity, 99
            ):
                existing.severity = finding.severity

        if collapsed:
            logger.info("Collapsed %d duplicate quality finding(s).", collapsed)
            result.notes.append(
                f"Collapsed {collapsed} duplicate finding(s) reporting the same rule "
                "for the same symbol."
            )
        return list(by_key.values())

    @staticmethod
    def _normalize_path(file_path: object) -> str:
        """Normalize a reported path to workspace-relative POSIX form."""
        if not file_path:
            return ""
        return Path(str(file_path)).as_posix().lstrip("./")

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
    diff: str,
    changed_files: list[str] | None = None,
    workspace_path: str = "",
) -> QualityAgentResult:
    """Convenience entry point using default retriever + LLM client."""
    return QualityAgent().run(diff, changed_files, workspace_path)
