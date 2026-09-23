"""Issue A verification: real Quality Agent run against the real E2E PR.

Same fixture that previously produced 21 fabricated "class TimeoutError" findings.
Uses the real checkout, the real ChromaDB collection, and a real Groq call.

Checks:
  1. Which standards passages the augmented retrieval query surfaces (with distances).
  2. The raw Groq response (what the model actually claimed this run).
  3. Which findings were rejected, and the WARNING lines proving it.
  4. Every accepted finding independently re-verified against the file's AST.
  5. Whether a function-length violation is now reported.
  6. A REPLAY of the exact recorded fabrication from the previous session, so the
     gate is proven against the observed payload rather than whatever the model
     happens to emit today. Clearly labelled: the replayed text is the recorded
     response, not a fresh model output.
"""
from __future__ import annotations

import ast
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)

from backend.agents.quality_agent import MODULE_SYMBOL, QualityAgent  # noqa: E402
from backend.agents.state import AgentOutcome  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.rag.retriever import retrieve  # noqa: E402
from backend.tools.llm_client import LLMClient  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
token = get_settings().require("github_token")
fixture_rel = state["file_path"]


class _RecordingLLM(LLMClient):
    """Real Groq client that also keeps the raw request/response."""

    def __init__(self) -> None:
        super().__init__()
        self.raw_response = ""
        self.user_prompt = ""
        self.json_mode = None

    def complete(self, **kwargs) -> str:
        self.user_prompt = kwargs.get("user_prompt", "")
        self.json_mode = kwargs.get("json_mode")
        self.raw_response = super().complete(**kwargs)
        return self.raw_response


class _ReplayLLM:
    """Returns a fixed, previously-recorded response. No model is called."""

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, **kwargs) -> str:
        return self._response


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    print("=" * 72)
    print("ISSUE A — real Quality Agent run")
    print("=" * 72)
    print(f"repo      : {state['repo_full_name']} PR #{state['pr_number']}")
    print(f"head sha  : {state['head_sha']}")
    print(f"fixture   : {fixture_rel}")
    print(f"workspace : {ws.path}\n")

    diff = subprocess.run(
        ["git", "diff", "HEAD~1"], cwd=ws.path, capture_output=True, text=True, timeout=30
    ).stdout
    print(f"diff bytes: {len(diff)}\n")

    agent = QualityAgent()
    changed = [fixture_rel]

    # ---------------------------------------------------------------- #
    # 1. Retrieval with the augmented (AST-fact-led) query
    # ---------------------------------------------------------------- #
    print("-" * 72)
    print("1. RETRIEVAL — augmented query")
    print("-" * 72)
    query = agent._build_retrieval_query(diff, changed, ws.path)
    print("query sent to ChromaDB:")
    for line in query.splitlines():
        print(f"    {line}")

    result_r = retrieve(query)
    print(f"\nretrieved {len(result_r.passages)} passage(s):")
    for i, p in enumerate(result_r.passages):
        head = p.text.strip().splitlines()[0]
        print(f"  [{i}] distance={p.distance:.3f}  {head}")
    length_idx = [
        i for i, p in enumerate(result_r.passages)
        if "40 lines" in p.text or "Function Length" in p.text
    ]
    print(f"\nfunction-length passage retrieved: {bool(length_idx)} (index {length_idx})")

    old_query = "\n".join(["Files changed: " + ", ".join(changed), diff[:3000]])
    old_result = retrieve(old_query)
    old_has_length = any(
        "40 lines" in p.text or "Function Length" in p.text for p in old_result.passages
    )
    print(f"previous diff-only query retrieved it: {old_has_length} "
          f"({len(old_result.passages)} passage(s))")

    # ---------------------------------------------------------------- #
    # 2 + 3. Real agent run (real Groq), with rejection logging
    # ---------------------------------------------------------------- #
    print()
    print("-" * 72)
    print("2. REAL GROQ CALL + GATES (WARNING lines are real-time rejections)")
    print("-" * 72)
    llm = _RecordingLLM()
    result = QualityAgent(llm_client=llm).run(diff, changed, ws.path)

    print(f"\njson_mode requested: {llm.json_mode}")
    print(f"raw response length: {len(llm.raw_response)} chars")
    try:
        raw_obj = json.loads(llm.raw_response)
        claimed = raw_obj.get("findings", []) if isinstance(raw_obj, dict) else raw_obj
        print(f"raw response is valid JSON: True ({len(claimed)} finding(s) claimed)")
    except json.JSONDecodeError as exc:
        claimed = []
        print(f"raw response is valid JSON: False ({exc})")

    print("\nWHAT THE MODEL CLAIMED (raw, pre-gate):")
    for i, item in enumerate(claimed):
        print(f"  [{i}] symbol={item.get('symbol')!r} rule={item.get('rule_violated')!r} "
              f"sev={item.get('severity')!r}")

    # ---------------------------------------------------------------- #
    # 4. Accepted findings, independently re-verified against the AST
    # ---------------------------------------------------------------- #
    print()
    print("-" * 72)
    print("3. ACCEPTED FINDINGS (after gates + dedup)")
    print("-" * 72)
    print(f"outcome        : {result.outcome.value}")
    print(f"failure_reason : {result.failure_reason}")
    print(f"accepted       : {len(result.findings)}")
    for f in result.findings:
        print(f"\n  symbol={f.symbol!r} line={f.line} severity={f.severity}")
        print(f"    rule       : {f.rule_violated}")
        print(f"    explanation: {f.explanation[:200]}")
        print(f"    cites      : {f.source_file} :: {f.cited_passage[:100]!r}")

    print("\nnotes:")
    for n in result.notes:
        print(f"  - {n}")

    source = (Path(ws.path) / fixture_rel).read_text(encoding="utf-8")
    tree = ast.parse(source)
    real_symbols = set()
    func_lengths: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            real_symbols.add(node.name)
            if isinstance(node, ast.FunctionDef):
                func_lengths[node.name] = node.end_lineno - node.lineno + 1
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    real_symbols.add(t.id)

    print()
    print("-" * 72)
    print("4. INDEPENDENT VERIFICATION")
    print("-" * 72)

    # --- <module> escape-hatch audit ------------------------------------- #
    raw_module_claims = [
        i for i in claimed if str(i.get("symbol")) == MODULE_SYMBOL
    ]
    accepted_module = [f for f in result.findings if f.symbol == MODULE_SYMBOL]
    print(f"raw findings claiming '{MODULE_SYMBOL}'      : {len(raw_module_claims)}")
    for i in raw_module_claims:
        print(f"    rule={i.get('rule_violated')!r} explanation="
              f"{str(i.get('explanation'))[:90]!r}")
    print(f"accepted findings still '{MODULE_SYMBOL}'   : {len(accepted_module)}")
    smuggled = [
        i for i in raw_module_claims
        if any(w in real_symbols for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*",
                                                    str(i.get("explanation", ""))))
    ]
    print(f"  of those, ones naming a real symbol (must end up re-anchored): "
          f"{len(smuggled)}")
    still_module_but_naming_symbol = [
        f for f in accepted_module
        if any(w in real_symbols for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*",
                                                    f.explanation))
    ]
    print(f"  ESCAPED the re-anchor (must be 0): {len(still_module_but_naming_symbol)}")

    # --- countable-claim truth audit ------------------------------------ #
    param_re = re.compile(
        r"(\d+)[\s-]*(?:positional|keyword|function|input|required)?[\s-]*"
        r"(?:parameters?|params?|arguments?|args)\b", re.IGNORECASE)
    length_re = re.compile(
        r"(\d+)[\s-]*(?:source|logical|logic|physical)?[\s-]*lines?\b", re.IGNORECASE)

    real_params: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = node.args
            names = {
                a.arg for a in args.args + args.posonlyargs + args.kwonlyargs
                if a.arg not in ("self", "cls")
            }
            if args.vararg:
                names.add(args.vararg.arg)
            if args.kwarg:
                names.add(args.kwarg.arg)
            real_params[node.name] = len(names)

    print(f"\nreal parameter counts: {real_params}")

    false_numeric = []
    for f in result.findings:
        text = f"{f.rule_violated} {f.explanation}"
        p = [int(m.group(1)) for m in param_re.finditer(text)]
        if p and f.symbol in real_params and real_params[f.symbol] < min(p):
            false_numeric.append(
                f"{f.symbol}: claims >{min(p)} params, really "
                f"{real_params[f.symbol]}  [{f.rule_violated}]"
            )
        n = [int(m.group(1)) for m in length_re.finditer(text)]
        if n and f.symbol in func_lengths and func_lengths[f.symbol] < min(n) * 0.75:
            false_numeric.append(
                f"{f.symbol}: claims >{min(n)} lines, really "
                f"{func_lengths[f.symbol]}  [{f.rule_violated}]"
            )
    print(f"accepted findings with a contradicted count (must be 0): "
          f"{len(false_numeric)}")
    for line in false_numeric:
        print(f"    {line}")

    print()
    fabricated = [
        f.symbol for f in result.findings
        if f.symbol != MODULE_SYMBOL and f.symbol not in real_symbols
    ]
    print(f"accepted findings naming a NON-EXISTENT symbol: {len(fabricated)} {fabricated}")
    print(f"accepted 'TimeoutError' findings: "
          f"{len([f for f in result.findings if f.symbol == 'TimeoutError'])}")
    keys = [(f.file_path, f.symbol, f.rule_violated) for f in result.findings]
    print(f"duplicate (file, symbol, rule) keys among accepted: {len(keys) - len(set(keys))}")
    print(f"real function lengths: {func_lengths}")

    length_findings = [
        f for f in result.findings
        if "length" in f.rule_violated.lower()
        or "line" in f.rule_violated.lower()
        or "complex" in f.rule_violated.lower()
        or "40 lines" in f.cited_passage
    ]
    print(f"\nfunction-length / complexity findings reported: {len(length_findings)}")
    for f in length_findings:
        print(f"  {f.symbol} (actually {func_lengths.get(f.symbol, '?')} lines) "
              f"-> {f.rule_violated} [{f.severity}] line={f.line}")

    # ---------------------------------------------------------------- #
    # 6. Replay of the recorded fabrication
    # ---------------------------------------------------------------- #
    print()
    print("=" * 72)
    print("5. REPLAY OF THE RECORDED FABRICATION (no model called)")
    print("=" * 72)
    print("Replaying the payload recorded in the previous session: 21 identical")
    print("findings about 'class TimeoutError', which does not exist in the fixture.")
    print("Variant (a) is the payload exactly as recorded (the old schema had no")
    print("'symbol' field). Variant (b) adds symbol='TimeoutError', which is what the")
    print("same claim looks like under the new schema.\n")

    recorded_finding = {
        "passage_index": 1,
        "file_path": fixture_rel,
        "line": None,
        "rule_violated": "1.2 Classes",
        "explanation": (
            "Exception classes must end with Error: ScannerTimeoutError, "
            "LLMConfigError. However, the code defines a class called 'TimeoutError' "
            "without the 'Error' suffix."
        ),
        "severity": "high",
    }

    for label, extra in (
        ("(a) exactly as recorded, no symbol field", {}),
        ("(b) same claim with symbol='TimeoutError'", {"symbol": "TimeoutError"}),
    ):
        payload = json.dumps(
            {"findings": [{**recorded_finding, **extra} for _ in range(21)]}
        )
        print(f"--- {label} — 21 findings replayed ---")
        replay = QualityAgent(llm_client=_ReplayLLM(payload)).run(
            diff, changed, ws.path
        )
        print(f"    accepted : {len(replay.findings)}")
        print(f"    outcome  : {replay.outcome.value}")
        for n in replay.notes:
            print(f"    note     : {n}")
        print()

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  fabricated symbols accepted (live run) : {len(fabricated)} (must be 0)")
    print(f"  duplicates accepted (live run)         : {len(keys) - len(set(keys))} (must be 0)")
    print(f"  length rule retrieved                  : {bool(length_idx)}")
    print(f"  length/complexity violation reported   : {len(length_findings) > 0}")
    print(f"  outcome                                : {result.outcome.value}")
