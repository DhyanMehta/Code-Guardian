"""Checkpoint 1: exercise the new/changed dashboard endpoints against the real DB."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import BASE_URL

print("=" * 72)
print("GET /reviews  (envelope + counts)")
print("=" * 72)
body = requests.get(f"{BASE_URL}/reviews", timeout=30).json()
print(f"keys: {sorted(body)}")
print(f"total={body['total']} limit={body['limit']} offset={body['offset']} "
      f"returned={len(body['items'])}")
print()
print(f"{'id':>3} {'status':10} {'find':>4} {'crit':>4} {'high':>4} {'med':>4} "
      f"{'low':>4} {'fix':>4} {'autofix':16} degraded")
for item in body["items"]:
    sc = item["severity_counts"]
    print(f"{item['id']:>3} {item['status']:10} {item['finding_count']:>4} "
          f"{sc['critical']:>4} {sc['high']:>4} {sc['medium']:>4} {sc['low']:>4} "
          f"{item['fixable_count']:>4} {str(item['autofix_status']):16} "
          f"{item['degraded_agents']}")
    assert sum(sc.values()) == item["finding_count"], "severity counts must sum"
    assert sum(item["agent_counts"].values()) == item["finding_count"]
print("\nall severity/agent counts sum to finding_count: OK")

pg = requests.get(f"{BASE_URL}/reviews", params={"limit": 2, "offset": 1}).json()
print(f"pagination: limit=2 offset=1 -> {[i['id'] for i in pg['items']]} "
      f"total still {pg['total']}")

print()
print("=" * 72)
print("GET /reviews/{id}  (ranked findings, agent runs, autofix detail)")
print("=" * 72)
for review_id in (5, 8, 9, 1, 3, 4):
    resp = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=30)
    if resp.status_code != 200:
        print(f"\nreview {review_id}: HTTP {resp.status_code}")
        continue
    d = resp.json()
    print(f"\n--- review {review_id}: status={d['status']} fork={d['is_fork']} "
          f"findings={d['finding_count']} fixable={d['fixable_count']} ---")
    print(f"    completed_at={d['completed_at']}")
    ranks = [f["rank"] for f in d["findings"]]
    sevs = [f["severity"] for f in d["findings"]]
    print(f"    ranks contiguous 1..n: {ranks == list(range(1, len(ranks) + 1))}")
    order = ["critical", "high", "medium", "low", "info", "unknown"]
    idx = [order.index(s) for s in sevs]
    print(f"    severity non-decreasing: {idx == sorted(idx)}  sequence={sevs}")
    print("    agent_runs:")
    for run in d["agent_runs"]:
        extra = f" info={run.get('scanner_info')}" if run.get("scanner_info") else ""
        reason = f" reason={run['failure_reason'][:60]}" if run["failure_reason"] else ""
        print(f"      {run['agent']:14} outcome={str(run['outcome']):9} "
              f"recorded={run['recorded']!s:5} count={run['finding_count']}{extra}{reason}")
    af = d["autofix"]
    print(f"    autofix: status={af['status']} branch={af['branch']} "
          f"applied={af['applied_count']} skipped={len(af['skipped_fixes'])} "
          f"by={af['approved_by']}")

print()
print("=" * 72)
print("GET /metrics/trends")
print("=" * 72)
t = requests.get(f"{BASE_URL}/metrics/trends", timeout=30).json()
print(f"range: {t['range']}")
print(f"repos: {t['repos']}")
print(f"\n{'rid':>4} {'created':26} {'status':10} {'find':>4} {'idx':>4} coverage")
for p in t["points"]:
    print(f"{p['review_id']:>4} {p['created_at'][:25]:26} {p['status']:10} "
          f"{p['total_findings']:>4} {p['weighted_index']:>4} "
          f"{'complete' if p['coverage_complete'] else 'GAP ' + str(p['degraded_agents'])}")
print(f"\ntotals: {json.dumps(t['totals'], indent=2)}")

# Cross-check the trends totals against the reviews list.
list_total_findings = sum(i["finding_count"] for i in body["items"])
print(f"\nreconciliation: trends findings={t['totals']['findings']} "
      f"vs list sum={list_total_findings} -> "
      f"{t['totals']['findings'] == list_total_findings}")
