"""Shared validation functions for apply-time re-validation of auto-fix data.

Extracted from test_gap_agent.py and documentation_agent.py so that the autofix
service can re-check fixes immediately before writing them to disk. These are the
same anti-hallucination checks from Session 4, but run against the current code
state at apply time (which may have diverged from review time).

:func:`collect_defined_symbols` generalizes the same AST anchoring to every kind of
definition (functions, classes, methods, module-level names) so the Quality Agent can
verify that a symbol an LLM claims to have found actually exists.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolInfo:
    """Where a defined symbol lives in a source file, and what kind it is."""

    name: str
    kind: str  # "function" | "class" | "variable"
    start_line: int
    end_line: int

    @property
    def line_count(self) -> int:
        """Number of source lines the definition spans (inclusive)."""
        return max(1, self.end_line - self.start_line + 1)


def module_exists(module_path: str, workspace_path: str) -> bool:
    """Check if a dotted module path corresponds to a real file on disk."""
    parts = module_path.split(".")
    file_path = os.path.join(workspace_path, *parts) + ".py"
    pkg_path = os.path.join(workspace_path, *parts, "__init__.py")
    return os.path.isfile(file_path) or os.path.isfile(pkg_path)


def _parse_file(file_path: str, purpose: str) -> ast.AST | None:
    """Parse a source file, returning ``None`` when it is missing or unparseable."""
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        return ast.parse(source)
    except (SyntaxError, OSError) as exc:
        logger.warning("Cannot parse %s for %s: %s", file_path, purpose, exc)
        return None


def collect_defined_symbols(file_path: str) -> dict[str, SymbolInfo] | None:
    """Map every symbol defined in ``file_path`` to its :class:`SymbolInfo`.

    Covers functions, async functions, classes, methods (recorded under their bare
    name), and module-level assignments — i.e. everything an LLM could plausibly
    claim a quality violation is "about". The first definition of a name wins.

    Returns:
        The symbol table, or ``None`` if the file is missing or cannot be parsed.
        ``None`` and ``{}`` mean different things: unknown versus genuinely empty.
    """
    tree = _parse_file(file_path, "symbol collection")
    if tree is None:
        return None

    symbols: dict[str, SymbolInfo] = {}

    def _record(name: str, kind: str, node: ast.AST) -> None:
        if not name or name in symbols:
            return
        start = getattr(node, "lineno", 0) or 0
        end = getattr(node, "end_lineno", None) or start
        symbols[name] = SymbolInfo(
            name=name, kind=kind, start_line=start, end_line=end
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _record(node.name, "function", node)
        elif isinstance(node, ast.ClassDef):
            _record(node.name, "class", node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    _record(target.id, "variable", node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                _record(node.target.id, "variable", node)

    return symbols


def symbol_exists_in_file(symbol: str, file_path: str) -> bool:
    """Check whether ``symbol`` is defined anywhere in ``file_path`` via AST."""
    symbols = collect_defined_symbols(file_path)
    return symbols is not None and symbol in symbols


def function_exists_in_file(func_name: str, file_path: str) -> bool:
    """Check if a function/method with the given name exists in the file via AST."""
    tree = _parse_file(file_path, "validation")
    if tree is None:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return True
    return False


def get_function_params(func_name: str, file_path: str) -> set[str] | None:
    """Return the parameter names for a function, or None if not found."""
    tree = _parse_file(file_path, "param extraction")
    if tree is None:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                params = set()
                for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    if arg.arg != "self" and arg.arg != "cls":
                        params.add(arg.arg)
                if node.args.vararg:
                    params.add(node.args.vararg.arg)
                if node.args.kwarg:
                    params.add(node.args.kwarg.arg)
                return params
    return None


def extract_documented_params(docstring: str) -> set[str]:
    """Extract parameter names from a Google/NumPy/Sphinx-style docstring."""
    params: set[str] = set()
    _SECTION_HEADERS = frozenset({
        "args", "arguments", "parameters", "params",
        "returns", "return", "raises", "yields", "yield",
        "attributes", "note", "notes", "example", "examples",
        "references", "see", "todo", "warnings", "warns",
    })

    param_pattern = re.compile(r"^\s+(\w+)\s*[\(:]", re.MULTILINE)
    sphinx_pattern = re.compile(r":param\s+(\w+)\s*:", re.MULTILINE)

    for match in param_pattern.finditer(docstring):
        name = match.group(1)
        if name.lower() not in _SECTION_HEADERS:
            params.add(name)

    for match in sphinx_pattern.finditer(docstring):
        params.add(match.group(1))

    return params


def validate_drafted_test(
    target_function: str,
    target_file: str,
    test_code: str,
    workspace_path: str,
) -> tuple[bool, str]:
    """Re-validate a drafted test at apply time.

    Returns (is_valid, reason). If invalid, reason explains why.
    """
    full_path = os.path.join(workspace_path, target_file)

    if not function_exists_in_file(target_function, full_path):
        return False, f"Function '{target_function}' no longer exists in {target_file}"

    if target_function not in test_code:
        return False, f"Test code does not reference target function '{target_function}'"

    # Check imports in the test code reference existing modules
    import_lines = [
        line.strip() for line in test_code.split("\n")
        if line.strip().startswith(("import ", "from "))
    ]
    for line in import_lines:
        module = _extract_module_from_import(line)
        if module and not module.startswith(("pytest", "unittest", "mock", "os", "sys")):
            if not module_exists(module, workspace_path):
                return False, f"Import references non-existent module '{module}'"

    return True, ""


def validate_drafted_docstring(
    target_function: str,
    target_file: str,
    docstring: str,
    workspace_path: str,
) -> tuple[bool, str]:
    """Re-validate a drafted docstring at apply time.

    Returns (is_valid, reason). If invalid, reason explains why.
    """
    full_path = os.path.join(workspace_path, target_file)

    if not function_exists_in_file(target_function, full_path):
        return False, f"Function '{target_function}' no longer exists in {target_file}"

    actual_params = get_function_params(target_function, full_path)
    if actual_params is None:
        return False, f"Cannot extract parameters for '{target_function}' in {target_file}"

    documented_params = extract_documented_params(docstring)
    invalid_params = documented_params - actual_params
    if invalid_params:
        return False, (
            f"Docstring references parameters not in function signature: "
            f"{sorted(invalid_params)}"
        )

    return True, ""


def validate_naming_convention(symbol: str, info: SymbolInfo) -> tuple[bool, str]:
    """Check if a symbol actually violates a naming convention.

    Returns (violates, reason). If ``violates`` is False, the symbol conforms to
    the expected convention for its kind and any finding claiming otherwise is a
    false positive.
    """
    if not symbol or symbol.startswith("_"):
        stripped = symbol.lstrip("_")
        if not stripped:
            return False, "dunder/private names are not subject to public naming rules"
    else:
        stripped = symbol

    if info.kind == "class":
        if _is_pascal_case(stripped):
            return False, f"'{symbol}' already follows PascalCase"
    else:
        if _is_snake_case(stripped):
            return False, f"'{symbol}' already follows snake_case"

    return True, ""


def _is_snake_case(name: str) -> bool:
    """Return True if name is valid snake_case (lowercase + underscores + digits)."""
    return bool(re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name))


def _is_pascal_case(name: str) -> bool:
    """Return True if name is valid PascalCase (starts upper, no underscores)."""
    return bool(re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name))


def _extract_module_from_import(import_line: str) -> str | None:
    """Extract the top-level module from an import statement."""
    line = import_line.strip()
    if line.startswith("from "):
        parts = line.split()
        if len(parts) >= 2:
            return parts[1].split(".")[0] if "." in parts[1] else parts[1]
    elif line.startswith("import "):
        parts = line.split()
        if len(parts) >= 2:
            module = parts[1].rstrip(",")
            return module.split(".")[0] if "." in module else module
    return None
