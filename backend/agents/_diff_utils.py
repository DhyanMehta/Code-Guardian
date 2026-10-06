"""Shared diff-parsing utilities for Test-Gap and Documentation agents.

Parses unified diffs into structured hunk data so agents can determine which
functions were introduced or modified in a PR.
"""

from __future__ import annotations

import re
import ast

_HUNK_HEADER_RE = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
)

_FILE_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$")


def parse_diff_hunks(diff: str) -> dict[str, list[tuple[int, int]]]:
    """Parse a unified diff into added/modified line ranges per file.

    Returns:
        Mapping of ``{file_path: [(start_line, end_line), ...]}`` where each
        tuple represents a contiguous range of new/modified lines (1-indexed,
        inclusive on both ends).
    """
    result: dict[str, list[tuple[int, int]]] = {}
    current_file: str | None = None
    new_line = 0
    in_hunk = False

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            in_hunk = False
        if line.startswith('+++ "'):
            try:
                line = "+++ " + ast.literal_eval(line[4:])
            except (ValueError, SyntaxError):
                continue
        if line == "+++ /dev/null":
            current_file = None
            in_hunk = False
            continue
        file_match = _FILE_HEADER_RE.match(line)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in result:
                result[current_file] = []
            continue

        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match and current_file is not None:
            new_line = int(hunk_match.group(1))
            in_hunk = True
            continue
        if in_hunk and current_file is not None:
            if line.startswith("+"):
                result[current_file].append((new_line, new_line))
                new_line += 1
            elif line.startswith("-"):
                result[current_file].append((max(1, new_line), max(1, new_line)))
            elif line.startswith(" "):
                new_line += 1

    # Collapse adjacent changed lines without including unchanged hunk context.
    for path, ranges in result.items():
        merged = []
        for start, end in sorted(set(ranges)):
            if merged and start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        result[path] = merged

    return result


def function_overlaps_diff(
    func_start: int,
    func_end: int,
    hunks: list[tuple[int, int]],
) -> bool:
    """Check if a function's line range overlaps any diff hunk.

    All values are 1-indexed, inclusive.
    """
    for hunk_start, hunk_end in hunks:
        if func_start <= hunk_end and func_end >= hunk_start:
            return True
    return False


def bounded_diff_batches(diff: str, limit: int = 5000) -> list[str]:
    """Split file hunks without losing changed lines or their original offsets."""
    batches = []
    headers = []
    body = []
    old = new = 0
    header_pattern = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    def flush():
        nonlocal old, new, body
        if not body:
            return
        old_count = sum(line.startswith((" ", "-")) for line in body)
        new_count = sum(line.startswith((" ", "+")) for line in body)
        batches.append("".join(headers) + f"@@ -{old},{old_count} +{new},{new_count} @@\n" + "".join(body))
        old += old_count
        new += new_count
        body = []

    for line in diff.splitlines(keepends=True):
        match = header_pattern.match(line)
        if line.startswith("diff --git "):
            flush()
            headers = [line]
        elif line.startswith("--- "):
            flush()
            headers = [line]
        elif line.startswith("+++ "):
            headers.append(line)
        elif match:
            flush()
            old, new = int(match[1]), int(match[2])
        elif headers and line.startswith((" ", "+", "-", "\\")):
            if body and sum(map(len, body)) + sum(map(len, headers)) + len(line) + 80 > limit:
                flush()
            body.append(line)
    flush()
    return batches or [diff]
