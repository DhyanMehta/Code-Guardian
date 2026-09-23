"""Inspect current GitHub state relevant to the E2E run (read-only)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests  # noqa: E402

from backend.config import get_settings  # noqa: E402

token = get_settings().require("github_token")
H = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

r = requests.get("https://api.github.com/user", headers=H, timeout=20)
print(f"GET /user -> {r.status_code}")
if r.ok:
    print("  login:", r.json().get("login"))
print("  x-oauth-scopes:", r.headers.get("x-oauth-scopes"))
print("  x-ratelimit-remaining:", r.headers.get("x-ratelimit-remaining"))

for full in ("DhyanMehta/codeguardian-e2e-test", "DhyanMehta/Code-Guardian"):
    print(f"\n=== {full} ===")
    r = requests.get(f"https://api.github.com/repos/{full}", headers=H, timeout=20)
    print(f"  GET repo -> {r.status_code}")
    if not r.ok:
        print("   ", r.text[:200])
        continue
    j = r.json()
    print(f"  private={j['private']} default_branch={j['default_branch']} fork={j['fork']}")
    print(f"  pushed_at={j['pushed_at']} size={j['size']}KB")
    perms = j.get("permissions", {})
    print(f"  permissions={perms}")

    rb = requests.get(f"https://api.github.com/repos/{full}/branches?per_page=100", headers=H, timeout=20)
    if rb.ok:
        print("  branches:", [b["name"] for b in rb.json()])

    rp = requests.get(f"https://api.github.com/repos/{full}/pulls?state=all&per_page=20", headers=H, timeout=20)
    if rp.ok:
        for p in rp.json():
            print(
                f"  PR #{p['number']} [{p['state']}] '{p['title']}' "
                f"head={p['head']['label']} base={p['base']['label']} "
                f"head_repo={(p['head']['repo'] or {}).get('full_name')} "
                f"sha={p['head']['sha'][:8]}"
            )
