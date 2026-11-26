"""Supported Python predicates shared by discovery and proposal validation.

This is deliberately not a general natural-language policy interpreter. Only
the existing length, positional-parameter and future-annotations rules with
explicit applicable passages are executable. Other interpretations stay advisory.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.rag.retriever import RetrievedPassage


@dataclass(frozen=True)
class SupportedRule:
    name: str
    threshold: int | None
    passage: RetrievedPassage


_PYTHON_LANGUAGE = re.compile(r"\bpython\b", re.I)
_FRONTEND_LANGUAGE = re.compile(r"\b(?:javascript|typescript|tsx|jsx)\b", re.I)
_FOREIGN_LANGUAGE = re.compile(
    r"\b(?:javascript|typescript|tsx|jsx|java|golang|rust|c\+\+|cpp|c#|csharp|ruby|php|swift|kotlin|scala)\b",
    re.I,
)
_OTHER_NON_FRONTEND_LANGUAGE = re.compile(
    r"\b(?:python|java|golang|rust|c\+\+|cpp|c#|csharp|ruby|php|swift|kotlin|scala)\b",
    re.I,
)
_UNIVERSAL_LANGUAGE = re.compile(r"\b(?:all languages|every language|language[- ]agnostic)\b", re.I)
_LENGTH = re.compile(r"\b(?:function|method)s?\b[^.]*?\b(?:not exceed|at most|maximum of)\s+(\d+)\s+lines", re.I)
_PARAMETERS = re.compile(r"\b(?:function|method)s?\b[^.]*?\b(\d+)\s+or fewer positional parameters", re.I)
_FUTURE = re.compile(r"\b(?:use|include|require|requires|must have)\s+(?:the\s+)?[`\"]?from __future__ import annotations", re.I)
_NEGATION = re.compile(r"\b(?:do not|don't|never|not required|need not|no need to|optional(?:ly)?|avoid requiring)\b", re.I)
_OPTOUT = re.compile(r"\b(?:disable|disabled|opt[- ]?out|do not enforce|skip)\b", re.I)
_STANDARDS_DIR = Path(__file__).resolve().parents[1] / "rag" / "standards"


def _split_items(plain: str) -> list[str]:
    """Split markdown text into individual list items or paragraphs."""
    items: list[str] = []
    for block in re.split(r"\n\s*\n", plain):
        current: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", line):
                if current:
                    items.append(" ".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            items.append(" ".join(current))
    return items


@lru_cache(maxsize=1)
def baseline_passages() -> tuple[RetrievedPassage, ...]:
    """Load bundled default coding-standards sections as baseline passages."""
    passages: list[RetrievedPassage] = []
    if _STANDARDS_DIR.is_dir():
        for path in sorted(_STANDARDS_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            sections = re.split(r"(?=^##\s+)", text, flags=re.MULTILINE)
            for idx, section in enumerate(s.strip() for s in sections if s.strip()):
                passages.append(
                    RetrievedPassage(
                        text=section,
                        source_file=path.name,
                        distance=0.0,
                        chunk_id=f"baseline:{path.name}:{idx}",
                    )
                )
    if not passages:
        passages.append(
            RetrievedPassage(
                text=(
                    "A single Python function or method should not exceed 40 lines of logic "
                    "(excluding blank lines, decorators, and the docstring).\n"
                    "Functions should accept 5 or fewer positional parameters.\n"
                    "Use `from __future__ import annotations` at the top of every Python module."
                ),
                source_file="python_coding_standards.md",
                distance=0.0,
                chunk_id="baseline:fallback:0",
            )
        )
    return tuple(passages)


def _item_applies(item: str, passage_text: str, source_file: str, target_language: str) -> bool:
    """Return whether a markdown rule item applies to target_language ('python' or 'frontend')."""
    if target_language == "frontend":
        item_has_frontend = bool(_FRONTEND_LANGUAGE.search(item) or _UNIVERSAL_LANGUAGE.search(item))
        passage_has_frontend = bool(
            _FRONTEND_LANGUAGE.search(passage_text)
            or _FRONTEND_LANGUAGE.search(source_file)
            or _UNIVERSAL_LANGUAGE.search(passage_text)
        )
        if not (item_has_frontend or passage_has_frontend):
            return False
        if _OTHER_NON_FRONTEND_LANGUAGE.search(item) and not _FRONTEND_LANGUAGE.search(item):
            return False
        if _OTHER_NON_FRONTEND_LANGUAGE.search(source_file) and not (
            _FRONTEND_LANGUAGE.search(source_file) or _FRONTEND_LANGUAGE.search(passage_text)
        ):
            return False
        return True

    passage_scope = passage_text + " " + source_file
    if _FOREIGN_LANGUAGE.search(source_file) and not _PYTHON_LANGUAGE.search(source_file):
        return False
    if _FOREIGN_LANGUAGE.search(passage_scope) and not _PYTHON_LANGUAGE.search(passage_scope):
        return False
    if _FOREIGN_LANGUAGE.search(item) and not _PYTHON_LANGUAGE.search(item):
        return False
    return True


def _detect_optouts(item: str, disabled: set[str]) -> None:
    if not (_OPTOUT.search(item) or _NEGATION.search(item)):
        return
    if _LENGTH.search(item) or re.search(r"\b(?:maximum_function_length|function length)\b", item, re.I):
        disabled.add("maximum_function_length")
    if _PARAMETERS.search(item) or re.search(r"\b(?:maximum_positional_parameters|positional parameters?)\b", item, re.I):
        disabled.add("maximum_positional_parameters")
    if _FUTURE.search(item) or re.search(r"\b(?:future_annotations_import|from __future__ import annotations)\b", item, re.I):
        disabled.add("future_annotations_import")


def extract_rules(
    passages: list[RetrievedPassage],
    *,
    target_language: str = "python",
) -> tuple[list[SupportedRule], list[str], set[str], set[str]]:
    """Extract unambiguous supported rules, conflict notes, opt-outs, and conflicts."""
    candidates: dict[str, dict[int | None, SupportedRule]] = {}
    disabled: set[str] = set()
    for passage in passages:
        plain = passage.text.replace("*", "")
        for item in _split_items(plain):
            if not _item_applies(item, plain, passage.source_file, target_language):
                continue
            _detect_optouts(item, disabled)
            if _NEGATION.search(item):
                continue
            for name, pattern in (
                ("maximum_function_length", _LENGTH),
                ("maximum_positional_parameters", _PARAMETERS),
            ):
                if name == "maximum_function_length" and re.search(r"physical|including (?:the )?docstring", item, re.I):
                    continue
                for match in pattern.finditer(item):
                    threshold = int(match[1])
                    candidates.setdefault(name, {}).setdefault(threshold, SupportedRule(name, threshold, passage))
            if target_language == "python" and _FUTURE.search(item):
                name = "future_annotations_import"
                candidates.setdefault(name, {}).setdefault(None, SupportedRule(name, None, passage))

    rules: list[SupportedRule] = []
    notes: list[str] = []
    conflicted: set[str] = set()
    for name, by_threshold in candidates.items():
        if len(by_threshold) == 1:
            if name not in disabled:
                rules.append(next(iter(by_threshold.values())))
        else:
            conflicted.add(name)
            notes.append(f"Conflicting retrieved thresholds for {name}; no deterministic rule enforced.")
    return rules, notes, disabled, conflicted


def supported_rules(passages: list[RetrievedPassage]) -> tuple[list[SupportedRule], list[str]]:
    """Return only unambiguous supported Python rules, keeping their exact citations."""
    rules, notes, _, _ = extract_rules(passages, target_language="python")
    return rules, notes


def resolve_supported_rules(
    retrieved_passages: list[RetrievedPassage],
    *,
    policy_passages: list[RetrievedPassage] | None = None,
    target_language: str = "python",
    include_baseline: bool = True,
) -> tuple[list[SupportedRule], list[str]]:
    """Merge custom/retrieved rules over built-in baseline rules with explicit precedence."""
    combined: list[RetrievedPassage] = []
    seen: set[tuple[str, str]] = set()
    for passage in [*(policy_passages or []), *retrieved_passages]:
        key = (passage.source_file, passage.text)
        if key not in seen:
            seen.add(key)
            combined.append(passage)

    custom_rules, notes, disabled, conflicted = extract_rules(combined, target_language=target_language)
    if not include_baseline:
        return custom_rules, notes

    base_rules, _, _, _ = extract_rules(list(baseline_passages()), target_language=target_language)
    merged: dict[str, SupportedRule] = {
        rule.name: rule
        for rule in base_rules
        if rule.name not in disabled and rule.name not in conflicted
    }
    for rule in custom_rules:
        merged[rule.name] = rule
    return list(merged.values()), notes


def functions(tree: ast.AST):
    """Yield lexical names, including methods/nested functions without bare-name collisions."""
    def visit(parent, prefix='', method=False):
        for node in ast.iter_child_nodes(parent):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                if not isinstance(node, ast.ClassDef):
                    yield name, node, method
                yield from visit(node, name + '.', isinstance(node, ast.ClassDef))
            else:
                yield from visit(node, prefix, method)
    yield from visit(tree)


def logic_lines(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count nonblank body lines bearing tokens, excluding comments and the docstring.

    Signature/decorators are outside the body. Token positions distinguish a
    comment from a '#' inside a string, and preserve code sharing a docstring line.
    Closing delimiters count, consistently with the pinned 42/49/226 measurements.
    """
    first = node.body[0].lineno
    doc = node.body[0] if ast.get_docstring(node) is not None else None
    lines = source.splitlines()
    occupied = set()
    ignored = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
               tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in ignored or token.string == ';':
            continue
        if doc and doc.lineno <= token.start[0] <= doc.end_lineno and token.type == tokenize.STRING:
            continue
        for line in range(max(first, token.start[0]), min(node.end_lineno, token.end[0]) + 1):
            if lines[line - 1].strip():
                occupied.add(line)
    return len(occupied)


def positional_parameters(node, *, method: bool = False) -> int:
    args = list(node.args.posonlyargs + node.args.args)
    static = any(isinstance(d, ast.Name) and d.id == 'staticmethod' for d in node.decorator_list)
    if method and not static and args and args[0].arg in {'self', 'cls'}:
        args.pop(0)
    return len(args)


def evaluate(rule: SupportedRule, source: str, tree: ast.AST, symbol: str, node=None, *, method=False):
    """Return a recomputed violation and explanation, never model measurements."""
    if rule.name == 'future_annotations_import':
        present = any(isinstance(n, ast.ImportFrom) and n.module == '__future__'
                      and any(a.name == 'annotations' for a in n.names) for n in tree.body)
        return not present, ('The required annotations future import is absent from the pinned module.'
                             if not present else 'The pinned module already imports annotations from __future__.')
    if node is None:
        return None, None
    if rule.name == 'maximum_function_length':
        count = logic_lines(source, node)
        return count > rule.threshold, f'{symbol} contains {count} nonblank logic lines; the cited limit is {rule.threshold}.'
    if rule.name == 'maximum_positional_parameters':
        count = positional_parameters(node, method=method)
        return count > rule.threshold, f'{symbol} accepts {count} positional parameters; the cited limit is {rule.threshold}.'
    return None, None
