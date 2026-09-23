"""E2E preflight check: ports, scanners, Docker, DB, config.

Run from project root with the venv python:
    backend\\venv\\Scripts\\python.exe scripts\\e2e\\_preflight.py
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.config import get_settings  # noqa: E402


def port(p: int) -> str:
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", p))
        return "OPEN"
    except Exception as exc:  # noqa: BLE001
        return f"CLOSED ({exc.__class__.__name__})"
    finally:
        s.close()


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, (cp.stdout + cp.stderr).strip()
    except FileNotFoundError:
        return 127, "not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


print("== python ==")
print(sys.executable)

print("\n== ports ==")
for p in (5432, 8000, 8001):
    print(f"  {p}: {port(p)}")

print("\n== scanner binaries on PATH ==")
for tool in ("semgrep", "bandit", "gitleaks", "docker", "git"):
    print(f"  {tool}: {shutil.which(tool) or 'NOT FOUND'}")

print("\n== versions ==")
for name, cmd in (
    ("bandit", ["bandit", "--version"]),
    ("semgrep", ["semgrep", "--version"]),
    ("gitleaks", ["gitleaks", "version"]),
    ("docker daemon", ["docker", "info", "--format", "{{.ServerVersion}}"]),
):
    rc, out = run(cmd)
    print(f"  {name}: rc={rc} {out.splitlines()[0] if out else ''}")

print("\n== config ==")
s = get_settings()
for field in ("groq_api_key", "github_token", "github_webhook_secret"):
    v = getattr(s, field)
    print(f"  {field}: {'SET (len=%d)' % len(v) if v else 'MISSING'}")
print(f"  groq_model: {s.groq_model}")
print(f"  database_url: {s.database_url.split('@')[-1] if '@' in s.database_url else s.database_url}")
print(f"  chroma_persist_dir: {s.chroma_persist_dir}")

print("\n== db connectivity ==")
try:
    from sqlalchemy import create_engine, text

    eng = create_engine(s.database_url, connect_args={"connect_timeout": 3})
    with eng.connect() as conn:
        print("  connected:", conn.execute(text("select version()")).scalar_one()[:60])
        rows = conn.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_schema='public' order by table_name"
            )
        ).scalars().all()
        print("  tables:", rows)
except Exception as exc:  # noqa: BLE001
    print(f"  FAILED: {exc.__class__.__name__}: {exc}")
