"""Documentation Agent.

Flags missing or outdated docstrings against the actual current function signature
and behavior, and drafts replacement docstrings.

Detection is entirely deterministic (AST-based). The LLM is used ONLY to draft
docstring content — never to decide whether something is missing or outdated.

Anti-hallucination boundary:
* Every drafted docstring must only reference parameter names that exist in the
  actual function signature (parameter-name anchoring).
* Every drafted docstring must be for a function in the deterministic flagged list
  (function-name anchoring).
* Drafted docstrings failing either check are dropped and logged.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path

from backend.agents._diff_utils import function_overlaps_diff, parse_diff_hunks
from backend.agents.state import (
    DocAgentResult,
    DocTarget,
    DraftedDocstring,
    FunctionInfo,
)
from backend.tools.llm_client import LLMClient, LLMConfigError, LLMError

logger = logging.getLogger(__name__)

AGENT_NAME = "documentation"

FileReaderFn = Callable[[str], str]

_SYSTEM_PROMPT = (
    "You are a documentation assistant. You will be given a Python function's full "
    "source code (including its signature). Your ONLY job is to write a Google-style "
    "docstring for this function.\n\n"
    "STRICT RULES:\n"
    "1. Document ONLY the parameters that appear in the provided signature.\n"
    "2. Do NOT invent parameters, return types, or behaviors not evident from the code.\n"
    "3. Use Google-style format: one-line summary, then Args:, Returns:, Raises: "
    "sections as appropriate.\n"
    "4. Keep it concise — one line per parameter.\n"
    "5. If the function is trivial (1-2 lines, self-explanatory), write only a "
    "one-line summary with no sections.\n\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{"docstring": "<the docstring content without triple quotes>", '
    '"params_documented": ["<param_name_1>", "<param_name_2>"]}\n'
    "Do not include any prose outside the JSON object."
)

_PARAM_SECTION_RE = re.compile(
    r"(?:Args|Parameters|Params)\s*:", re.IGNORECASE
)


def _default_file_reader(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


class DocumentationAgent:
    """The Documentation Agent node."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        file_reader_fn: FileReaderFn | None = None,
    ) -> None:
        self._llm = llm_client
        self._llm_provided = llm_client is not None
        self._read_file = file_reader_fn or _default_file_reader

    def run(
        self,
        diff: str,
        changed_files: list[str],
        workspace_path: str,
    ) -> DocAgentResult:
        """Analyze the diff and flag functions with missing/outdated docstrings.

        Args:
            diff: the full PR unified diff text.
            changed_files: list of changed file paths (relative to workspace).
            workspace_path: root of the checked-out repository.

        Returns:
            DocAgentResult with flagged functions and optionally drafted docstrings.
        """
        result = DocAgentResult()

        if not diff.strip():
            result.notes.append("Empty diff; nothing to analyze.")
            return result

        python_files = [f for f in changed_files if f.endswith(".py")]
        if not python_files:
            result.notes.append(
                "No Python files changed; documentation analysis skipped."
            )
            return result

        hunks = parse_diff_hunks(diff)
        targets = self._extract_functions_needing_docs(
            python_files, hunks, workspace_path
        )

        if not targets:
            result.notes.append(
                "All modified public functions have adequate documentation."
            )
            return result

        result.flagged_functions = targets
        self._draft_docstrings(targets, result)
        return result

    def _extract_functions_needing_docs(
        self,
        python_files: list[str],
        hunks: dict[str, list[tuple[int, int]]],
        workspace_path: str,
    ) -> list[DocTarget]:
        """AST-parse changed files, flag functions with doc issues."""
        targets: list[DocTarget] = []

        for file_path in python_files:
            file_hunks = hunks.get(file_path)
            if not file_hunks:
                continue

            abs_path = os.path.join(workspace_path, file_path)
            try:
                source = self._read_file(abs_path)
            except (OSError, IOError) as exc:
                logger.warning("Cannot read %s: %s", file_path, exc)
                continue

            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError as exc:
                logger.warning("Cannot parse %s: %s", file_path, exc)
                continue

            targets.extend(
                self._analyze_functions(tree, source, file_path, file_hunks)
            )

        return targets

    def _analyze_functions(
        self,
        tree: ast.Module,
        source: str,
        file_path: str,
        file_hunks: list[tuple[int, int]],
    ) -> list[DocTarget]:
        """Check each function/class in the AST for documentation issues."""
        results: list[DocTarget] = []
        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                continue

            # Skip private functions and dunder methods
            if node.name.startswith("_"):
                continue

            start_line = node.lineno
            end_line = node.end_lineno or node.lineno

            if not function_overlaps_diff(start_line, end_line, file_hunks):
                continue

            # For functions, check if trivial
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._is_trivial_function(node):
                    continue

            docstring = ast.get_docstring(node)
            params = self._get_params(node)
            func_source = "\n".join(source_lines[start_line - 1 : end_line])

            fn_info = FunctionInfo(
                name=node.name,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                source=func_source,
                is_method=isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and self._get_enclosing_class(tree, node) is not None,
                class_name=self._get_enclosing_class(tree, node),
                params=params,
            )

            if docstring is None:
                results.append(DocTarget(
                    function=fn_info,
                    reason="missing",
                    existing_docstring=None,
                ))
            elif self._is_docstring_outdated(docstring, params):
                results.append(DocTarget(
                    function=fn_info,
                    reason="outdated",
                    existing_docstring=docstring,
                ))
            elif self._is_docstring_incomplete(docstring, params):
                results.append(DocTarget(
                    function=fn_info,
                    reason="incomplete",
                    existing_docstring=docstring,
                ))

        return results

    @staticmethod
    def _is_trivial_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """A function is trivial if body is <=2 statements and only self/cls params."""
        body = [stmt for stmt in node.body
                if not isinstance(stmt, ast.Expr)
                or not isinstance(getattr(stmt, "value", None), ast.Constant)]
        if len(body) > 2:
            return False
        non_self_params = [
            arg.arg for arg in node.args.args
            if arg.arg not in ("self", "cls")
        ]
        return len(non_self_params) == 0

    @staticmethod
    def _get_params(node: ast.AST) -> list[str]:
        """Extract parameter names from a function/class node."""
        if isinstance(node, ast.ClassDef):
            return []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return [
                arg.arg for arg in node.args.args
                if arg.arg not in ("self", "cls")
            ]
        return []

    @staticmethod
    def _is_docstring_outdated(docstring: str, params: list[str]) -> bool:
        """A docstring is outdated if it references params not in the signature.

        Only checks if the docstring has a structured parameter section.
        """
        if not _PARAM_SECTION_RE.search(docstring):
            return False

        # Extract parameter names mentioned in the docstring's param section
        doc_lower = docstring.lower()
        for param in _extract_documented_params(docstring):
            if param not in params:
                return True
        return False

    @staticmethod
    def _is_docstring_incomplete(docstring: str, params: list[str]) -> bool:
        """A docstring is incomplete if params exist but aren't documented."""
        if not params:
            return False

        if not _PARAM_SECTION_RE.search(docstring):
            # No structured param section at all — incomplete if there are params
            if len(params) > 0:
                return True
            return False

        documented = _extract_documented_params(docstring)
        for param in params:
            if param not in documented:
                return True
        return False

    @staticmethod
    def _get_enclosing_class(tree: ast.Module, target: ast.AST) -> str | None:
        """Return the class name if target is a method, else None."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is target:
                        return node.name
        return None

    def _draft_docstrings(
        self,
        targets: list[DocTarget],
        result: DocAgentResult,
    ) -> None:
        """Use the LLM to draft docstrings for flagged functions."""
        llm = self._get_llm()
        if llm is None:
            result.notes.append(
                "LLM not configured; returning flags without drafts."
            )
            return

        for target in targets[:15]:
            fn = target.function
            user_prompt = (
                f"Function name: {fn.name}\n"
                f"Parameters: {', '.join(fn.params) if fn.params else 'none'}\n"
                f"Source code:\n```python\n{fn.source}\n```"
            )
            if target.existing_docstring:
                user_prompt += (
                    f"\n\nExisting (outdated) docstring:\n"
                    f'"""{target.existing_docstring}"""'
                )

            try:
                raw_response = llm.complete(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    json_mode=True,
                )
            except LLMError as exc:
                logger.warning("LLM draft failed for %s: %s", fn.name, exc)
                result.notes.append(
                    f"LLM draft failed for '{fn.name}' ({type(exc).__name__})."
                )
                continue

            draft = self._validate_drafted_docstring(raw_response, target)
            if draft is not None:
                result.drafted_docstrings.append(draft)

    def _validate_drafted_docstring(
        self,
        raw_response: str,
        target: DocTarget,
    ) -> DraftedDocstring | None:
        """Validate the LLM draft against anti-hallucination rules."""
        parsed = self._parse_llm_response(raw_response)
        if parsed is None:
            logger.warning(
                "Unparseable LLM draft for %s; dropping.", target.function.name
            )
            return None

        docstring = parsed.get("docstring", "")
        params_documented = parsed.get("params_documented", [])

        if not docstring.strip():
            return None

        # Anti-hallucination check 1: function must be in flagged list
        # (enforced by the caller — we only call LLM for flagged functions)

        # Anti-hallucination check 2: documented params must exist in signature
        if isinstance(params_documented, list):
            real_params = set(target.function.params)
            for param in params_documented:
                if str(param) not in real_params:
                    logger.warning(
                        "Drafted docstring for '%s' references non-existent "
                        "param '%s'; dropping.",
                        target.function.name,
                        param,
                    )
                    return None

        return DraftedDocstring(
            target_function=target.function.name,
            target_file=target.function.file_path,
            docstring=docstring,
            params_valid=True,
        )

    def _get_llm(self) -> LLMClient | None:
        if self._llm is not None:
            return self._llm
        try:
            self._llm = LLMClient()
        except LLMConfigError as exc:
            logger.warning("LLM not configured; skipping doc drafts: %s", exc)
            return None
        return self._llm

    @staticmethod
    def _parse_llm_response(raw_response: str) -> dict | None:
        """Parse the LLM's JSON response, tolerating code fences."""
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
            logger.warning("LLM doc draft was not valid JSON: %s", exc)
            return None

        if isinstance(data, dict):
            return data
        return None


def _extract_documented_params(docstring: str) -> set[str]:
    """Extract parameter names from a Google/NumPy/Sphinx-style docstring."""
    params: set[str] = set()
    # Known section headers to exclude from param extraction
    _SECTION_HEADERS = frozenset({
        "args", "arguments", "parameters", "params",
        "returns", "return", "raises", "yields", "yield",
        "attributes", "note", "notes", "example", "examples",
        "references", "see", "todo", "warnings", "warns",
    })

    # Match patterns like "    param_name:" or "    param_name (" in Args sections
    param_pattern = re.compile(r"^\s+(\w+)\s*[\(:]", re.MULTILINE)
    # Match ":param param_name:" for Sphinx style
    sphinx_pattern = re.compile(r":param\s+(\w+)\s*:", re.MULTILINE)

    for match in param_pattern.finditer(docstring):
        name = match.group(1)
        if name.lower() not in _SECTION_HEADERS:
            params.add(name)

    for match in sphinx_pattern.finditer(docstring):
        params.add(match.group(1))

    return params


def run_documentation_agent(
    diff: str, changed_files: list[str], workspace_path: str
) -> DocAgentResult:
    """Convenience entry point using default LLM client."""
    return DocumentationAgent().run(diff, changed_files, workspace_path)
