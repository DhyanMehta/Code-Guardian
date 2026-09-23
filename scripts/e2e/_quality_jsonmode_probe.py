"""Probe: does json_mode make the Quality Agent's Groq call parseable?

The agent calls LLMClient.complete() without json_mode, and on the real PR the model
returned 160 lines of malformed JSON, so every quality finding was discarded. The
client already supports json_mode; this checks whether enabling it is sufficient,
before touching production code. Also reports which standards passages the agent's
own retrieval query actually surfaces.
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
from backend.tools.llm_client import LLMClient  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
token = get_settings().require("github_token")


class _JsonModeLLM(LLMClient):
    """Same client, but forces JSON mode and records raw output."""

    def __init__(self) -> None:
        super().__init__()
        self.raw = ""

    def complete(self, **kwargs) -> str:
        kwargs["json_mode"] = True
        self.raw = super().complete(**kwargs)
        return self.raw


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    p = subprocess.run(
        ["git", "diff", "HEAD~1"], cwd=ws.path, capture_output=True, text=True, timeout=30
    )
    diff = p.stdout

# What does the agent's own retrieval query surface?
agent = QualityAgent()
query = agent._build_retrieval_query(diff, [state["file_path"]])
r = retrieve(query)
print("--- retrieval with the agent's real query (diff-based) ---")
print(f"has_context={r.has_context} passages={len(r.passages)}")
for i, ps in enumerate(r.passages):
    print(f"  [{i}] dist={ps.distance:.3f} {ps.text[:90]!r}")
print()

print("--- quality agent WITH json_mode ---")
llm = _JsonModeLLM()
result = QualityAgent(llm_client=llm).run(diff, [state["file_path"]])
print(f"raw response length: {len(llm.raw)} chars")
try:
    json.loads(llm.raw)
    print("raw response is valid JSON: True")
except json.JSONDecodeError as exc:
    print(f"raw response is valid JSON: False ({exc})")
print(f"findings: {len(result.findings)}")
for f in result.findings:
    print(f"  [{f.severity}] {f.rule_violated} @ {f.file_path}:{f.line}")
    print(f"      {f.explanation[:200]}")
    print(f"      cites {f.source_file}: {f.cited_passage[:110]!r}")
print(f"notes: {result.notes}")
print()
print("raw response (first 1200 chars):")
print(llm.raw[:1200])
