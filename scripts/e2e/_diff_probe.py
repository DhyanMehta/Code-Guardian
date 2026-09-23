"""Probe: does the real checkout_pr workspace support `git diff HEAD~1`?

review_service._get_diff/_get_changed_files run `git diff HEAD~1` inside the
workspace produced by checkout_pr(), which clones with --depth=1. This script runs
the exact same commands against the real E2E PR head SHA and reports what happens.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from backend.config import get_settings  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
token = get_settings().require("github_token")


def git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    print(f"workspace: {ws.path}\n")

    for label, args in (
        ("rev-parse HEAD", ["rev-parse", "HEAD"]),
        ("rev-parse --is-shallow-repository", ["rev-parse", "--is-shallow-repository"]),
        ("log --oneline -n 5", ["log", "--oneline", "-n", "5"]),
        ("rev-parse HEAD~1", ["rev-parse", "HEAD~1"]),
        ("diff --name-only HEAD~1", ["diff", "--name-only", "HEAD~1"]),
    ):
        rc, out, err = git(args, ws.path)
        print(f"$ git {' '.join(args)}")
        print(f"  rc={rc}")
        if out:
            print("  stdout:", out.replace("\n", "\n          "))
        if err:
            print("  stderr:", err.replace("\n", "\n          "))
        print()

    rc, out, err = git(["diff", "HEAD~1"], ws.path)
    print(f"full `git diff HEAD~1`: rc={rc} len(stdout)={len(out)}")

    files = list(Path(ws.path).rglob("*.py"))
    print(f"\n.py files present in workspace: {len(files)}")
    fixture = Path(ws.path) / state["file_path"]
    print(f"fixture {state['file_path']} present: {fixture.exists()}")
