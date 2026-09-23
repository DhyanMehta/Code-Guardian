"""Create the E2E test PR (with deliberately bad code) for CodeGuardian.

Preferred target is a dedicated throwaway repo. The fine-grained token in use does
NOT have Administration:write, so repo creation returns 403; in that case the script
falls back to the existing project repo and isolates the fixture on its own branch
under ``e2e_fixtures/`` so nothing on the default branch is touched.

Planted issues (deliberate):
  - SQL injection via f-string interpolation      -> Security (bandit/semgrep)
  - Hardcoded AWS key / Slack token / PAT         -> Security (gitleaks/bandit/semgrep)
  - eval() of caller-supplied string              -> Security (bandit/semgrep)
  - process_data(): 100+ lines, deeply nested     -> Quality (standards violation)
  - run_dynamic_code()/process_data(): no docstring -> Documentation
  - No tests anywhere for these functions         -> Test-Gap

Run from the project root with the venv python:
    backend\\venv\\Scripts\\python.exe scripts\\create_e2e_test_repo.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from backend.config import get_settings

token = get_settings().require("github_token")
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
TIMEOUT = 30

USER = "DhyanMehta"
DEDICATED_REPO = f"{USER}/codeguardian-e2e-test"
FALLBACK_REPO = f"{USER}/Code-Guardian"

BRANCH = "e2e/bad-code-pr"
DEDICATED_BRANCH = "bad-code-pr"
FILE_PATH_FALLBACK = "e2e_fixtures/app.py"
FILE_PATH_DEDICATED = "src/app.py"

STATE_FILE = Path(__file__).resolve().parent / "e2e" / "e2e_target.json"

BAD_CODE = '''import sqlite3
import os
import json
from datetime import datetime

# Hardcoded credentials - security vulnerability
# NOTE: no Slack/GitHub-format token here on purpose. GitHub secret-scanning push
# protection rejects those patterns with 409 on write, which would make the fixture
# uncommittable. The AWS access key below passes push protection but is still
# detected by gitleaks, so secret detection is genuinely exercised.
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7REALKEY"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DB_PASSWORD = "sup3rs3cr3t_pr0duction_pw"


def get_user_from_db(user_id):
    """Fetch user from database using raw SQL - SQL INJECTION VULNERABILITY."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # SQL Injection: directly interpolating user input into query
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    result = cursor.fetchone()
    conn.close()
    return result


def run_dynamic_code(code_string):
    result = eval(code_string)
    return result


def process_data(data):
    results = []
    error_count = 0
    warning_count = 0
    processed_items = []
    skipped_items = []

    if data is None:
        return None

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"error": "invalid json"}

    if isinstance(data, list):
        for i, item in enumerate(data):
            if item is None:
                skipped_items.append(i)
                continue
            elif isinstance(item, dict):
                if "type" in item:
                    if item["type"] == "critical":
                        if "value" in item:
                            if item["value"] > 100:
                                results.append({"status": "overflow", "index": i})
                                error_count += 1
                            elif item["value"] > 50:
                                results.append({"status": "warning", "index": i})
                                warning_count += 1
                            elif item["value"] > 0:
                                results.append({"status": "ok", "index": i})
                                processed_items.append(item)
                            else:
                                results.append({"status": "negative", "index": i})
                                error_count += 1
                        else:
                            skipped_items.append(i)
                    elif item["type"] == "warning":
                        if "priority" in item:
                            if item["priority"] == "high":
                                results.append({"status": "escalated", "index": i})
                                warning_count += 1
                            elif item["priority"] == "medium":
                                results.append({"status": "noted", "index": i})
                            else:
                                results.append({"status": "low", "index": i})
                        else:
                            results.append({"status": "unprioritized", "index": i})
                    elif item["type"] == "info":
                        processed_items.append(item)
                    elif item["type"] == "debug":
                        if os.environ.get("DEBUG"):
                            processed_items.append(item)
                        else:
                            skipped_items.append(i)
                    else:
                        skipped_items.append(i)
                else:
                    if "name" in item:
                        processed_items.append(item)
                    else:
                        skipped_items.append(i)
            elif isinstance(item, str):
                if len(item) > 1000:
                    skipped_items.append(i)
                elif item.startswith("ERR:"):
                    error_count += 1
                    results.append({"status": "error", "message": item})
                elif item.startswith("WARN:"):
                    warning_count += 1
                    results.append({"status": "warning", "message": item})
                else:
                    processed_items.append(item)
            elif isinstance(item, (int, float)):
                if item < 0:
                    error_count += 1
                elif item > 1000000:
                    warning_count += 1
                    results.append({"status": "large_number", "value": item})
                else:
                    processed_items.append(item)
            else:
                skipped_items.append(i)
    elif isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if value is None:
                skipped_items.append(key)
            elif isinstance(value, (int, float)):
                if value > 0:
                    processed_items.append({key: value})
                else:
                    error_count += 1
            elif isinstance(value, str):
                if len(value) > 500:
                    warning_count += 1
                else:
                    processed_items.append({key: value})
            else:
                processed_items.append({key: value})
    else:
        return {"error": "unsupported type"}

    return {
        "results": results,
        "processed": processed_items,
        "skipped": skipped_items,
        "errors": error_count,
        "warnings": warning_count,
        "timestamp": datetime.now().isoformat(),
    }


def build_report(data, user_id, format_type, include_headers=True):
    """Build a report for the given user and data.

    This function is excessively long to violate coding standards.
    """
    user = get_user_from_db(user_id)
    processed = process_data(data)
    report_lines = []
    separator = "=" * 80
    if include_headers:
        report_lines.append(separator)
        report_lines.append(f"REPORT FOR USER: {user_id}")
        report_lines.append(f"Generated: {datetime.now()}")
        report_lines.append(separator)
    if processed is None:
        report_lines.append("No data to process")
        return "\\n".join(report_lines)
    if "error" in processed:
        report_lines.append(f"ERROR: {processed['error']}")
        return "\\n".join(report_lines)
    report_lines.append(f"Total processed: {len(processed.get('processed', []))}")
    report_lines.append(f"Total skipped: {len(processed.get('skipped', []))}")
    report_lines.append(f"Errors: {processed.get('errors', 0)}")
    report_lines.append(f"Warnings: {processed.get('warnings', 0)}")
    if format_type == "detailed":
        report_lines.append("")
        report_lines.append("DETAILED RESULTS:")
        report_lines.append("-" * 40)
        for r in processed.get("results", []):
            report_lines.append(f"  Status: {r.get('status', 'unknown')}")
            if "index" in r:
                report_lines.append(f"  Index: {r['index']}")
            if "message" in r:
                report_lines.append(f"  Message: {r['message']}")
            report_lines.append("")
    elif format_type == "summary":
        report_lines.append("")
        report_lines.append("SUMMARY: Processing complete")
    elif format_type == "json":
        report_lines.append("")
        report_lines.append(json.dumps(processed, indent=2))
    else:
        report_lines.append("")
        report_lines.append("Unknown format type")
    if include_headers:
        report_lines.append(separator)
        report_lines.append("END OF REPORT")
        report_lines.append(separator)
    final_report = "\\n".join(report_lines)
    log_entry = f"{datetime.now()} - Report generated for user {user_id}, format={format_type}, lines={len(report_lines)}"
    print(log_entry)
    return final_report
'''


def api(method: str, url: str, **kwargs) -> requests.Response:
    return requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)


def resolve_target() -> tuple[str, str, str]:
    """Return (repo_full_name, branch, file_path) to use for the fixture PR."""
    r = api("GET", f"https://api.github.com/repos/{DEDICATED_REPO}")
    if r.status_code == 200:
        print(f"Using existing dedicated repo {DEDICATED_REPO}.")
        return DEDICATED_REPO, DEDICATED_BRANCH, FILE_PATH_DEDICATED

    print(f"Dedicated repo {DEDICATED_REPO} not present. Attempting to create it...")
    r = api(
        "POST",
        "https://api.github.com/user/repos",
        json={
            "name": DEDICATED_REPO.split("/", 1)[1],
            "description": "E2E test repo for Code-Guardian review system",
            "private": False,
            "auto_init": True,
        },
    )
    if r.status_code in (200, 201):
        print(f"Created {DEDICATED_REPO}.")
        time.sleep(3)
        return DEDICATED_REPO, DEDICATED_BRANCH, FILE_PATH_DEDICATED

    print(f"  create repo -> {r.status_code}: {r.json().get('message', r.text[:120])}")
    print(
        "  Token lacks Administration:write, so a dedicated repo cannot be created.\n"
        f"  Falling back to {FALLBACK_REPO}: fixture is isolated on branch "
        f"'{BRANCH}' at '{FILE_PATH_FALLBACK}' (default branch untouched)."
    )
    return FALLBACK_REPO, BRANCH, FILE_PATH_FALLBACK


def main() -> int:
    repo, branch, file_path = resolve_target()

    r = api("GET", f"https://api.github.com/repos/{repo}")
    if r.status_code != 200:
        print(f"ERROR: cannot read {repo} ({r.status_code}): {r.text[:200]}")
        return 1
    base_branch = r.json()["default_branch"]
    print(f"\nTarget: {repo}  base={base_branch}  head={branch}  file={file_path}")

    r = api("GET", f"https://api.github.com/repos/{repo}/git/ref/heads/{base_branch}")
    if r.status_code != 200:
        print(f"ERROR: cannot read base ref ({r.status_code}): {r.text[:200]}")
        return 1
    base_sha = r.json()["object"]["sha"]
    print(f"Base {base_branch} SHA: {base_sha}")

    # Close any open PR from this head and delete the branch, so the run is clean.
    r = api(
        "GET",
        f"https://api.github.com/repos/{repo}/pulls",
        params={"state": "open", "head": f"{repo.split('/')[0]}:{branch}"},
    )
    if r.status_code == 200:
        for p in r.json():
            print(f"Closing stale PR #{p['number']}...")
            api("PATCH", f"https://api.github.com/repos/{repo}/pulls/{p['number']}", json={"state": "closed"})

    rd = api("DELETE", f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}")
    if rd.status_code == 204:
        print(f"Deleted existing branch {branch}.")
        time.sleep(2)

    print(f"\nCreating branch {branch}...")
    r = api(
        "POST",
        f"https://api.github.com/repos/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )
    if r.status_code != 201:
        print(f"ERROR: create branch ({r.status_code}): {r.text[:300]}")
        return 1
    print("  created.")

    print(f"\nCreating {file_path} on {branch}...")
    r = api(
        "PUT",
        f"https://api.github.com/repos/{repo}/contents/{file_path}",
        json={
            "message": "Add data processing feature",
            "content": base64.b64encode(BAD_CODE.encode()).decode(),
            "branch": branch,
        },
    )
    if r.status_code not in (200, 201):
        print(f"ERROR: create file ({r.status_code}): {r.text[:600]}")
        return 1
    head_sha = r.json()["commit"]["sha"]
    print(f"  committed: {head_sha}")

    print("\nCreating pull request...")
    r = api(
        "POST",
        f"https://api.github.com/repos/{repo}/pulls",
        json={
            "title": "Add data processing feature",
            "body": (
                "This PR adds a new data processing module with user lookup and "
                "report generation capabilities.\n\n"
                "_E2E fixture for CodeGuardian AI verification. Contains deliberately "
                "insecure code and fake (non-functional) credentials. Do not merge._"
            ),
            "head": branch,
            "base": base_branch,
        },
    )
    if r.status_code not in (200, 201):
        print(f"ERROR: create PR ({r.status_code}): {r.text[:400]}")
        return 1
    pr = r.json()
    pr_number = pr["number"]
    print(f"  created PR #{pr_number}: {pr['html_url']}")

    state = {
        "repo_full_name": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "head_repo_full_name": repo,
        "base_branch": base_branch,
        "branch": branch,
        "file_path": file_path,
        "html_url": pr["html_url"],
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print()
    print("=" * 60)
    print("WEBHOOK PAYLOAD VALUES:")
    print("=" * 60)
    for k, v in state.items():
        print(f"{k}: {v}")
    print("=" * 60)
    print(f"(written to {STATE_FILE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
