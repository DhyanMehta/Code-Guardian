"""Steps 3 + 4: trigger a real review via a signed webhook, then poll to completion.

Step 3 asserts the webhook returns 202 with a review_id immediately (the review runs
in the background). Step 4 polls GET /reviews/{id} until status leaves "running" and
reports the real wall-clock duration.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import BASE_URL, post_webhook, pr_payload, show, target

POLL_INTERVAL = 5
POLL_TIMEOUT = 600

t = target()
print("=" * 70)
print("STEP 3 — trigger a real review via signed GitHub webhook")
print("=" * 70)
print(f"target PR: {t['repo_full_name']}#{t['pr_number']} @ {t['head_sha'][:8]}")
print(f"           {t['html_url']}\n")

t0 = time.monotonic()
resp = post_webhook(pr_payload(action="opened"))
dispatch_seconds = time.monotonic() - t0

body = show(resp, "POST /webhooks/github")
print(f"  returned in {dispatch_seconds:.3f}s")

if resp.status_code != 202:
    print(f"\nFAIL: expected HTTP 202, got {resp.status_code}")
    sys.exit(1)
if not body or "review_id" not in body:
    print("\nFAIL: response did not include a review_id")
    sys.exit(1)

review_id = body["review_id"]
print(f"\nPASS: 202 Accepted, review_id={review_id}, dispatched in {dispatch_seconds:.3f}s")

print()
print("=" * 70)
print(f"STEP 4 — poll GET /reviews/{review_id} until status != running")
print("=" * 70)

start = time.monotonic()
last_status = None
while True:
    elapsed = time.monotonic() - start
    r = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=30)
    if r.status_code != 200:
        print(f"  GET /reviews/{review_id} -> HTTP {r.status_code}: {r.text[:300]}")
        sys.exit(1)

    detail = r.json()
    status = detail.get("status")
    if status != last_status:
        print(f"  [{elapsed:6.1f}s] status={status}")
        last_status = status

    if status not in ("pending", "running"):
        print(f"\nReview reached terminal status '{status}' after {elapsed:.1f}s")
        break

    if elapsed > POLL_TIMEOUT:
        print(f"\nFAIL: still '{status}' after {POLL_TIMEOUT}s")
        sys.exit(1)

    time.sleep(POLL_INTERVAL)

total_seconds = time.monotonic() - start
print()
print("Full review detail:")
print(json.dumps(detail, indent=2)[:8000])

findings = detail.get("findings", [])
print()
print("-" * 70)
print(f"RESULT: status={detail.get('status')}  duration={total_seconds:.1f}s  "
      f"findings={len(findings)}")
print(f"summary: {detail.get('summary')}")
by_agent: dict[str, int] = {}
by_sev: dict[str, int] = {}
for f in findings:
    by_agent[f.get("agent", "?")] = by_agent.get(f.get("agent", "?"), 0) + 1
    by_sev[f.get("severity", "?")] = by_sev.get(f.get("severity", "?"), 0) + 1
print(f"by agent: {by_agent}")
print(f"by severity: {by_sev}")

(Path(__file__).resolve().parent / "e2e_review.json").write_text(
    json.dumps({"review_id": review_id, "duration_seconds": round(total_seconds, 1)}, indent=2),
    encoding="utf-8",
)
print(f"\n(review_id {review_id} saved to scripts/e2e/e2e_review.json)")
