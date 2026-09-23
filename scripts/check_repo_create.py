"""Try creating repo via REST API directly to confirm permission issue."""
import sys
sys.path.insert(0, r"D:\Dhyan\Self Projects\Code-Guardian")

import requests
from backend.config import get_settings

token = get_settings().require("github_token")
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Try to create repo
payload = {
    "name": "codeguardian-e2e-test",
    "description": "E2E test repo for Code-Guardian review system",
    "private": False,
    "auto_init": False,
}

r = requests.post("https://api.github.com/user/repos", headers=headers, json=payload)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:500]}")

# Also check what repos we can access
print("\n--- Checking existing repos ---")
r2 = requests.get("https://api.github.com/user/repos?per_page=5&sort=updated", headers=headers)
print(f"List repos status: {r2.status_code}")
if r2.status_code == 200:
    repos = r2.json()
    for repo in repos[:5]:
        print(f"  - {repo['full_name']} (permissions: admin={repo['permissions'].get('admin')}, push={repo['permissions'].get('push')})")
