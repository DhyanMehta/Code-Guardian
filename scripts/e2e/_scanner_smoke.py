"""Prove all three scanners really run against the EXACT E2E fixture content.

Imports BAD_CODE from scripts/create_e2e_test_repo.py so what we verify here is
byte-identical to what gets committed to the PR.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from backend.tools import bandit_runner, gitleaks_runner, semgrep_runner  # noqa: E402

# Load BAD_CODE without executing the script's main().
spec = importlib.util.spec_from_file_location(
    "_e2e_fixture", ROOT / "scripts" / "create_e2e_test_repo.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BAD = mod.BAD_CODE

tmp = tempfile.mkdtemp(prefix="cg_smoke_")
target_file = os.path.join(tmp, "app.py")
with open(target_file, "w", encoding="utf-8") as fh:
    fh.write(BAD)
print(f"target: {tmp} ({len(BAD)} bytes)\n")

summary = {}
for name, fn in (
    ("bandit", lambda: bandit_runner.run(tmp)),
    ("semgrep", lambda: semgrep_runner.run(tmp)),
    ("gitleaks", lambda: gitleaks_runner.run(tmp)),
):
    t0 = time.monotonic()
    print(f"----- {name} -----")
    try:
        findings = fn()
        dt = time.monotonic() - t0
        summary[name] = len(findings)
        print(f"  RESULT: {len(findings)} finding(s) in {dt:.1f}s")
        for f in findings:
            print(
                f"    [{f.severity}] {f.rule_id} "
                f"{os.path.basename(f.file_path or '')}:{f.line} - {f.message[:90]}"
            )
    except Exception as exc:  # noqa: BLE001
        dt = time.monotonic() - t0
        summary[name] = f"FAILED: {exc.__class__.__name__}"
        print(f"  FAILED after {dt:.1f}s: {exc.__class__.__name__}: {exc}")
    print()

print("SUMMARY:", summary)
degraded = [k for k, v in summary.items() if not isinstance(v, int) or v == 0]
print("DEGRADED SCANNERS:", degraded or "none")
