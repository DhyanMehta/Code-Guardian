"""Step 8: two near-simultaneous webhooks for the same PR.

Fires both deliveries from separate threads at the same moment, then inspects the
resulting review rows to confirm only one review actually ran and the duplicate was
rejected rather than running a second concurrent review.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from sqlalchemy import create_engine, text

from _common import BASE_URL, post_webhook, pr_payload, target
from backend.config import get_settings

t = target()
engine = create_engine(get_settings().database_url)

print("=" * 70)
print("STEP 8 — concurrency guard: two near-simultaneous webhooks, same PR")
print("=" * 70)

with engine.connect() as conn:
    idx = conn.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'reviews' AND indexdef ILIKE '%unique%'"
        )
    ).mappings().all()
print("unique indexes on reviews:")
for row in idx:
    print(f"  {row['indexname']}")
    print(f"    {row['indexdef']}")
print()

results: dict[str, object] = {}
barrier = threading.Barrier(2)


def fire(tag: str) -> None:
    payload = pr_payload(action="synchronize")
    barrier.wait()  # release both at the same instant
    started = time.monotonic()
    try:
        resp = post_webhook(payload)
        results[tag] = {
            "status_code": resp.status_code,
            "body": resp.json() if resp.content else None,
            "elapsed": round(time.monotonic() - started, 3),
        }
    except Exception as exc:  # noqa: BLE001
        results[tag] = {"error": f"{exc.__class__.__name__}: {exc}"}


threads = [threading.Thread(target=fire, args=(f"webhook_{i+1}",)) for i in range(2)]
for th in threads:
    th.start()
for th in threads:
    th.join()

for tag in sorted(results):
    print(f"{tag}: {results[tag]}")

review_ids = [
    r["body"]["review_id"]  # type: ignore[index]
    for r in results.values()
    if isinstance(r, dict) and isinstance(r.get("body"), dict) and "review_id" in r["body"]
]
print(f"\nreview ids created: {review_ids}")

print("\nwaiting for both background tasks to settle...")
deadline = time.monotonic() + 600
while time.monotonic() < deadline:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, status, summary FROM reviews WHERE id = ANY(:ids) ORDER BY id"
            ),
            {"ids": review_ids},
        ).mappings().all()
    statuses = [r["status"] for r in rows]
    if all(s not in ("pending", "running") for s in statuses):
        break
    time.sleep(5)

print()
print("-" * 70)
print("FINAL REVIEW ROWS")
print("-" * 70)
for r in rows:
    print(f"  id={r['id']} status={r['status']}")
    print(f"      summary: {r['summary']}")

# How many of these two reviews actually completed a full run?
completed = [r for r in rows if r["status"] == "completed"]
skipped = [r for r in rows if r["status"] == "skipped"]
print()
print(f"completed: {len(completed)}   skipped: {len(skipped)}")

# Count PR comments — a second concurrent run would post a second comment.
from _common import gh_headers  # noqa: E402

rc = requests.get(
    f"https://api.github.com/repos/{t['repo_full_name']}"
    f"/issues/{t['pr_number']}/comments",
    headers=gh_headers(), timeout=30,
)
print(f"total CodeGuardian comments now on PR #{t['pr_number']}: {len(rc.json())}")

print()
if len(completed) == 1 and len(skipped) == 1:
    print("PASS: exactly one review ran; the duplicate was rejected by the guard.")
else:
    print("RESULT DIFFERS FROM EXPECTATION — see rows above.")
