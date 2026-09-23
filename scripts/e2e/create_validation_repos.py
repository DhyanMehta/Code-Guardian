"""Fork small Python libraries and create realistic PRs for CodeGuardian validation.

Unlike the crafted e2e fixture (which has planted issues), these PRs contain
realistic code changes to test how CodeGuardian behaves on unfamiliar, real code.

Repos:
  A) theskumar/python-dotenv — clean, small (~15 files). Tests false-positive rate.
  B) encode/httpx — medium, modern Python. Tests diff-scoping and clone performance.
  C) A small Flask app starter — realistic imperfect code. Tests true-positive rate.

Run from the project root with the venv python:
    backend\\venv\\Scripts\\python.exe scripts\\e2e\\create_validation_repos.py
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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

STATE_FILE = Path(__file__).resolve().parent / "validation_targets.json"


def api(method: str, url: str, **kwargs) -> requests.Response:
    return requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)


def fork_repo(upstream: str) -> str:
    """Fork upstream repo to USER's account. Returns fork full_name."""
    fork_name = f"{USER}/{upstream.split('/')[1]}"

    # Check if fork already exists
    r = api("GET", f"https://api.github.com/repos/{fork_name}")
    if r.status_code == 200:
        print(f"  Fork {fork_name} already exists.")
        return fork_name

    print(f"  Forking {upstream} -> {fork_name}...")
    r = api("POST", f"https://api.github.com/repos/{upstream}/forks")
    if r.status_code not in (200, 202):
        print(f"  ERROR forking: {r.status_code} {r.text[:200]}")
        return ""

    # Wait for fork to be ready
    for _ in range(15):
        time.sleep(3)
        r = api("GET", f"https://api.github.com/repos/{fork_name}")
        if r.status_code == 200:
            print(f"  Fork ready: {fork_name}")
            return fork_name
    print("  ERROR: fork not ready after 45s")
    return ""


def create_branch(repo: str, branch: str, base_branch: str = "") -> str:
    """Create a branch on the repo. Returns base SHA or empty on failure."""
    if not base_branch:
        r = api("GET", f"https://api.github.com/repos/{repo}")
        if r.status_code != 200:
            return ""
        base_branch = r.json()["default_branch"]

    r = api("GET", f"https://api.github.com/repos/{repo}/git/ref/heads/{base_branch}")
    if r.status_code != 200:
        print(f"  ERROR reading base ref: {r.status_code}")
        return ""
    base_sha = r.json()["object"]["sha"]

    # Delete existing branch if present
    api("DELETE", f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}")
    time.sleep(1)

    r = api(
        "POST",
        f"https://api.github.com/repos/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )
    if r.status_code != 201:
        print(f"  ERROR creating branch: {r.status_code} {r.text[:200]}")
        return ""
    return base_sha


def create_file(repo: str, branch: str, path: str, content: str, message: str) -> str:
    """Create or update a file. Returns commit SHA or empty on failure."""
    # Check if file exists (need its sha for update)
    r = api("GET", f"https://api.github.com/repos/{repo}/contents/{path}", params={"ref": branch})
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]

    r = api("PUT", f"https://api.github.com/repos/{repo}/contents/{path}", json=payload)
    if r.status_code not in (200, 201):
        print(f"  ERROR creating file {path}: {r.status_code} {r.text[:300]}")
        return ""
    return r.json()["commit"]["sha"]


def open_pr(repo: str, branch: str, base_branch: str, title: str, body: str) -> dict:
    """Open a PR. Returns PR info dict or empty dict on failure."""
    # Close existing PRs from this branch
    r = api(
        "GET",
        f"https://api.github.com/repos/{repo}/pulls",
        params={"state": "open", "head": f"{USER}:{branch}"},
    )
    if r.status_code == 200:
        for p in r.json():
            api("PATCH", f"https://api.github.com/repos/{repo}/pulls/{p['number']}", json={"state": "closed"})

    r = api(
        "POST",
        f"https://api.github.com/repos/{repo}/pulls",
        json={"title": title, "body": body, "head": branch, "base": base_branch},
    )
    if r.status_code not in (200, 201):
        print(f"  ERROR creating PR: {r.status_code} {r.text[:300]}")
        return {}
    pr = r.json()
    return {"number": pr["number"], "html_url": pr["html_url"], "head_sha": pr["head"]["sha"]}


# ---------------------------------------------------------------------------
# Repo A: python-dotenv — add a utility function (clean code, minor style issue)
# ---------------------------------------------------------------------------

DOTENV_UTIL_CODE = '''"""Convenience utilities for dotenv loading with typed access."""

import os
from typing import Optional


def get_typed_env(key: str, cast_type=str, default=None):
    """Retrieve an environment variable and cast it to the specified type.

    Parameters
    ----------
    key : str
        Environment variable name.
    cast_type : type
        Type to cast the value to (str, int, float, bool).
    default
        Value to return if the variable is not set.

    Returns
    -------
    The casted value or default.
    """
    raw = os.environ.get(key)
    if raw is None:
        return default

    if cast_type is bool:
        return raw.lower() in ("1", "true", "yes", "on")

    try:
        return cast_type(raw)
    except (ValueError, TypeError):
        return default


def require_env(key: str) -> str:
    """Get a required environment variable or raise RuntimeError."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable {key} is not set or empty")
    return value


def load_env_file(filepath: str, override: bool = False) -> dict:
    """Parse a .env file manually without python-dotenv dependency.

    This is a lightweight fallback for environments where installing
    python-dotenv is not practical. It handles:
    - Comments (# prefix)
    - Blank lines
    - KEY=VALUE pairs
    - Quoted values (single and double)
    - Export prefix (export KEY=VALUE)

    Parameters
    ----------
    filepath : str
        Path to the .env file.
    override : bool
        If True, overwrite existing env vars.
    """
    result = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                result[key] = value
                if override or key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass
    return result


def env_snapshot() -> dict:
    """Return a dict of all current environment variables.

    Useful for debugging configuration issues in CI/CD pipelines.
    WARNING: This may expose sensitive values - use only in development.
    """
    return dict(os.environ)
'''


# ---------------------------------------------------------------------------
# Repo B: httpx — add a retry utility (medium repo, tests clone + scoping)
# ---------------------------------------------------------------------------

HTTPX_UTIL_CODE = '''"""HTTP request retry helper with exponential backoff."""

import time
import random
from typing import Optional, Callable, Any


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_status: Optional[list] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_status = retry_on_status or [429, 500, 502, 503, 504]


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for the given attempt number using exponential backoff."""
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)
    if config.jitter:
        delay = delay * (0.5 + random.random())
    return delay


def should_retry(status_code: int, attempt: int, config: RetryConfig) -> bool:
    """Determine if a request should be retried based on status and attempt count."""
    if attempt >= config.max_retries:
        return False
    return status_code in config.retry_on_status


def retry_request(
    request_func: Callable[[], Any],
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, float, int], None]] = None,
) -> Any:
    """Execute a request function with retry logic.

    Parameters
    ----------
    request_func : callable
        A callable that performs the HTTP request and returns a response.
    config : RetryConfig, optional
        Retry configuration. Uses defaults if not provided.
    on_retry : callable, optional
        Callback invoked before each retry with (attempt, delay, status_code).

    Returns
    -------
    The response from request_func.

    Raises
    ------
    Exception
        The last exception if all retries are exhausted.
    """
    if config is None:
        config = RetryConfig()

    last_exception = None
    for attempt in range(config.max_retries + 1):
        try:
            response = request_func()
            if hasattr(response, "status_code"):
                if not should_retry(response.status_code, attempt, config):
                    return response
                delay = calculate_delay(attempt, config)
                if on_retry:
                    on_retry(attempt, delay, response.status_code)
                time.sleep(delay)
            else:
                return response
        except Exception as exc:
            last_exception = exc
            if attempt >= config.max_retries:
                raise
            delay = calculate_delay(attempt, config)
            if on_retry:
                on_retry(attempt, delay, 0)
            time.sleep(delay)

    raise last_exception


class CircuitBreaker:
    """Simple circuit breaker to prevent repeated calls to a failing service."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def can_proceed(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        # half-open: allow one attempt
        return True

    def execute(self, func: Callable[[], Any]) -> Any:
        if not self.can_proceed():
            raise RuntimeError(
                f"Circuit breaker is open. {self.failure_count} consecutive failures. "
                f"Recovery in {self.recovery_timeout - (time.time() - self.last_failure_time):.1f}s"
            )
        try:
            result = func()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
'''


# ---------------------------------------------------------------------------
# Repo C: A small Flask app with realistic shortcuts (tests true-positive rate)
# We'll create this as a new repo since we need imperfect code
# ---------------------------------------------------------------------------

FLASK_APP_CODE = (Path(__file__).resolve().parent / "fixtures" / "flask_task_api.py").read_text(encoding="utf-8")


def setup_repo_a():
    """Fork python-dotenv, add a utility module."""
    print("\n" + "=" * 60)
    print("REPO A: python-dotenv (clean code, false-positive test)")
    print("=" * 60)

    upstream = "theskumar/python-dotenv"
    branch = "feature/typed-env-utils"

    repo = fork_repo(upstream)
    if not repo:
        return None

    # Get default branch
    r = api("GET", f"https://api.github.com/repos/{repo}")
    base_branch = r.json()["default_branch"]

    print(f"  Creating branch {branch}...")
    base_sha = create_branch(repo, branch, base_branch)
    if not base_sha:
        return None

    print(f"  Adding src/dotenv/typed_utils.py...")
    head_sha = create_file(
        repo, branch, "src/dotenv/typed_utils.py", DOTENV_UTIL_CODE,
        "Add typed environment variable utilities"
    )
    if not head_sha:
        return None

    print("  Opening PR...")
    pr = open_pr(
        repo, branch, base_branch,
        "Add typed environment variable utilities",
        "Adds convenience functions for typed env var access with casting, "
        "a lightweight .env parser fallback, and an env snapshot helper.\n\n"
        "_Validation PR for CodeGuardian AI testing._"
    )
    if not pr:
        return None

    print(f"  PR #{pr['number']}: {pr['html_url']}")
    return {
        "label": "python-dotenv (clean, false-positive test)",
        "repo_full_name": repo,
        "pr_number": pr["number"],
        "head_sha": pr["head_sha"],
        "branch": branch,
        "base_branch": base_branch,
        "html_url": pr["html_url"],
    }


def setup_repo_b():
    """Fork httpx, add a retry utility."""
    print("\n" + "=" * 60)
    print("REPO B: httpx (medium repo, clone + scoping test)")
    print("=" * 60)

    upstream = "encode/httpx"
    branch = "feature/retry-helper"

    repo = fork_repo(upstream)
    if not repo:
        return None

    r = api("GET", f"https://api.github.com/repos/{repo}")
    base_branch = r.json()["default_branch"]

    print(f"  Creating branch {branch}...")
    base_sha = create_branch(repo, branch, base_branch)
    if not base_sha:
        return None

    print(f"  Adding httpx/_retry.py...")
    head_sha = create_file(
        repo, branch, "httpx/_retry.py", HTTPX_UTIL_CODE,
        "Add retry helper with exponential backoff and circuit breaker"
    )
    if not head_sha:
        return None

    print("  Opening PR...")
    pr = open_pr(
        repo, branch, base_branch,
        "Add retry helper with circuit breaker",
        "Adds a retry utility with exponential backoff, jitter, and a "
        "simple circuit breaker pattern for resilient HTTP calls.\n\n"
        "_Validation PR for CodeGuardian AI testing._"
    )
    if not pr:
        return None

    print(f"  PR #{pr['number']}: {pr['html_url']}")
    return {
        "label": "httpx (medium, clone + scoping test)",
        "repo_full_name": repo,
        "pr_number": pr["number"],
        "head_sha": pr["head_sha"],
        "branch": branch,
        "base_branch": base_branch,
        "html_url": pr["html_url"],
    }


def setup_repo_c():
    """Create a small Flask app repo with realistic security shortcuts."""
    print("\n" + "=" * 60)
    print("REPO C: flask-task-api (imperfect code, true-positive test)")
    print("=" * 60)

    # Try to create a dedicated repo for this
    repo_name = "flask-task-api"
    repo_full = f"{USER}/{repo_name}"
    branch = "feature/task-crud"

    r = api("GET", f"https://api.github.com/repos/{repo_full}")
    if r.status_code != 200:
        print(f"  Creating repo {repo_full}...")
        r = api(
            "POST",
            "https://api.github.com/user/repos",
            json={
                "name": repo_name,
                "description": "Simple task management API for testing",
                "private": False,
                "auto_init": True,
            },
        )
        if r.status_code not in (200, 201):
            # Fallback: use Code-Guardian repo with an isolated branch
            print(f"  Cannot create repo ({r.status_code}). Using Code-Guardian fallback.")
            repo_full = f"{USER}/Code-Guardian"
            branch = "validation/flask-task-api"
        else:
            print(f"  Created {repo_full}.")
            time.sleep(3)

    r = api("GET", f"https://api.github.com/repos/{repo_full}")
    base_branch = r.json()["default_branch"]

    print(f"  Creating branch {branch}...")
    base_sha = create_branch(repo_full, branch, base_branch)
    if not base_sha:
        return None

    print(f"  Adding app.py...")
    head_sha = create_file(
        repo_full, branch, "app.py", FLASK_APP_CODE,
        "Add task management API"
    )
    if not head_sha:
        return None

    print("  Opening PR...")
    pr = open_pr(
        repo_full, branch, base_branch,
        "Add task management API with CRUD endpoints",
        "Quick prototype of a task management API with user registration, "
        "task CRUD, search, and export functionality.\n\n"
        "_Validation PR for CodeGuardian AI testing._"
    )
    if not pr:
        return None

    print(f"  PR #{pr['number']}: {pr['html_url']}")
    return {
        "label": "flask-task-api (imperfect, true-positive test)",
        "repo_full_name": repo_full,
        "pr_number": pr["number"],
        "head_sha": pr["head_sha"],
        "branch": branch,
        "base_branch": base_branch,
        "html_url": pr["html_url"],
    }


def main() -> int:
    print("CodeGuardian Validation — Creating test PRs on real repos")
    print("=" * 60)

    targets = []

    result_a = setup_repo_a()
    if result_a:
        targets.append(result_a)

    result_b = setup_repo_b()
    if result_b:
        targets.append(result_b)

    result_c = setup_repo_c()
    if result_c:
        targets.append(result_c)

    if not targets:
        print("\nERROR: No validation repos were set up successfully.")
        return 1

    STATE_FILE.write_text(json.dumps(targets, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"VALIDATION TARGETS ({len(targets)} repos ready)")
    print("=" * 60)
    for t in targets:
        print(f"\n  {t['label']}")
        print(f"    repo: {t['repo_full_name']}")
        print(f"    PR:   #{t['pr_number']} ({t['html_url']})")
        print(f"    SHA:  {t['head_sha']}")
    print(f"\nState written to: {STATE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
