"""Checkpoint 2: verify the dashboard is really wired to the real backend.

Checks the things a browser would do: the dev server serves the app, CORS preflight
succeeds for the dev origin and fails for an untrusted one, and the payloads the pages
consume contain the fields the UI reads — against real rows, no mocks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

BACKEND = "http://127.0.0.1:8000"
DEV_SERVER = "http://127.0.0.1:5173"
DEV_ORIGIN = "http://127.0.0.1:5173"
EVIL_ORIGIN = "http://evil.example.com"

print("=" * 72)
print("1. DEV SERVER")
print("=" * 72)
page = requests.get(DEV_SERVER, timeout=15)
print(f"GET {DEV_SERVER} -> HTTP {page.status_code}, {len(page.text)} bytes")
root_div = '<div id="root">'
print(f"  serves #root div      : {root_div in page.text}")
print(f"  loads /src/main.tsx   : {'/src/main.tsx' in page.text}")
entry = requests.get(f"{DEV_SERVER}/src/main.tsx", timeout=15)
print(f"GET /src/main.tsx -> HTTP {entry.status_code} "
      f"(transformed: {'createRoot' in entry.text})")

print()
print("=" * 72)
print("2. CORS")
print("=" * 72)
pre = requests.options(
    f"{BACKEND}/reviews",
    headers={
        "Origin": DEV_ORIGIN,
        "Access-Control-Request-Method": "GET",
    },
    timeout=15,
)
print(f"OPTIONS /reviews from {DEV_ORIGIN} -> HTTP {pre.status_code}")
print(f"  allow-origin : {pre.headers.get('access-control-allow-origin')}")
print(f"  allow-methods: {pre.headers.get('access-control-allow-methods')}")

get_with_origin = requests.get(
    f"{BACKEND}/reviews", headers={"Origin": DEV_ORIGIN}, timeout=20
)
print(f"GET /reviews with Origin -> HTTP {get_with_origin.status_code}, "
      f"allow-origin={get_with_origin.headers.get('access-control-allow-origin')}")

evil = requests.options(
    f"{BACKEND}/reviews",
    headers={"Origin": EVIL_ORIGIN, "Access-Control-Request-Method": "POST"},
    timeout=15,
)
print(f"OPTIONS /reviews from {EVIL_ORIGIN} -> HTTP {evil.status_code}, "
      f"allow-origin={evil.headers.get('access-control-allow-origin')} "
      f"(must be absent/mismatched)")

print()
print("=" * 72)
print("3. REVIEW LIST PAYLOAD (fields the list page reads)")
print("=" * 72)
body = get_with_origin.json()
required_item = [
    "id", "repo_full_name", "pr_number", "commit_sha", "status", "summary",
    "is_fork", "created_at", "completed_at", "finding_count", "severity_counts",
    "agent_counts", "fixable_count", "autofix_status", "autofix_branch",
    "degraded_agents",
]
missing = [k for k in required_item if k not in (body["items"][0] or {})]
print(f"envelope keys: {sorted(body)}")
print(f"item field coverage: {'ALL PRESENT' if not missing else f'MISSING {missing}'}")
print(f"total={body['total']} items={len(body['items'])}")
for item in body["items"]:
    print(f"  id={item['id']:>2} {item['status']:10} findings={item['finding_count']:>3} "
          f"fixable={item['fixable_count']:>2} autofix={str(item['autofix_status']):16} "
          f"degraded={item['degraded_agents']}")

print()
print("=" * 72)
print("4. REVIEW DETAIL PAYLOAD (fields the detail page reads)")
print("=" * 72)
required_detail = [
    "id", "status", "findings", "findings_by_agent", "severity_counts",
    "agent_counts", "fixable_count", "agent_runs", "autofix", "completed_at",
]
for review_id in (10, 8, 1, 3, 4):
    detail = requests.get(
        f"{BACKEND}/reviews/{review_id}", headers={"Origin": DEV_ORIGIN}, timeout=20
    ).json()
    gaps = [k for k in required_detail if k not in detail]
    ranks = [f["rank"] for f in detail["findings"]]
    contiguous = ranks == list(range(1, len(ranks) + 1))
    runs = {r["agent"]: (r["outcome"], r["recorded"]) for r in detail["agent_runs"]}
    print(f"\n  review {review_id}: fields={'ok' if not gaps else gaps} "
          f"findings={len(detail['findings'])} ranks_contiguous={contiguous}")
    print(f"    agent_runs={runs}")
    print(f"    autofix={json.dumps(detail['autofix'])[:150]}")
    fixable = [f for f in detail["findings"] if f["fixable"]]
    if fixable:
        fd = fixable[0]["fix_data"]
        kind = "test" if fd.get("test_code") else "docstring"
        print(f"    first fixable: {fd.get('target_function')} ({kind}) "
              f"renderable={bool(fd.get('test_code') or fd.get('docstring'))}")
    abs_paths = [
        f["file_path"] for f in detail["findings"]
        if f["file_path"] and (f["file_path"][1:3] == ":\\" or f["file_path"].startswith("/tmp"))
    ]
    print(f"    absolute paths in findings: {len(abs_paths)}")

print()
print("=" * 72)
print("5. REPORT ENDPOINT (posted-comment tab)")
print("=" * 72)
for review_id, expect in ((10, 200), (3, 409)):
    resp = requests.get(
        f"{BACKEND}/reviews/{review_id}/report",
        headers={"Origin": DEV_ORIGIN}, timeout=20
    )
    label = "markdown" if resp.status_code == 200 else resp.json().get("detail", "")
    size = len(resp.json().get("markdown", "")) if resp.status_code == 200 else 0
    print(f"  review {review_id}: HTTP {resp.status_code} (expected {expect}) "
          f"{'chars=' + str(size) if size else label[:70]}")
