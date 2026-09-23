"""Locate the emoji found in the built bundle and attribute them to a dependency."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"

bundle = sorted((FRONTEND / "dist" / "assets").glob("index-*.js"))[-1]
text = bundle.read_text(encoding="utf-8")

for ch in ("\U0001F4BF", "\U0001F44B"):
    for match in re.finditer(re.escape(ch), text):
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 160)
        print(f"--- U+{ord(ch):04X} {unicodedata.name(ch)} @ offset {match.start()} ---")
        print(text[start:end].replace("\n", " "))
        print()

print("=" * 72)
print("Which installed package ships these codepoints?")
print("=" * 72)
node_modules = FRONTEND / "node_modules"
for package in ("react-router", "react-router-dom", "react-dom", "react", "recharts"):
    root = node_modules / package
    if not root.exists():
        continue
    found: list[str] = []
    for path in root.rglob("*.js"):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "\U0001F4BF" in content or "\U0001F44B" in content:
            found.append(str(path.relative_to(node_modules)))
            if len(found) >= 3:
                break
    print(f"  {package}: {found or 'none'}")
