"""Step 5: verify the real PR comment posted on GitHub.

Fetches the actual issue comments from the PR via the GitHub API and prints the
comment verbatim, then cross-checks that every deliberately planted issue is
represented and that the Agent Status block reflects all three scanners.
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
review_id = json.loads(
    (Path(__file__).resolve().parent / "e2e_review.json").read_text(encoding="utf-8")
)["review_id"]

print("=" * 70)
print("STEP 5 — verify the real PR comment on GitHub")
print("=" * 70)

url = (
    f"https://api.github.com/repos/{t['repo_full_name']}"
    f"/issues/{t['pr_number']}/comments"
)
r = requests.get(url, headers=gh_headers(), timeout=30)
print(f"GET {url} -> HTTP {r.status_code}")
if r.status_code != 200:
    print(r.text[:400])
    sys.exit(1)

comments = r.json()
print(f"comments on PR #{t['pr_number']}: {len(comments)}")
if not comments:
    print("\nFAIL: no comment was posted on the PR")
    sys.exit(1)

comment = comments[-1]
print(f"  id={comment['id']} author={comment['user']['login']} "
      f"created={comment['created_at']}")
print(f"  url={comment['html_url']}")
body = comment["body"]

print()
print("=" * 70)
print("ACTUAL PR COMMENT BODY (verbatim)")
print("=" * 70)
print(body)
print("=" * 70)
print(f"(comment length: {len(body)} chars)")

# ---------------------------------------------------------------------- #
# Planted-issue cross-check
# ---------------------------------------------------------------------- #
lowered = body.lower()
checks = {
    "SQL injection (bandit B608)": "b608" in lowered or "sql injection" in lowered,
    "Hardcoded AWS key (gitleaks aws-access-token)": "aws-access-token" in lowered,
    "Generic API key / hardcoded password": (
        "generic-api-key" in lowered or "b105" in lowered
    ),
    "Dangerous eval": "eval" in lowered,
    "Missing test coverage": "untested" in lowered or "test" in lowered,
    "Missing docstring": "docstring" in lowered,
    "Agent Status section": "agent status" in lowered,
    "Scanner: semgrep": "semgrep" in lowered,
    "Scanner: bandit": "bandit" in lowered,
    "Scanner: gitleaks": "gitleaks" in lowered,
}
print()
print("PLANTED-ISSUE / CONTENT CHECKS")
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

# ---------------------------------------------------------------------- #
# Severity ordering
# ---------------------------------------------------------------------- #
order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
seen = [m.lower() for m in re.findall(r"\b(CRITICAL|HIGH|MEDIUM|LOW|INFO)\b", body)]
ranks = [order[s] for s in seen if s in order]
print()
print(f"severity tokens in document order: {seen}")
print(f"non-decreasing (correctly ranked): {ranks == sorted(ranks)}")

# ---------------------------------------------------------------------- #
# Compare against the stored review + rendered report endpoint
# ---------------------------------------------------------------------- #
detail = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=30).json()
print()
print("STORED REVIEW (per agent):")
total = 0
for agent, findings in (detail.get("findings_by_agent") or {}).items():
    total += len(findings)
    print(f"  {agent:14} {len(findings)} finding(s)")
    for f in findings:
        print(f"      [{f['severity']:8}] {f['title']}  ({f['file_path']}:{f['line']})")
print(f"  TOTAL: {total}")
print(f"  summary: {detail.get('summary')}")

rep = requests.get(f"{BASE_URL}/reviews/{review_id}/report", timeout=30)
print()
print(f"GET /reviews/{review_id}/report -> HTTP {rep.status_code}")
if rep.status_code == 200:
    rendered = rep.json().get("report_markdown") if rep.headers.get(
        "content-type", ""
    ).startswith("application/json") else rep.text
    if rendered:
        print(f"  rendered report matches posted comment: {rendered.strip() == body.strip()}")

# ---------------------------------------------------------------------- #
# Local-path leakage check (paths should be repo-relative, not temp dirs)
# ---------------------------------------------------------------------- #
leaked = re.findall(r"[A-Za-z]:\\\\?[^\s`|]*codeguardian_[^\s`|]*", body)
print()
print(f"absolute local workspace paths leaked into the comment: {len(leaked)}")
for p in leaked[:5]:
    print(f"  {p}")
