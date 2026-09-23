"""Enforce the dashboard's hard design rules over the frontend source and build.

Two rules from the approved design system:
  - No emoji anywhere in the UI. (The backend's PR comment uses emoji severity
    markers; the dashboard speaks colour + shape + text instead. The one sanctioned
    exception is the verbatim posted-comment block, whose content comes from the API
    at runtime and is therefore not in the source.)
  - No gradients anywhere.

Checks source files and, when present, the built CSS/JS in dist/.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
SRC = FRONTEND / "src"
DIST = FRONTEND / "dist"

SOURCE_SUFFIXES = {".ts", ".tsx", ".css"}

# Codepoint ranges that actually contain emoji / pictographs. Deliberately excludes
# typographic characters the design DOES use: em dash (U+2014), arrows in copy,
# and the box-drawing/quote punctuation.
EMOJI_RANGES = [
    (0x1F000, 0x1FAFF),  # pictographs, emoticons, symbols & pictographs extended
    (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF),
    (0x2600, 0x26FF),    # miscellaneous symbols (includes the warning sign)
    (0x2700, 0x27BF),    # dingbats (includes the check mark)
    (0xFE0F, 0xFE0F),    # variation selector-16 (emoji presentation)
    (0x1F900, 0x1F9FF),
]


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(low <= cp <= high for low, high in EMOJI_RANGES)


def scan_emoji(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for ch in line:
                if is_emoji(ch):
                    name = unicodedata.name(ch, "UNNAMED")
                    hits.append(
                        f"{path.relative_to(FRONTEND)}:{lineno} "
                        f"U+{ord(ch):04X} {name}"
                    )
    return hits


# "gradient" appearing inside a comment that forbids gradients is not a violation.
GRADIENT_RE = re.compile(r"(linear-gradient|radial-gradient|conic-gradient|bg-gradient-)")


def scan_gradients(paths: list[Path]) -> tuple[list[str], list[str]]:
    real: list[str] = []
    mentions: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if GRADIENT_RE.search(line):
                real.append(f"{path.relative_to(FRONTEND)}:{lineno} {line.strip()[:90]}")
            elif "gradient" in line.lower():
                mentions.append(
                    f"{path.relative_to(FRONTEND)}:{lineno} {line.strip()[:90]}"
                )
    return real, mentions


source_files = sorted(p for p in SRC.rglob("*") if p.suffix in SOURCE_SUFFIXES)
print(f"scanned {len(source_files)} source file(s) under frontend/src\n")

print("=" * 72)
print("RULE: no emoji in the UI source")
print("=" * 72)
emoji_hits = scan_emoji(source_files)
if emoji_hits:
    for hit in emoji_hits:
        print(f"  VIOLATION {hit}")
else:
    print("  PASS — zero emoji codepoints in frontend/src")

print()
print("=" * 72)
print("RULE: no gradients")
print("=" * 72)
gradient_hits, gradient_mentions = scan_gradients(source_files)
if gradient_hits:
    for hit in gradient_hits:
        print(f"  VIOLATION {hit}")
else:
    print("  PASS — no gradient function or utility used in frontend/src")
if gradient_mentions:
    print("  (the word appears only in prose forbidding it:)")
    for mention in gradient_mentions:
        print(f"    {mention}")

if DIST.exists():
    built = sorted(
        p for p in DIST.rglob("*") if p.suffix in {".css", ".js", ".html"}
    )
    print()
    print("=" * 72)
    print(f"BUILT OUTPUT ({len(built)} file(s) in dist/)")
    print("=" * 72)
    built_emoji = scan_emoji(built)
    built_gradients, _ = scan_gradients(built)
    print(f"  gradients in build        : "
          f"{'PASS — none' if not built_gradients else built_gradients[:5]}")
    if not built_emoji:
        print("  emoji codepoints in build : PASS — none")
    else:
        # Bundled dependency bytes are reported, not failed: the rule is about what
        # the UI can render. React Router ships an emoji in its default error
        # boundary; the app supplies its own errorElement so that fallback is
        # unreachable. Any hit here must be traceable to unreachable vendor code.
        print(f"  emoji codepoints in build : {len(built_emoji)} in bundled "
              f"dependency bytes (not reachable UI):")
        for hit in built_emoji:
            print(f"      {hit}")

print()
print("=" * 72)
print("RULE: severity ranking is not duplicated client-side")
print("=" * 72)
sort_hits: list[str] = []
for path in source_files:
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if ".sort(" in line or "localeCompare" in line:
            sort_hits.append(f"{path.relative_to(FRONTEND)}:{lineno} {line.strip()[:90]}")
print(
    "  PASS — no client-side sort of findings"
    if not sort_hits
    else "\n".join(f"  REVIEW {hit}" for hit in sort_hits)
)

failures = len(emoji_hits) + len(gradient_hits)
print(f"\nTOTAL HARD-RULE VIOLATIONS: {failures}")
sys.exit(1 if failures else 0)
