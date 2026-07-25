"""Shared diff-parsing utilities for Test-Gap and Documentation agents.

Parses unified diffs into structured hunk data so agents can determine which
functions were introduced or modified in a PR.
"""

from __future__ import annotations

import re

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

    for line in diff.splitlines():
        file_match = _FILE_HEADER_RE.match(line)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in result:
                result[current_file] = []
            continue

        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match and current_file is not None:
            start = int(hunk_match.group(1))
            length = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            if length > 0:
                end = start + length - 1
                result[current_file].append((start, end))

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
