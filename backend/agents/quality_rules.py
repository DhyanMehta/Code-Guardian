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

from backend.rag.retriever import RetrievedPassage


@dataclass(frozen=True)
class SupportedRule:
    name: str
    threshold: int | None
    passage: RetrievedPassage


_FOREIGN_LANGUAGE = re.compile(r"\b(?:javascript|typescript|tsx|jsx|java|golang|rust)\b", re.I)
_LENGTH = re.compile(r"\b(?:function|method)s?\b[^.]*?\b(?:not exceed|at most|maximum of)\s+(\d+)\s+lines", re.I)
_PARAMETERS = re.compile(r"\b(?:function|method)s?\b[^.]*?\b(\d+)\s+or fewer positional parameters", re.I)
_FUTURE = re.compile(r"\b(?:use|include|require|requires|must have)\s+(?:the\s+)?[`\"]?from __future__ import annotations", re.I)


def supported_rules(passages: list[RetrievedPassage]) -> tuple[list[SupportedRule], list[str]]:
    """Return only unambiguous supported rules, keeping their exact citations."""
    candidates: dict[str, dict[int | None, SupportedRule]] = {}
    for passage in passages:
        plain = passage.text.replace('*', '')
        language = plain + ' ' + passage.source_file
        if _FOREIGN_LANGUAGE.search(language) and not re.search(r'\bpython\b', language, re.I):
            continue
        # A paragraph explicitly scoped to another language must not constrain Python.
        for paragraph in re.split(r'\n\s*\n', plain):
            if _FOREIGN_LANGUAGE.search(paragraph) and not re.search(r'\bpython\b', paragraph, re.I):
                continue
            for name, pattern in (('maximum_function_length', _LENGTH),
                                  ('maximum_positional_parameters', _PARAMETERS)):
                # Physical-span policies need different semantics; never call them logic lines.
                if name == 'maximum_function_length' and re.search(r'physical|including (?:the )?docstring', paragraph, re.I):
                    continue
                for match in pattern.finditer(paragraph):
                    threshold = int(match[1])
                    candidates.setdefault(name, {}).setdefault(threshold, SupportedRule(name, threshold, passage))
            if _FUTURE.search(paragraph) and not re.search(r'\b(?:do not|never|optional|need not)\b', paragraph, re.I):
                name = 'future_annotations_import'
                candidates.setdefault(name, {}).setdefault(None, SupportedRule(name, None, passage))
    rules, notes = [], []
    for name, by_threshold in candidates.items():
        if len(by_threshold) == 1:
            rules.append(next(iter(by_threshold.values())))
        else:
            notes.append(f'Conflicting retrieved thresholds for {name}; no deterministic rule enforced.')
    return rules, notes


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
