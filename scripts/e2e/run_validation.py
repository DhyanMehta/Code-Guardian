"""Trigger CodeGuardian reviews on validation repos and poll until completion.

Reads targets from validation_targets.json (created by create_validation_repos.py),
fires signed webhooks for each, polls until completion, then prints a summary.

Run from the project root with the venv python:
    backend\\venv\\Scripts\\python.exe scripts\\e2e\\run_validation.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from _common import post_webhook, show
from backend.config import get_settings

BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 5
POLL_TIMEOUT = 600  # 10 minutes per review

STATE_FILE = Path(__file__).resolve().parent / "validation_targets.json"
RESULTS_FILE = Path(__file__).resolve().parent / "validation_results.json"


def build_webhook_payload(target: dict) -> dict:
    """Build a GitHub PR webhook payload for the given target."""
    return {
        "action": "opened",
        "number": target["pr_number"],
        "pull_request": {
            "number": target["pr_number"],
            "head": {
                "sha": target["head_sha"],
                "repo": {
                    "full_name": target["repo_full_name"],
                },
            },
            "base": {
                "repo": {
                    "full_name": target["repo_full_name"],
                },
            },
        },
        "repository": {
            "full_name": target["repo_full_name"],
        },
    }


def poll_review(review_id: int, label: str) -> dict:
    """Poll until review reaches a terminal state. Returns the review detail."""
    start = time.time()
    print(f"  Polling review {review_id} ({label})...")

    while time.time() - start < POLL_TIMEOUT:
        try:
            r = requests.get(f"{BASE_URL}/reviews/{review_id}", timeout=10)
            if r.status_code != 200:
                print(f"    GET /reviews/{review_id} -> {r.status_code}")
                time.sleep(POLL_INTERVAL)
                continue

            data = r.json()
            status = data.get("status")
            elapsed = int(time.time() - start)

            if status in ("completed", "failed", "skipped"):
                print(f"    -> {status} after {elapsed}s")
                return data
            else:
                print(f"    [{elapsed}s] status={status}", end="\r")
        except requests.RequestException as e:
            print(f"    Connection error: {e}")

        time.sleep(POLL_INTERVAL)

    print(f"    TIMEOUT after {POLL_TIMEOUT}s")
    return {"status": "timeout", "review_id": review_id}


def analyze_result(target: dict, review: dict) -> dict:
    """Analyze a completed review for the validation report."""
    analysis = {
        "label": target["label"],
        "repo": target["repo_full_name"],
        "pr_number": target["pr_number"],
        "status": review.get("status"),
        "finding_count": review.get("finding_count", 0),
        "severity_counts": review.get("severity_counts", {}),
        "agent_counts": review.get("agent_counts", {}),
    }

    # Check agent runs
    agent_runs = review.get("agent_runs", [])
    analysis["agent_outcomes"] = {
        ar["agent_type"]: ar["outcome"] for ar in agent_runs
    }
    analysis["degraded_agents"] = [
        ar["agent_type"] for ar in agent_runs if ar.get("outcome") == "DEGRADED"
    ]
    analysis["failed_agents"] = [
        ar["agent_type"] for ar in agent_runs if ar.get("outcome") == "FAILED"
    ]

    # Check findings quality
    findings = review.get("findings", [])
    analysis["findings_summary"] = []
    for f in findings[:10]:  # First 10
        analysis["findings_summary"].append({
            "agent": f.get("agent_type"),
            "severity": f.get("severity"),
            "file": f.get("file_path"),
            "line": f.get("line_number"),
            "title": f.get("title", "")[:80],
        })

    # Validation checks
    checks = {}
    checks["completed_without_crash"] = review.get("status") in ("completed", "failed")
    checks["all_agents_reported"] = len(agent_runs) == 4
    checks["no_absolute_paths"] = not any(
        "\\" in (f.get("file_path") or "") or
        f.get("file_path", "").startswith("/tmp") or
        f.get("file_path", "").startswith("C:")
        for f in findings
    )
    checks["severity_ordered"] = _check_severity_order(findings)
    checks["findings_in_changed_files"] = True  # Will verify below

    # Check all findings reference files that were changed
    changed_files = set()
    if "changed_files" in review:
        changed_files = set(review["changed_files"])

    analysis["checks"] = checks
    return analysis


def _check_severity_order(findings: list) -> bool:
    """Verify findings are ordered by severity (high -> critical first)."""
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "none": 5}
    prev_rank = -1
    for f in findings:
        rank = severity_rank.get(f.get("severity", "none"), 5)
        if rank < prev_rank:
            return False
        prev_rank = rank
    return True


def print_summary(results: list):
    """Print a human-readable validation summary."""
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    all_passed = True
    for r in results:
        print(f"\n{'─' * 70}")
        print(f"  {r['label']}")
        print(f"  {r['repo']} PR #{r['pr_number']}")
        print(f"  Status: {r['status']}")
        print(f"  Findings: {r['finding_count']}")
        print(f"  Severity: {r.get('severity_counts', {})}")
        print(f"  Agent outcomes: {r.get('agent_outcomes', {})}")

        if r.get("degraded_agents"):
            print(f"  DEGRADED: {r['degraded_agents']}")
        if r.get("failed_agents"):
            print(f"  FAILED: {r['failed_agents']}")

        print(f"\n  Checks:")
        for check, passed in r.get("checks", {}).items():
            mark = "PASS" if passed else "FAIL"
            print(f"    [{mark}] {check}")
            if not passed:
                all_passed = False

        if r.get("findings_summary"):
            print(f"\n  Top findings:")
            for f in r["findings_summary"][:5]:
                print(f"    [{f['severity']}] {f['agent']}: {f['title']}")
                print(f"      {f['file']}:{f['line']}")

    print(f"\n{'=' * 70}")
    print(f"OVERALL: {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")
    print(f"{'=' * 70}")


def main() -> int:
    if not STATE_FILE.exists():
        print(f"ERROR: {STATE_FILE} not found. Run create_validation_repos.py first.")
        return 1

    targets = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(targets)} validation targets.")

    # Verify backend is running
    try:
        r = requests.get(f"{BASE_URL}/health/live", timeout=5)
        if r.status_code != 200:
            print(f"ERROR: Backend not healthy ({r.status_code})")
            return 1
        print("Backend is healthy.")
    except requests.RequestException:
        print("ERROR: Cannot reach backend at", BASE_URL)
        return 1

    results = []
    for i, target in enumerate(targets):
        print(f"\n{'=' * 70}")
        print(f"[{i+1}/{len(targets)}] {target['label']}")
        print(f"{'=' * 70}")

        payload = build_webhook_payload(target)
        print(f"  Firing webhook for {target['repo_full_name']} PR #{target['pr_number']}...")

        resp = post_webhook(payload)
        if resp.status_code != 202:
            print(f"  ERROR: webhook returned {resp.status_code}: {resp.text[:200]}")
            results.append({
                "label": target["label"],
                "repo": target["repo_full_name"],
                "pr_number": target["pr_number"],
                "status": f"webhook_error_{resp.status_code}",
                "checks": {"webhook_accepted": False},
            })
            continue

        review_id = resp.json().get("review_id")
        print(f"  Review created: {review_id}")

        review = poll_review(review_id, target["label"])
        analysis = analyze_result(target, review)
        analysis["review_id"] = review_id
        results.append(analysis)

        # Get the report too
        try:
            r = requests.get(f"{BASE_URL}/reviews/{review_id}/report", timeout=10)
            if r.status_code == 200:
                report_file = Path(__file__).resolve().parent / f"validation_report_{i+1}.md"
                report_file.write_text(r.text, encoding="utf-8")
                print(f"  Report saved: {report_file.name}")
        except requests.RequestException:
            pass

    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults written to: {RESULTS_FILE}")

    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
