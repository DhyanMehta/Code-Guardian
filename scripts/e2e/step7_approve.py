"""Step 7: record explicit human approval and prove no merge happened.

Reads the DB directly (not just the API) to confirm the persisted approval state,
then re-checks GitHub to confirm the auto-fix branch is still unmerged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from sqlalchemy import create_engine, text

from _common import BASE_URL, gh_headers, show, target
from backend.config import get_settings

t = target()
review_id = json.loads(
    (Path(__file__).resolve().parent / "e2e_review.json").read_text(encoding="utf-8")
)["review_id"]
repo = t["repo_full_name"]

print("=" * 70)
print(f"STEP 7 — POST /reviews/{review_id}/autofix/approve")
print("=" * 70)

engine = create_engine(get_settings().database_url)


def db_row() -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT autofix_status, autofix_branch, autofix_approved_by, "
                "autofix_approved_at FROM reviews WHERE id = :i"
            ),
            {"i": review_id},
        ).mappings().one()
        return dict(row)


print(f"DB before approval: {db_row()}\n")

resp = requests.post(
    f"{BASE_URL}/reviews/{review_id}/autofix/approve",
    json={"approved_by": "DhyanMehta"},
    timeout=60,
)
body = show(resp, f"POST /reviews/{review_id}/autofix/approve")

after = db_row()
print(f"\nDB after approval: {after}")

ok_status = after["autofix_status"] == "approved"
ok_by = after["autofix_approved_by"] == "DhyanMehta"
ok_at = after["autofix_approved_at"] is not None
print(f"  autofix_status == 'approved'      : {ok_status}")
print(f"  autofix_approved_by recorded      : {ok_by}")
print(f"  autofix_approved_at recorded      : {ok_at}")

branch = after["autofix_branch"]

print()
print("-" * 70)
print("NO-MERGE VERIFICATION (real GitHub state after approval)")
print("-" * 70)

r = requests.get(
    f"https://api.github.com/repos/{repo}/compare/{t['base_branch']}...{branch}",
    headers=gh_headers(), timeout=30,
)
cmp = r.json()
print(f"compare {t['base_branch']}...{branch}: status={cmp.get('status')} "
      f"ahead_by={cmp.get('ahead_by')} behind_by={cmp.get('behind_by')}")

r = requests.get(
    f"https://api.github.com/repos/{repo}/pulls",
    headers=gh_headers(), params={"state": "all", "per_page": 100}, timeout=30,
)
prs_from_branch = [p for p in r.json() if p["head"]["ref"] == branch]
print(f"PRs opened from {branch}: {len(prs_from_branch)}")
merged = [p for p in prs_from_branch if p.get("merged_at")]
print(f"merged PRs from {branch}: {len(merged)}")

# Is the branch's commit reachable from the default branch? If merged, it would be.
r = requests.get(
    f"https://api.github.com/repos/{repo}/commits",
    headers=gh_headers(), params={"sha": t["base_branch"], "per_page": 100}, timeout=30,
)
base_shas = {c["sha"] for c in r.json()}
r = requests.get(
    f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}",
    headers=gh_headers(), timeout=30,
)
branch_sha = r.json()["object"]["sha"]
print(f"branch head {branch_sha[:10]} present in {t['base_branch']} history: "
      f"{branch_sha in base_shas}")

print()
if ok_status and ok_by and ok_at and not merged and branch_sha not in base_shas:
    print("PASS: approval recorded in the DB, and the branch remains unmerged.")
else:
    print("CHECK THE ABOVE: one or more assertions did not hold.")
