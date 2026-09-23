"""Replay the two observed defects against the REAL checkout.

No model is called: these are the exact finding payloads recorded from real Groq
runs on this PR, replayed through the real gates against the real file on disk.

  1. `<module>` escape-hatch bypass — three findings claimed file scope while their
     explanations named `process_data`, which sits at line 32 of the real fixture.
  2. False parameter counts — `process_data` (1 param) and `build_report` (4 params)
     were both claimed to accept "more than 5 positional parameters".
"""
from __future__ import annotations

import ast
import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")

from backend.agents.quality_agent import MODULE_SYMBOL, QualityAgent  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.rag.retriever import RetrievalResult, RetrievedPassage  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
token = get_settings().require("github_token")
fixture_rel = state["file_path"]

# Fixed passages so the replay is fully deterministic: only the gates vary.
_PASSAGES = [
    (
        "## 1. Naming Conventions\n\n- Use snake_case for functions.",
        "python_coding_standards.md",
    ),
    (
        "## 2. Function Length and Complexity\n\n### 2.1 Maximum Function Length\n\n"
        "- A single function or method should not exceed 40 lines of logic.\n"
        "- A function should not take more than 5 parameters.",
        "python_coding_standards.md",
    ),
]


def _retriever(query_text: str, **kwargs) -> RetrievalResult:
    result = RetrievalResult(query_text=query_text)
    result.passages = [
        RetrievedPassage(text=t, source_file=s, distance=0.2, chunk_id=f"c{i}")
        for i, (t, s) in enumerate(_PASSAGES)
    ]
    return result


class _ReplayLLM:
    def __init__(self, findings: list[dict]) -> None:
        self._payload = json.dumps({"findings": findings})

    def complete(self, **kwargs) -> str:
        return self._payload


# The exact payloads observed in the real run.
MODULE_BYPASS = [
    {
        "passage_index": 1,
        "file_path": fixture_rel,
        "symbol": MODULE_SYMBOL,
        "line": None,
        "rule_violated": "Maximum Function Length",
        "explanation": "The function 'process_data' exceeds 40 lines of logic",
        "severity": "high",
    },
    {
        "passage_index": 1,
        "file_path": fixture_rel,
        "symbol": MODULE_SYMBOL,
        "line": None,
        "rule_violated": "Cyclomatic Complexity",
        "explanation": "The function 'process_data' has a high cyclomatic complexity",
        "severity": "high",
    },
]

FALSE_COUNTS = [
    {
        "passage_index": 1,
        "file_path": fixture_rel,
        "symbol": MODULE_SYMBOL,
        "line": None,
        "rule_violated": "Parameter Count",
        "explanation": (
            "The function 'process_data' accepts more than 5 positional parameters"
        ),
        "severity": "high",
    },
    {
        "passage_index": 1,
        "file_path": fixture_rel,
        "symbol": "build_report",
        "line": 148,
        "rule_violated": "Parameter Count",
        "explanation": (
            "The function 'build_report' accepts more than 5 positional parameters"
        ),
        "severity": "high",
    },
    {
        "passage_index": 1,
        "file_path": fixture_rel,
        "symbol": "run_dynamic_code",
        "line": 27,
        "rule_violated": "Maximum Function Length",
        "explanation": "run_dynamic_code exceeds 40 lines of logic",
        "severity": "high",
    },
]


def replay(label: str, findings: list[dict], workspace: str) -> None:
    print()
    print("=" * 72)
    print(label)
    print("=" * 72)
    for f in findings:
        print(f"  IN  symbol={f['symbol']!r} rule={f['rule_violated']!r}")
        print(f"      explanation={f['explanation']!r}")
    print()
    result = QualityAgent(
        llm_client=_ReplayLLM(findings), retriever_fn=_retriever
    ).run("diff --git a/x b/x\n@@ -1 +1 @@\n+x\n", [fixture_rel], workspace)
    print(f"  accepted: {len(result.findings)}")
    for f in result.findings:
        print(f"  OUT symbol={f.symbol!r} line={f.line} rule={f.rule_violated!r}")
    for n in result.notes:
        print(f"  note: {n}")


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    print(f"workspace: {ws.path}")
    source = (Path(ws.path) / fixture_rel).read_text(encoding="utf-8")
    tree = ast.parse(source)
    print("\nreal coordinates measured from the checked-out file:")
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = node.args
            names = [a.arg for a in args.args + args.posonlyargs + args.kwonlyargs]
            print(f"  {node.name:20} line={node.lineno:4} "
                  f"span={node.end_lineno - node.lineno + 1:4} lines  "
                  f"params={len(names)} {names}")

    replay(
        "1. '<module>' BYPASS REPLAY  (expect re-anchor to process_data @ line 32)",
        MODULE_BYPASS,
        ws.path,
    )
    replay(
        "2. FALSE COUNT REPLAY  (expect all three dropped)",
        FALSE_COUNTS,
        ws.path,
    )
