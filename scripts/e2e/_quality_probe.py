"""Probe: why did the Quality Agent report 0 findings for the real PR?

The fixture contains a 100+ line, deeply nested function, which should trip the
team's coding standards. This runs the real Quality Agent against the real PR diff
and prints the retrieval context, notes, and findings so the cause is visible.
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

from backend.agents.quality_agent import QualityAgent  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.rag.retriever import retrieve  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
settings = get_settings()
token = settings.require("github_token")

print(f"chroma_persist_dir setting: {settings.chroma_persist_dir}")
print(f"resolved: {Path(settings.chroma_persist_dir).resolve()}")
print(f"exists: {Path(settings.chroma_persist_dir).resolve().exists()}\n")

# Direct retrieval check, independent of the agent.
probe = retrieve("function length complexity nesting naming conventions")
print("--- direct retrieval probe ---")
print(f"has_context: {probe.has_context}")
print(f"error: {probe.error}")
print(f"passages: {len(probe.passages)}")
for i, p in enumerate(probe.passages[:3]):
    print(f"  [{i}] source={p.source_file} text={p.text[:120]!r}")
print()

with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    p = subprocess.run(
        ["git", "diff", "HEAD~1"], cwd=ws.path, capture_output=True, text=True, timeout=30
    )
    diff = p.stdout
    print(f"diff: {len(diff)} bytes\n")

    result = QualityAgent().run(diff, [state["file_path"]])

    print("--- quality agent result ---")
    print(f"findings: {len(result.findings)}")
    for f in result.findings:
        print(f"  [{f.severity}] {f.rule_violated} @ {f.file_path}:{f.line}")
        print(f"      {f.explanation[:160]}")
        print(f"      cites {f.source_file}: {f.cited_passage[:100]!r}")
    print(f"notes: {result.notes}")
    rc = result.retrieval_context
    if rc is not None:
        print(f"retrieval: has_context={rc.has_context} passages={len(rc.passages)} "
              f"error={rc.error}")
        for i, ps in enumerate(rc.passages):
            print(f"  [{i}] {ps.source_file}: {ps.text[:100]!r}")
