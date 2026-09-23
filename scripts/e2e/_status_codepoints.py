"""Print the Agent Status rows of a posted comment as explicit codepoints.

Console re-encoding makes glyphs unreadable in captured output, so assert on the
actual characters instead of how a terminal renders them.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import gh_headers, target

t = target()
comments = requests.get(
    f"https://api.github.com/repos/{t['repo_full_name']}"
    f"/issues/{t['pr_number']}/comments",
    headers=gh_headers(), timeout=30,
).json()
body = comments[-1]["body"]
print(f"comment id={comments[-1]['id']}  url={comments[-1]['html_url']}\n")

CHECK = "\u2705"
WARN = "\u26a0"
CROSS = "\u274c"

for line in body.splitlines():
    if not line.startswith("| ") or line.startswith("| Agent") or line.startswith("|--"):
        continue
    agent = line.split("|")[1].strip()
    glyphs = [
        f"U+{ord(ch):04X} {unicodedata.name(ch, '?')}"
        for ch in line
        if ord(ch) > 0x2000
    ]
    print(f"{agent}:")
    print(f"    has CHECK  (U+2705): {CHECK in line}")
    print(f"    has WARNING(U+26A0): {WARN in line}")
    print(f"    has CROSS  (U+274C): {CROSS in line}")
    print(f"    non-ascii codepoints: {glyphs}")
    print(f"    text: {line.encode('ascii', 'backslashreplace').decode()}")
    print()
