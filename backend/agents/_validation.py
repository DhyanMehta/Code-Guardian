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
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

def safe_workspace_path(workspace: str, target: str) -> Path:
    root = Path(workspace).resolve()
    path = (root / target).resolve()
    if not target or path == root or not path.is_relative_to(root) or Path(target).is_absolute():
        raise ValueError("Target path must remain inside the review workspace.")
    return path


def find_function(tree, name):
    matches = []
    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = prefix + child.name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and (qualified == name or ("." not in name and child.name == name)):
                    matches.append(child)
                visit(child, qualified + ".")
            else:
                visit(child, prefix)
    visit(tree)
    return matches[0] if len(matches) == 1 else None


@dataclass(frozen=True)
class SymbolInfo:
    """Where a defined symbol lives in a source file, and what kind it is."""

    name: str
    kind: str  # "function" | "class" | "variable" | "constant"
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

    # First pass: module-level assignments in tree.body can be module-level constants
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if _is_upper_snake_case(target.id) or _is_constant_node(node.value):
                        _record(target.id, "constant", node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                if _is_upper_snake_case(node.target.id) or (
                    node.value is not None and _is_constant_node(node.value)
                ):
                    _record(node.target.id, "constant", node)

    definitions = {}
    def visit_definitions(parent, prefix=""):
        for node in ast.iter_child_nodes(parent):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = prefix + node.name
                _record(qualified, "class" if isinstance(node, ast.ClassDef) else "function", node)
                definitions.setdefault(node.name, []).append(qualified)
                visit_definitions(node, qualified + ".")
            else:
                visit_definitions(node, prefix)
    visit_definitions(tree)
    for bare, qualified in definitions.items():
        if len(qualified) == 1:
            symbols.setdefault(bare, symbols[qualified[0]])
        elif bare in symbols:
            del symbols[bare]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
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

    return find_function(tree, func_name) is not None


def get_function_params(func_name: str, file_path: str) -> set[str] | None:
    """Return the parameter names for a function, or None if not found."""
    tree = _parse_file(file_path, "param extraction")
    if tree is None:
        return None

    selected = find_function(tree, func_name)
    for node in [selected] if selected else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node is selected:
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
        "args", "arguments", "parameters", "params", "keyword args",
        "keyword arguments", "other parameters",
        "returns", "return", "raises", "yields", "yield",
        "attributes", "note", "notes", "example", "examples",
        "references", "see", "todo", "warnings", "warns",
    })

    param_pattern = re.compile(r"^\s*(\*{0,2}\w+(?:\s*,\s*\*{0,2}\w+)*)\s*(?:\([^)]*\))?\s*:")
    sphinx_pattern = re.compile(r"^\s*:param\s+(?:[^:\s]+\s+)?(\*{0,2}\w+)\s*:", re.MULTILINE)
    in_parameters = False
    entry_indent = None
    lines = docstring.expandtabs().splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        header = stripped.rstrip(":").lower()
        underlined = index + 1 < len(lines) and bool(re.fullmatch(r"\s*-{3,}\s*", lines[index + 1]))
        if (stripped.endswith(":") and header in _SECTION_HEADERS) or underlined:
            in_parameters = header in {"args", "arguments", "parameters", "params", "keyword args", "keyword arguments", "other parameters"}
            entry_indent = None
            continue
        if not in_parameters:
            continue
        match = param_pattern.match(line)
        if match:
            indent = len(line) - len(line.lstrip())
            if entry_indent is None:
                entry_indent = indent
            if indent == entry_indent:
                params.update(name.strip().lstrip("*") for name in match.group(1).split(","))
    for match in sphinx_pattern.finditer(docstring):
        params.add(match.group(1).lstrip("*"))

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
    try:
        full_path = str(safe_workspace_path(workspace_path, target_file))
        tree = ast.parse(test_code)
    except (ValueError, SyntaxError):
        return False, "Test syntax or target path is invalid."

    if not function_exists_in_file(target_function, full_path):
        return False, f"Function '{target_function}' no longer exists in {target_file}"

    target_name = target_function.rsplit(".", 1)[-1]
    if target_name == "__init__" and "." in target_function:
        target_name = target_function.rsplit(".", 1)[0].rsplit(".", 1)[-1]
    if not any(isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == target_name) or (isinstance(n.func, ast.Attribute) and n.func.attr == target_name)) for n in ast.walk(tree)):
        return False, f"Test code does not reference target function '{target_function}'"

    # Check imports in the test code reference existing modules
    import sys
    for node in ast.walk(tree):
        modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
        for module in modules:
            if not module or (isinstance(node, ast.ImportFrom) and node.level):
                return False, "Generated tests must use resolvable absolute imports."
            if module.split(".")[0] not in sys.stdlib_module_names | {"pytest", "mock"} and not module_exists(module, workspace_path):
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
    try:
        full_path = str(safe_workspace_path(workspace_path, target_file))
    except ValueError:
        return False, "Docstring target is outside the workspace."

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


def validate_naming_convention(
    symbol: str,
    info: SymbolInfo,
    claim_text: str = "",
) -> tuple[bool, str]:
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

    is_constant_claim = bool(
        re.search(r"\b(constant|upper_snake|uppercase|upper case)\b", claim_text, re.IGNORECASE)
    )

    if info.kind == "class":
        if _is_pascal_case(stripped):
            return False, f"'{symbol}' already follows PascalCase"
    elif is_constant_claim:
        if _is_upper_snake_case(stripped):
            return False, f"'{symbol}' already follows UPPER_SNAKE_CASE"
    elif info.kind == "constant" and not re.search(r"\bsnake_case\b", claim_text, re.IGNORECASE):
        if _is_upper_snake_case(stripped):
            return False, f"'{symbol}' already follows UPPER_SNAKE_CASE"
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


def _is_upper_snake_case(name: str) -> bool:
    """Return True if name is valid UPPER_SNAKE_CASE (uppercase + underscores + digits)."""
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", name))


def _is_constant_node(node: ast.AST) -> bool:
    """Return True if AST node represents an immutable/literal constant value."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_constant_node(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return (
            all(_is_constant_node(k) for k in node.keys if k is not None)
            and all(_is_constant_node(v) for v in node.values)
        )
    return False


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
