"""Shared helpers for the Session 5 end-to-end verification scripts."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from backend.config import get_settings  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
STATE_FILE = Path(__file__).resolve().parent / "e2e_target.json"


def target() -> dict[str, Any]:
    """The real PR created by scripts/create_e2e_test_repo.py."""
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"token {get_settings().require('github_token')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def pr_payload(
    *,
    action: str = "opened",
    repo_full_name: str | None = None,
    pr_number: int | None = None,
    head_sha: str | None = None,
    head_repo_full_name: str | None = None,
    head_ref: str | None = None,
) -> dict[str, Any]:
    """Build a GitHub ``pull_request`` webhook payload.

    Only the fields the receiver actually reads are populated, plus enough
    surrounding shape to be a faithful stand-in for a real delivery. Passing a
    different ``head_repo_full_name`` produces a fork-shaped payload.
    """
    t = target()
    repo = repo_full_name or t["repo_full_name"]
    head_repo = head_repo_full_name or repo
    owner = repo.split("/")[0]
    head_owner = head_repo.split("/")[0]
    ref = head_ref or t["branch"]

    return {
        "action": action,
        "number": pr_number or t["pr_number"],
        "pull_request": {
            "number": pr_number or t["pr_number"],
            "state": "open",
            "title": "Add data processing feature",
            "head": {
                "ref": ref,
                "sha": head_sha or t["head_sha"],
                "label": f"{head_owner}:{ref}",
                "repo": {
                    "full_name": head_repo,
                    "name": head_repo.split("/")[1],
                    "fork": head_repo != repo,
                    "owner": {"login": head_owner},
                },
            },
            "base": {
                "ref": t["base_branch"],
                "label": f"{owner}:{t['base_branch']}",
                "repo": {"full_name": repo, "owner": {"login": owner}},
            },
        },
        "repository": {
            "full_name": repo,
            "name": repo.split("/")[1],
            "owner": {"login": owner},
            "private": False,
        },
        "sender": {"login": owner},
    }


def post_webhook(payload: dict[str, Any], *, event: str = "pull_request"):
    """POST a correctly HMAC-signed webhook delivery, exactly as GitHub would."""
    secret = get_settings().require("github_webhook_secret")
    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return requests.post(
        f"{BASE_URL}/webhooks/github",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": "e2e-verification-delivery",
        },
        timeout=30,
    )


def show(response, label: str) -> Any:
    """Print a response verbatim and return its parsed body."""
    print(f"{label}: HTTP {response.status_code}")
    try:
        body = response.json()
        print("  body: " + json.dumps(body, indent=2).replace("\n", "\n  "))
        return body
    except ValueError:
        print(f"  body (raw): {response.text[:500]}")
        return None
