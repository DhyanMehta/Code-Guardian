"""Test-Gap Agent.

Identifies functions/branches introduced or modified in a PR diff that have no
corresponding test coverage, and drafts starter unit tests for the highest-risk gaps.

Detection is entirely deterministic (AST-based). The LLM is used ONLY to draft test
content — never to decide whether something lacks coverage.

Anti-hallucination boundary:
* Every drafted test must call a function whose name exists in the deterministic
  gaps list (function-name anchoring).
* Every drafted test must import from a module path that actually exists in the
  workspace (import validation).
* Drafted tests failing either check are dropped and logged.
"""

from __future__ import annotations

import ast
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from backend.agents._diff_utils import function_overlaps_diff, parse_diff_hunks
from backend.agents.state import (
    DraftedTest,
    FunctionInfo,
    TestGap,
    TestGapAgentResult,
    AgentOutcome,
)
from backend.tools.llm_client import LLMClient, LLMConfigError, LLMError

logger = logging.getLogger(__name__)

AGENT_NAME = "test_gap"

# Use the larger model for test drafting — embedding code inside JSON is hard
# for the 8B model, while docstring/triage tasks work fine on it.
_DRAFTING_MODEL = "openai/gpt-oss-20b"

FileReaderFn = Callable[[str], str]

_SYSTEM_PROMPT = (
    "You are a test-writing assistant. You will be given a Python function's source "
    "code (including its signature). Your ONLY job is to draft a minimal, runnable "
    "pytest unit test for this function.\n\n"
    "STRICT RULES:\n"
    "1. Import the function using the module path provided.\n"
    "2. Write exactly ONE test function named test_<function_name>.\n"
    "3. The test MUST call the target function directly.\n"
    "4. Use only standard pytest patterns (no third-party mocking libraries).\n"
    "5. Do NOT invent helper functions or modules that don't exist.\n"
    "6. Keep the test short and focused on the happy path.\n\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{"test_code": "<full pytest test code as a string>", '
    '"imports": ["<module.path.imported>"]}\n'
    "Do not include any prose outside the JSON object."
)

_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py")


def _default_file_reader(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


class TestGapAgent:
    """The Test-Gap Agent node."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        file_reader_fn: FileReaderFn | None = None,
    ) -> None:
        self._llm = llm_client
        self._analysis_errors = []
        self._llm_provided = llm_client is not None
        self._read_file = file_reader_fn or _default_file_reader

    def run(
        self,
        diff: str,
        changed_files: list[str],
        workspace_path: str,
    ) -> TestGapAgentResult:
        """Analyze the diff and identify untested functions.

        Args:
            diff: the full PR unified diff text.
            changed_files: list of changed file paths (relative to workspace).
            workspace_path: root of the checked-out repository.

        Returns:
            TestGapAgentResult with gaps and optionally drafted tests.
        """
        result = TestGapAgentResult()
        self._analysis_errors = []

        if not diff.strip():
            result.notes.append("Empty diff; nothing to analyze.")
            return result

        python_files = [f for f in changed_files if f.endswith(".py")]
        if not python_files:
            result.notes.append("No Python files changed; test-gap analysis skipped.")
            return result

        hunks = parse_diff_hunks(diff)
        modified_fns = self._extract_modified_functions(
            python_files, hunks, workspace_path
        )

        if self._analysis_errors:
            result.outcome = AgentOutcome.DEGRADED
            result.notes.extend(self._analysis_errors)
        if not modified_fns:
            result.notes.append("No functions found in diff hunks.")
            return result

        tested_symbols = self._discover_existing_tests(workspace_path)
        if self._analysis_errors:
            result.outcome = AgentOutcome.DEGRADED
            result.notes = list(dict.fromkeys(result.notes + self._analysis_errors))
        gaps = self._identify_gaps(modified_fns, tested_symbols)

        if not gaps:
            result.notes.append(
                "All modified functions have direct test references."
            )
            return result

        ranked = self._rank_by_risk(gaps)
        result.gaps = ranked

        self._draft_tests(ranked, workspace_path, result)
        return result

    def _extract_modified_functions(
        self,
        python_files: list[str],
        hunks: dict[str, list[tuple[int, int]]],
        workspace_path: str,
    ) -> list[FunctionInfo]:
        """AST-parse changed files, return functions overlapping diff hunks."""
        functions: list[FunctionInfo] = []

        for file_path in python_files:
            # Test code supplies coverage; it is not itself a target for another
            # generated test (which otherwise produces test_test_* wrappers).
            normalized = file_path.replace("\\", "/")
            if self._is_test_file(os.path.basename(normalized), os.path.join(workspace_path, os.path.dirname(normalized)), workspace_path):
                continue
            file_hunks = hunks.get(file_path)
            if not file_hunks:
                continue

            try:
                from backend.agents._validation import safe_workspace_path
                abs_path = str(safe_workspace_path(workspace_path, file_path))
                source = self._read_file(abs_path)
            except (OSError, ValueError) as exc:
                self._analysis_errors.append(f"Could not read {file_path}.")
                logger.warning("Cannot read %s: %s", file_path, exc)
                continue

            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError as exc:
                self._analysis_errors.append(f"Could not parse {file_path}.")
                logger.warning("Cannot parse %s: %s", file_path, exc)
                continue

            functions.extend(
                self._collect_functions_from_ast(tree, source, file_path, file_hunks)
            )

        return functions

    def _collect_functions_from_ast(
        self,
        tree: ast.Module,
        source: str,
        file_path: str,
        file_hunks: list[tuple[int, int]],
    ) -> list[FunctionInfo]:
        """Walk AST and collect functions whose line ranges overlap hunks."""
        results: list[FunctionInfo] = []
        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip nested functions (defined inside another function)
            if self._is_nested_function(tree, node):
                continue

            start_line = node.lineno
            end_line = node.end_lineno or node.lineno

            if not function_overlaps_diff(start_line, end_line, file_hunks):
                continue

            class_name = self._get_enclosing_class(tree, node)
            params = [
                arg.arg
                for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs + ([node.args.vararg] if node.args.vararg else []) + ([node.args.kwarg] if node.args.kwarg else [])
                if arg.arg not in ("self", "cls")
            ]
            return_ann = (
                ast.unparse(node.returns) if node.returns else None
            )

            func_source = "\n".join(source_lines[start_line - 1 : end_line])

            results.append(
                FunctionInfo(
                    name=node.name,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    source=func_source,
                    is_method=class_name is not None,
                    class_name=class_name,
                    complexity=self._compute_complexity(node),
                    params=params,
                    return_annotation=return_ann,
                )
            )

        return results

    @staticmethod
    def _is_nested_function(tree: ast.Module, target: ast.AST) -> bool:
        """Return True if target is defined inside another function."""
        for node in ast.walk(tree):
            if node is target:
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if child is target and child is not node:
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

    @staticmethod
    def _compute_complexity(node: ast.AST) -> int:
        """Count branching nodes inside a function body."""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try,
                                  ast.ExceptHandler, ast.With)):
                count += 1
        return count

    def _discover_existing_tests(self, workspace_path: str) -> set[str]:
        """Scan the full repo for test files and extract called function names."""
        called_symbols: set[str] = set()

        for root, _dirs, files in os.walk(workspace_path):
            _dirs[:] = [name for name in _dirs if name not in {".git", ".venv", "venv", "node_modules", "__pycache__"}]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if not self._is_test_file(filename, root, workspace_path):
                    continue

                abs_path = os.path.join(root, filename)
                try:
                    from backend.agents._validation import safe_workspace_path
                    safe_workspace_path(workspace_path, os.path.relpath(abs_path, workspace_path))
                    source = self._read_file(abs_path)
                except (OSError, ValueError):
                    self._analysis_errors.append(f"Could not read test file {filename}.")
                    continue

                try:
                    tree = ast.parse(source, filename=filename)
                except SyntaxError:
                    self._analysis_errors.append(f"Could not parse test file {filename}.")
                    continue

                aliases = {}
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        for item in node.names:
                            aliases[item.asname or item.name] = node.module + "." + item.name
                    elif isinstance(node, ast.Import):
                        for item in node.names:
                            aliases[item.asname or item.name] = item.name
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                        constructor = ast.unparse(node.value.func)
                        first, _, rest = constructor.partition(".")
                        if first in aliases:
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    aliases[target.id] = aliases[first] + ("." + rest if rest else "")
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        name = ast.unparse(node.func)
                        first, _, rest = name.partition(".")
                        if first in aliases:
                            called_symbols.add(aliases[first] + ("." + rest if rest else ""))

        return called_symbols

    @staticmethod
    def _is_test_file(filename: str, dirpath: str, workspace_root: str) -> bool:
        """Determine if a file is a test file by name or location."""
        if filename.startswith("test_") or filename.endswith("_test.py"):
            return True
        rel_dir = os.path.relpath(dirpath, workspace_root)
        parts = Path(rel_dir).parts
        return "tests" in parts or "test" in parts

    @staticmethod
    def _extract_call_targets(tree: ast.Module) -> set[str]:
        """Extract function names from ast.Call nodes (AST-based, not substring)."""
        targets: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                targets.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                targets.add(node.func.attr)
        return targets

    def _identify_gaps(
        self,
        modified_fns: list[FunctionInfo],
        tested_symbols: set[str],
    ) -> list[TestGap]:
        """Filter to functions with no direct test reference."""
        gaps = []
        for fn in modified_fns:
            module = self._file_to_module(fn.file_path)
            qualified = module + "." + ((fn.class_name + ".") if fn.class_name else "") + fn.name
            if qualified not in tested_symbols:
                gaps.append(TestGap(function=fn))
        return gaps

    @staticmethod
    def _rank_by_risk(gaps: list[TestGap]) -> list[TestGap]:
        """Sort gaps by risk score (higher = riskier = should be tested first)."""
        for gap in gaps:
            fn = gap.function
            raw_score = fn.complexity * 3
            body_length = fn.end_line - fn.start_line + 1
            raw_score += min(body_length, 50)
            risky_keywords = ("open(", "subprocess", "os.system", "sql",
                              "execute", "request", "connect")
            source_lower = fn.source.lower()
            for kw in risky_keywords:
                if kw in source_lower:
                    raw_score += 5
            gap.risk_score = round(min(raw_score / 10.0, 10.0), 1)

        return sorted(gaps, key=lambda g: g.risk_score, reverse=True)

    def _draft_tests(
        self,
        gaps: list[TestGap],
        workspace_path: str,
        result: TestGapAgentResult,
    ) -> None:
        """Use the LLM to draft tests for the top gaps."""
        llm = self._get_llm()
        if llm is None:
            result.notes.append("LLM not configured; returning gaps without drafts.")
            return

        for gap in gaps[:10]:
            fn = gap.function
            module_path = self._file_to_module(fn.file_path)
            user_prompt = (
                f"Module path: {module_path}\n"
                f"Function name: {fn.name}\n"
                f"Source code:\n```python\n{fn.source}\n```"
            )

            try:
                raw_response = llm.complete(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=512,
                    json_mode=True,
                )
            except LLMError as exc:
                logger.warning("LLM draft failed for %s: %s", fn.name, exc)
                result.notes.append(
                    f"LLM draft failed for '{fn.name}' ({type(exc).__name__})."
                )
                continue

            draft = self._validate_drafted_test(
                raw_response, gap, workspace_path
            )
            if draft is not None:
                result.drafted_tests.append(draft)

    def _validate_drafted_test(
        self,
        raw_response: str,
        gap: TestGap,
        workspace_path: str,
    ) -> DraftedTest | None:
        """Validate the LLM draft against anti-hallucination rules."""
        parsed = self._parse_llm_response(raw_response)
        if parsed is None:
            logger.warning(
                "Unparseable LLM draft for %s; dropping.", gap.function.name
            )
            return None

        test_code = parsed.get("test_code", "")

        if not test_code.strip():
            return None

        # Validate imports parsed from the actual code. Model-supplied metadata
        # may list imported symbols (module.function) instead of module names.
        from backend.agents._validation import validate_drafted_test
        qualified = (gap.function.class_name + "." if gap.function.class_name else "") + gap.function.name
        valid, reason = validate_drafted_test(qualified, gap.function.file_path, test_code, workspace_path)
        if not valid:
            logger.warning("Drafted test rejected: %s", reason)
            return None
        return DraftedTest(
            target_function=(gap.function.class_name + "." if gap.function.class_name else "") + gap.function.name,
            target_file=gap.function.file_path,
            test_code=test_code,
            imports_valid=True,
        )

    @staticmethod
    def _module_exists(module_path: str, workspace_path: str) -> bool:
        """Check if a dotted module path corresponds to a real file."""
        parts = module_path.split(".")
        file_path = os.path.join(workspace_path, *parts) + ".py"
        pkg_path = os.path.join(workspace_path, *parts, "__init__.py")
        return os.path.isfile(file_path) or os.path.isfile(pkg_path)

    @staticmethod
    def _file_to_module(file_path: str) -> str:
        """Convert a file path to a dotted module path."""
        without_ext = file_path.replace(".py", "")
        return without_ext.replace("/", ".").replace("\\", ".")

    def _get_llm(self) -> LLMClient | None:
        if self._llm is not None:
            return self._llm
        try:
            self._llm = LLMClient()
        except LLMConfigError as exc:
            logger.warning("LLM not configured; skipping test drafts: %s", exc)
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
            logger.warning("LLM test draft was not valid JSON: %s", exc)
            return None

        if isinstance(data, dict):
            return data
        return None


def run_test_gap_agent(
    diff: str, changed_files: list[str], workspace_path: str
) -> TestGapAgentResult:
    """Convenience entry point using default LLM client."""
    return TestGapAgent().run(diff, changed_files, workspace_path)
