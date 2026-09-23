"""Probe: exact file_path strings each scanner reports for the same file.

Diff headers are repo-relative, so scoping depends on these being normalizable to
that form. Gitleaks runs in Docker against a bind mount, which makes its paths a
likely mismatch.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)

from backend.tools import bandit_runner, gitleaks_runner, semgrep_runner  # noqa: E402

CODE = '''AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7REALKEY"
DB_PASSWORD = "sup3rs3cr3t_pr0duction_pw"


def run_it(code):
    return eval(code)
'''

tmp = tempfile.mkdtemp(prefix="cg_path_")
sub = os.path.join(tmp, "e2e_fixtures")
os.makedirs(sub)
with open(os.path.join(sub, "app.py"), "w", encoding="utf-8") as fh:
    fh.write(CODE)

print(f"workspace: {tmp}")
print("expected repo-relative path: e2e_fixtures/app.py\n")

for name, fn in (
    ("bandit", bandit_runner.run),
    ("semgrep", semgrep_runner.run),
    ("gitleaks", gitleaks_runner.run),
):
    try:
        for f in fn(tmp):
            p = f.file_path
            print(f"{name:9} rule={f.rule_id[:40]:40} line={f.line}")
            print(f"          file_path={p!r}")
            print(f"          is_absolute={Path(p).is_absolute() if p else None}")
    except Exception as exc:  # noqa: BLE001
        print(f"{name}: FAILED {exc.__class__.__name__}: {exc}")
    print()
