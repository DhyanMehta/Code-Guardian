"""Dump the real /metrics/trends payload so the charts are built against actual data.

Read-only. Prints the full shape plus a per-point table, and reconciles the point
totals against the totals block and against GET /reviews.
"""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    trends = get("/metrics/trends?limit=50")
    reviews = get("/reviews?limit=200")

    print("=== top-level keys ===")
    print(sorted(trends.keys()))
    print()
    print("=== range ===")
    print(json.dumps(trends["range"], indent=2))
    print()
    print("=== repos ===")
    print(trends["repos"])
    print()
    print("=== totals ===")
    print(json.dumps(trends["totals"], indent=2))
    print()

    points = trends["points"]
    print(f"=== points ({len(points)}) ===")
    print("point keys:", sorted(points[0].keys()) if points else "NONE")
    print()
    header = (
        f"{'idx':>3} {'rev':>4} {'pr':>4} {'status':<10} {'created_at':<26} "
        f"{'find':>5} {'widx':>5} {'covOK':>6} degraded"
    )
    print(header)
    print("-" * len(header))
    for index, point in enumerate(points):
        print(
            f"{index:>3} {point['review_id']:>4} {point['pr_number']:>4} "
            f"{point['status']:<10} {str(point['created_at']):<26} "
            f"{point['total_findings']:>5} {point['weighted_index']:>5} "
            f"{str(point['coverage_complete']):>6} {point['degraded_agents']}"
        )
    print()

    print("=== chronological check ===")
    stamps = [p["created_at"] for p in points]
    print("oldest first:", stamps == sorted(stamps), "| first:", stamps[0] if stamps else None,
          "| last:", stamps[-1] if stamps else None)
    print()

    print("=== reconciliation ===")
    sum_points = sum(p["total_findings"] for p in points)
    sum_reviews = sum(r["finding_count"] for r in reviews["items"])
    print(f"sum(points.total_findings)   = {sum_points}")
    print(f"totals.findings              = {trends['totals']['findings']}")
    print(f"sum(/reviews.finding_count)  = {sum_reviews}")
    print(f"reviews total                = {reviews['total']}")
    print(f"points count                 = {len(points)}")
    print(
        "MATCH"
        if sum_points == trends["totals"]["findings"] == sum_reviews
        else "MISMATCH"
    )
    print()

    print("=== severity totals cross-check ===")
    from collections import Counter

    acc: Counter[str] = Counter()
    for point in points:
        for key, value in point["severity_counts"].items():
            acc[key] += value
    print("summed from points:", dict(sorted(acc.items())))
    print("totals block      :", dict(sorted(trends["totals"]["severity_counts"].items())))
    print("MATCH" if dict(acc) == {k: v for k, v in trends["totals"]["severity_counts"].items() if True} or all(
        acc[k] == v for k, v in trends["totals"]["severity_counts"].items()
    ) else "MISMATCH")
    print()

    print("=== agent-run recording vs coverage_complete ===")
    print("Each review's agent_runs recorded flags, to test whether coverage_complete")
    print("distinguishes 'all four ran' from 'nothing was recorded'.")
    for point in points:
        detail = get(f"/reviews/{point['review_id']}")
        runs = detail["agent_runs"]
        recorded = [r["agent"] for r in runs if r["recorded"]]
        outcomes = {r["agent"]: r["outcome"] for r in runs}
        print(
            f"  review {point['review_id']:>3}: coverage_complete="
            f"{str(point['coverage_complete']):<5} agent_runs={len(runs)} "
            f"recorded={len(recorded)} outcomes={outcomes}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
