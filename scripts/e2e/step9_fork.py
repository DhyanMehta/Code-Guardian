"""Step 9: fork-PR handling.

IMPORTANT LABELLING: this is a SIMULATED fork payload, not a real cross-account fork
PR. No second GitHub account is available, so the delivery is crafted with a head
repo whose full_name differs from the base repo — which is exactly the signal the
webhook receiver uses to set is_fork. This exercises the real is_fork code path and
the real 422 refusal on the autofix endpoint, but it is not a genuine fork.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from sqlalchemy import create_engine, text

from _common import BASE_URL, post_webhook, pr_payload, show, target
from backend.config import get_settings

t = target()
engine = create_engine(get_settings().database_url)

FORK_OWNER = "outside-contributor"
FORK_REPO = f"{FORK_OWNER}/Code-Guardian"

print("=" * 70)
print("STEP 9 — fork PR: autofix must refuse with 422")
print("=" * 70)
print("NOTE: simulated fork payload (no second account available).")
print(f"      base repo = {t['repo_full_name']}")
print(f"      head repo = {FORK_REPO}  <- differs, so is_fork must be True")
print()

payload = pr_payload(
    action="opened",
    head_repo_full_name=FORK_REPO,
    head_ref="contributor-feature",
)
print("payload head.repo.full_name:", payload["pull_request"]["head"]["repo"]["full_name"])
print("payload repository.full_name:", payload["repository"]["full_name"])
print("payload head.repo.fork     :", payload["pull_request"]["head"]["repo"]["fork"])
print()

resp = post_webhook(payload)
body = show(resp, "POST /webhooks/github (fork-shaped)")
if resp.status_code != 202:
    print("FAIL: webhook was not accepted")
    sys.exit(1)

review_id = body["review_id"]

with engine.connect() as conn:
    is_fork = conn.execute(
        text("SELECT is_fork FROM reviews WHERE id = :i"), {"i": review_id}
    ).scalar_one()
print(f"\nDB: review {review_id} is_fork = {is_fork}")
if not is_fork:
    print("FAIL: is_fork was not set from the fork-shaped payload")
    sys.exit(1)

print("\nwaiting for the review to reach a terminal state...")
deadline = time.monotonic() + 600
status = None
while time.monotonic() < deadline:
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM reviews WHERE id = :i"), {"i": review_id}
        ).scalar_one()
    if status not in ("pending", "running"):
        break
    time.sleep(5)
print(f"review {review_id} status = {status}")

print()
print("-" * 70)
print(f"POST /reviews/{review_id}/autofix  (expecting 422 fork-unavailable)")
print("-" * 70)
resp = requests.post(f"{BASE_URL}/reviews/{review_id}/autofix", timeout=300)
fbody = show(resp, f"POST /reviews/{review_id}/autofix")

detail = (fbody or {}).get("detail", "") if isinstance(fbody, dict) else ""
print()
print(f"  HTTP 422                     : {resp.status_code == 422}")
print(f"  mentions fork unavailability : {'unavailable for fork' in detail.lower()}")

with engine.connect() as conn:
    row = conn.execute(
        text("SELECT autofix_status, autofix_branch FROM reviews WHERE id = :i"),
        {"i": review_id},
    ).mappings().one()
print(f"  DB autofix state unchanged   : {dict(row)}")

print()
if resp.status_code == 422 and row["autofix_branch"] is None:
    print("PASS: fork PR refused with 422 and no auto-fix branch was created.")
else:
    print("RESULT DIFFERS FROM EXPECTATION — see above.")
