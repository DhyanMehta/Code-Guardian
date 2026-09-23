"""Check GitHub token permissions."""
import sys
sys.path.insert(0, r"D:\Dhyan\Self Projects\Code-Guardian")

import requests
from backend.config import get_settings

token = get_settings().require("github_token")
headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
r = requests.get("https://api.github.com/user", headers=headers)
print(f"Status: {r.status_code}")
print(f"X-OAuth-Scopes: {r.headers.get('X-OAuth-Scopes', '(not present - likely fine-grained token)')}")
print(f"X-Accepted-OAuth-Scopes: {r.headers.get('X-Accepted-OAuth-Scopes', '(not present)')}")
print(f"User: {r.json().get('login', 'unknown')}")
