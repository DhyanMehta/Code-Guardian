"""Prove GET /reviews/{id}/report reproduces the comment actually posted to GitHub.

Before Session 6 the endpoint rebuilt agent statuses from "which agents have
findings", so a zero-finding agent vanished from the table and every remaining agent
defaulted to OK. This compares the endpoint's markdown against the real comment body
fetched from the GitHub API, byte for byte, and prints the persisted agent-run rows
behind it.

Usage:  python scripts\\e2e\\verify_report_fidelity.py <review_id>
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from sqlalchemy import create_engine, text

from _common import BASE_URL, gh_headers, target
from backend.config import get_settings

review_id = int(sys.argv[1])
t = target()

print("=" * 72)
print(f"REPORT FIDELITY — review {review_id}")
print("=" * 72)

engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    review = conn.execute(
        text("select id, status, summary, completed_at from reviews where id = :i"),
        {"i": review_id},
    ).mappings().one()
    print(f"status       : {review['status']}")
    print(f"completed_at : {review['completed_at']}")
    print(f"summary      : {review['summary']}")

    print("\npersisted review_agent_runs rows:")
    runs = conn.execute(
        text(
            "select agent, outcome, finding_count, failure_reason, notes "
            "from review_agent_runs where review_id = :i order by agent"
        ),
        {"i": review_id},
    ).mappings().all()
    if not runs:
        print("  (none) — nothing persisted, fidelity cannot hold")
    for r in runs:
        print(f"  {r['agent']:14} outcome={r['outcome']:9} "
              f"count={r['finding_count']}")
        if r["failure_reason"]:
            print(f"                 reason={r['failure_reason']}")
        if r["notes"]:
            for note in json.loads(r["notes"]):
                print(f"                 note={note}")

# The comment this review posted is the most recent one on the PR.
comments = requests.get(
    f"https://api.github.com/repos/{t['repo_full_name']}"
    f"/issues/{t['pr_number']}/comments",
    headers=gh_headers(), timeout=30,
).json()
posted = comments[-1]
print(f"\nposted comment id={posted['id']} at {posted['created_at']}")
print(f"  {posted['html_url']}")

resp = requests.get(f"{BASE_URL}/reviews/{review_id}/report", timeout=30)
print(f"\nGET /reviews/{review_id}/report -> HTTP {resp.status_code}")
rendered = resp.json()["markdown"]

posted_body = posted["body"]
print(f"posted   : {len(posted_body)} chars")
print(f"rendered : {len(rendered)} chars")
identical = posted_body.strip() == rendered.strip()
print(f"\nBYTE-IDENTICAL: {identical}")

if not identical:
    print("\ndiff (posted -> rendered):")
    for line in difflib.unified_diff(
        posted_body.strip().splitlines(),
        rendered.strip().splitlines(),
        fromfile="posted-to-github",
        tofile="endpoint-rendered",
        lineterm="",
        n=1,
    ):
        print(f"  {line}")

print("\n" + "-" * 72)
print("AGENT STATUS TABLE — posted vs rendered")
print("-" * 72)


def status_rows(md: str) -> list[str]:
    rows, in_table = [], False
    for line in md.splitlines():
        if line.startswith("### Agent Status"):
            in_table = True
            continue
        if in_table:
            if line.startswith("---"):
                break
            if line.startswith("| ") and not line.startswith("| Agent") \
                    and not line.startswith("|--"):
                rows.append(line)
    return rows


posted_rows = status_rows(posted_body)
rendered_rows = status_rows(rendered)
for label, rows in (("POSTED", posted_rows), ("RENDERED", rendered_rows)):
    print(f"\n{label}:")
    for row in rows:
        print("  " + row.encode("ascii", "backslashreplace").decode())

print(f"\nagent status rows match: {posted_rows == rendered_rows}")
print(f"agents listed: posted={len(posted_rows)} rendered={len(rendered_rows)}")
