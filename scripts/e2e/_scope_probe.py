"""Probe: security findings and Groq triage payload size for the real PR.

Runs the real scanners over the real PR checkout through the real SecurityAgent,
with a stand-in LLM client that only records the prompt it is handed. That gives
the exact triage payload size without spending a Groq call.

Before/after reference (whole workspace, no diff scoping):
    437 raw findings, ~163,664 char payload (~41k tokens).
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from backend.agents.security_agent import SecurityAgent  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
token = get_settings().require("github_token")


class _RecordingLLM:
    """Captures the triage prompt instead of calling Groq."""

    def __init__(self) -> None:
        self.user_prompt = ""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return json.dumps({"findings": []})


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    print(f"workspace: {ws.path}\n")

    p = subprocess.run(
        ["git", "diff", "HEAD~1"], cwd=ws.path, capture_output=True, text=True, timeout=30
    )
    diff = p.stdout
    print(f"git diff HEAD~1 -> rc={p.returncode}, {len(diff)} bytes\n")

    # --- unscoped (previous behaviour) -------------------------------------- #
    llm_unscoped = _RecordingLLM()
    unscoped = SecurityAgent(llm_client=llm_unscoped).run(ws.path)
    print(f"UNSCOPED : {len(unscoped.raw_findings)} raw findings, "
          f"payload {len(llm_unscoped.user_prompt)} chars "
          f"(~{len(llm_unscoped.user_prompt)//4} tokens)")

    # --- scoped to the PR diff --------------------------------------------- #
    llm_scoped = _RecordingLLM()
    scoped = SecurityAgent(llm_client=llm_scoped).run(ws.path, diff)
    print(f"SCOPED   : {len(scoped.raw_findings)} raw findings, "
          f"payload {len(llm_scoped.user_prompt)} chars "
          f"(~{len(llm_scoped.user_prompt)//4} tokens)")

    print("\nScoped findings in detail:")
    for f in scoped.raw_findings:
        print(f"  [{f.severity.value:8}] {f.scanner:8} {f.rule_id:55} "
              f"{f.file_path}:{f.line}")

    print("\nPer-scanner status (scoped):")
    for s in scoped.scanner_statuses:
        print(f"  {s.scanner:9} ok={s.ok} count={s.finding_count} err={s.error_type}")

    print("\nFiles represented in scoped findings:",
          Counter(Path(f.file_path).name for f in scoped.raw_findings if f.file_path))
    print("Notes:", scoped.notes)
