"""Step 6: create the auto-fix branch and inspect the REAL commit contents.

The critical check: nothing hallucinated (non-existent imports, functions that do
not exist) may reach the pushed branch. Every applied fix is inspected against the
actual file content fetched back from GitHub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import BASE_URL, gh_headers, show, target

t = target()
review_id = json.loads(
    (Path(__file__).resolve().parent / "e2e_review.json").read_text(encoding="utf-8")
)["review_id"]
repo = t["repo_full_name"]

print("=" * 70)
print(f"STEP 6 — POST /reviews/{review_id}/autofix")
print("=" * 70)

# Report the fixable findings going in, for comparison with what comes out.
detail = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=30).json()
fixable = [
    (f["agent"], f["title"], f["fix_data"])
    for agent, items in (detail.get("findings_by_agent") or {}).items()
    for f in ({**i, "agent": agent} for i in items)
    if f.get("fix_data")
]
print(f"fixable findings stored for this review: {len(fixable)}")
for agent, title, fd in fixable:
    kind = "test" if "test_code" in (fd or {}) else "docstring"
    print(f"  {agent:14} {kind:9} {title}")
print()

resp = requests.post(f"{BASE_URL}/reviews/{review_id}/autofix", timeout=300)
body = show(resp, f"POST /reviews/{review_id}/autofix")

if resp.status_code != 201:
    print(f"\nautofix did not return 201 (got {resp.status_code})")
    sys.exit(1)

branch = body["branch"]
print(f"\nbranch reported: {branch}")

# ------------------------------------------------------------------ #
# Verify the branch really exists on GitHub
# ------------------------------------------------------------------ #
print()
print("-" * 70)
print("REAL GITHUB STATE")
print("-" * 70)
r = requests.get(
    f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}",
    headers=gh_headers(), timeout=30,
)
print(f"GET git/ref/heads/{branch} -> HTTP {r.status_code}")
if r.status_code != 200:
    print(f"FAIL: branch does not exist on GitHub: {r.text[:300]}")
    sys.exit(1)
branch_sha = r.json()["object"]["sha"]
print(f"  branch head SHA: {branch_sha}")

# ------------------------------------------------------------------ #
# Real commits on the branch
# ------------------------------------------------------------------ #
r = requests.get(
    f"https://api.github.com/repos/{repo}/commits",
    headers=gh_headers(), params={"sha": branch, "per_page": 5}, timeout=30,
)
commits = r.json()
print(f"\ncommits on {branch} (newest first):")
for c in commits[:3]:
    print(f"  {c['sha'][:10]} {c['commit']['author']['name']:20} "
          f"{c['commit']['message'].splitlines()[0]}")

head_commit_sha = commits[0]["sha"]
r = requests.get(
    f"https://api.github.com/repos/{repo}/commits/{head_commit_sha}",
    headers=gh_headers(), timeout=30,
)
commit = r.json()
print(f"\nHEAD commit {head_commit_sha[:10]} details:")
print(f"  message: {commit['commit']['message']}")
print(f"  files changed: {len(commit.get('files', []))}")
print(f"  stats: {commit.get('stats')}")

print()
print("=" * 70)
print("ACTUAL COMMIT DIFF (verbatim patch per file)")
print("=" * 70)
for f in commit.get("files", []):
    print(f"\n--- {f['filename']}  ({f['status']}, +{f['additions']}/-{f['deletions']})")
    patch = f.get("patch")
    print(patch if patch else "  (no patch available)")

# ------------------------------------------------------------------ #
# Hallucination check against the real file content on the branch
# ------------------------------------------------------------------ #
print()
print("=" * 70)
print("HALLUCINATION CHECK ON THE PUSHED BRANCH")
print("=" * 70)

skipped = body.get("skipped_fixes", [])
print(f"applied_fixes: {body.get('applied_fixes')}")
print(f"skipped_fixes: {len(skipped)}")
for s in skipped:
    print(f"  SKIPPED {s['target']}: {s['reason']}")

# Any test file added? Check its imports resolve to real modules on the branch.
def fetch(path: str) -> str | None:
    rr = requests.get(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers=gh_headers(), params={"ref": branch}, timeout=30,
    )
    if rr.status_code != 200:
        return None
    import base64
    return base64.b64decode(rr.json()["content"]).decode("utf-8", errors="replace")


added_paths = [f["filename"] for f in commit.get("files", [])]
print(f"\npaths touched by the auto-fix commit: {added_paths}")

problems: list[str] = []
for path in added_paths:
    content = fetch(path)
    if content is None:
        problems.append(f"{path}: could not fetch content from the branch")
        continue
    if not path.endswith(".py"):
        continue
    # Every `from X import ...` must resolve to something that exists on the branch.
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("from ") and " import " in line:
            module = line.split()[1].split(".")[0]
            if module in ("pytest", "unittest", "mock", "os", "sys", "json",
                          "datetime", "sqlite3", "re", "typing", "pathlib"):
                continue
            probe_paths = [f"{module}.py", f"{module}/__init__.py"]
            if not any(fetch(p) is not None for p in probe_paths):
                problems.append(
                    f"{path}: imports '{module}' which does not exist on the branch "
                    f"-> HALLUCINATED IMPORT REACHED THE BRANCH"
                )

print()
if problems:
    print("PROBLEMS FOUND:")
    for p in problems:
        print(f"  {p}")
else:
    print("No hallucinated imports or missing targets found in the pushed commit.")

# Confirm the fixed docstrings correspond to functions that really exist.
fixture = fetch(t["file_path"])
if fixture:
    import ast
    tree = ast.parse(fixture)
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    print(f"\nfunctions present in {t['file_path']} on the branch: {sorted(funcs)}")
    docstrings = {
        n.name: ast.get_docstring(n)
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    print("docstrings now present:")
    for name, doc in docstrings.items():
        first = (doc or "").strip().splitlines()[0] if doc else None
        print(f"  {name:22} {first!r}")

print()
print("-" * 70)
print("MERGE SAFETY: confirming the branch is NOT merged")
r = requests.get(
    f"https://api.github.com/repos/{repo}/pulls",
    headers=gh_headers(), params={"state": "all", "per_page": 50}, timeout=30,
)
autofix_prs = [p for p in r.json() if p["head"]["ref"] == branch]
print(f"  pull requests opened from {branch}: {len(autofix_prs)}")
r = requests.get(
    f"https://api.github.com/repos/{repo}/compare/{t['base_branch']}...{branch}",
    headers=gh_headers(), timeout=30,
)
if r.status_code == 200:
    cmp = r.json()
    print(f"  compare {t['base_branch']}...{branch}: status={cmp['status']} "
          f"ahead_by={cmp['ahead_by']} behind_by={cmp['behind_by']}")
