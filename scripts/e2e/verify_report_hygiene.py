"""Issues B + C verification against a fresh real review.

B: no absolute local path may appear in the stored findings, the rendered report,
   or the comment actually posted to GitHub.
C: the Agent Status table must distinguish "ran, found nothing" from "could not run",
   driven by the structured outcome rather than note text.

Usage:  python scripts/e2e/verify_report_hygiene.py [review_id]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import BASE_URL, gh_headers, target

t = target()
if len(sys.argv) > 1:
    review_id = int(sys.argv[1])
else:
    review_id = json.loads(
        (Path(__file__).resolve().parent / "e2e_review.json").read_text(encoding="utf-8")
    )["review_id"]

print("=" * 72)
print(f"ISSUES B + C — review {review_id}")
print("=" * 72)

detail = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=30).json()
print(f"status  : {detail['status']}")
print(f"summary : {detail['summary']}")
print(f"commit  : {detail['commit_sha'][:8]}")

# ------------------------------------------------------------------ #
# B: absolute-path scan
# ------------------------------------------------------------------ #
ABS_PATTERNS = [
    (r"[A-Za-z]:\\", "windows drive-letter path"),
    (r"/tmp/", "posix temp path"),
    (r"codeguardian_[0-9a-z_]{6,}", "temp workspace directory name"),
    (r"AppData\\Local\\Temp", "windows temp path"),
]


def scan(label: str, text: str) -> int:
    hits = 0
    for pattern, desc in ABS_PATTERNS:
        found = re.findall(pattern, text)
        if found:
            hits += len(found)
            print(f"    LEAK in {label}: {len(found)}x {desc} -> {sorted(set(found))[:3]}")
    if not hits:
        print(f"    {label}: clean")
    return hits


print()
print("-" * 72)
print("B. ABSOLUTE PATH SCAN")
print("-" * 72)

total_leaks = 0

print("  stored finding file_path values (from the database):")
all_paths = []
for agent, items in (detail.get("findings_by_agent") or {}).items():
    for f in items:
        all_paths.append((agent, f["file_path"], f["line"], f["title"]))
for agent, path, line, title in all_paths:
    flag = ""
    if path and (re.match(r"^[A-Za-z]:\\", path) or path.startswith("/")):
        flag = "   <== ABSOLUTE"
        total_leaks += 1
    print(f"    [{agent:13}] {path}:{line}{flag}")

print()
print("  full API detail payload:")
total_leaks += scan("GET /reviews/{id}", json.dumps(detail))

report = requests.get(f"{BASE_URL}/reviews/{review_id}/report", timeout=30)
markdown = report.json().get("markdown", "") if report.status_code == 200 else ""
print(f"\n  rendered report (GET /reviews/{{id}}/report -> {report.status_code}, "
      f"{len(markdown)} chars):")
total_leaks += scan("rendered markdown", markdown)

comments = requests.get(
    f"https://api.github.com/repos/{t['repo_full_name']}"
    f"/issues/{t['pr_number']}/comments",
    headers=gh_headers(), timeout=30,
).json()
posted = comments[-1]["body"] if comments else ""
print(f"\n  comment actually posted on GitHub (id={comments[-1]['id'] if comments else '-'}, "
      f"{len(posted)} chars):")
total_leaks += scan("posted PR comment", posted)

print(f"\n  TOTAL absolute-path leaks: {total_leaks} (must be 0)")

# ------------------------------------------------------------------ #
# C: agent status table
# ------------------------------------------------------------------ #
print()
print("-" * 72)
print("C. AGENT STATUS TABLE (from the posted comment)")
print("-" * 72)
in_table = False
for line in posted.splitlines():
    if line.startswith("### Agent Status"):
        in_table = True
    elif in_table and line.startswith("---"):
        break
    if in_table and line.strip():
        print(f"    {line}")

status_line = next(
    (l for l in posted.splitlines() if l.startswith("**Status**")), "(none)"
)
print(f"\n  status line: {status_line}")
banner = [l for l in posted.splitlines() if "Incomplete review" in l]
print(f"  incomplete-review banner present: {bool(banner)}")
for b in banner:
    print(f"    {b}")

print()
print("-" * 72)
print("QUALITY FINDINGS STORED FOR THIS REVIEW")
print("-" * 72)
quality = (detail.get("findings_by_agent") or {}).get("quality", [])
print(f"  count: {len(quality)}")
for f in quality:
    print(f"    [{f['severity']:6}] {f['title']}  @ {f['file_path']}:{f['line']}")
    print(f"             {f['detail'][:120]}")
