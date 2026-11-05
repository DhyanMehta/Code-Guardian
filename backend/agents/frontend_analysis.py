"""Bounded static JS/TS/TSX capabilities using the trusted TypeScript parser."""
import json
import re
import subprocess
from pathlib import Path

from backend.agents._diff_utils import parse_diff_hunks, function_overlaps_diff
from backend.agents._validation import safe_workspace_path
from backend.services.agent_coverage import current

SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
CAPABILITIES_VERSION = "frontend-static-v1"
CAPABILITIES = {
    "security": {"python": ["semgrep", "bandit", "gitleaks"],
                 "javascript": ["semgrep", "gitleaks"], "typescript": ["semgrep", "gitleaks"],
                 "tsx": ["semgrep", "gitleaks"]},
    "quality": ["function length against explicitly applicable retrieved standards"],
    "test_gap": ["relative named/default import references in .test/.spec files"],
    "documentation": ["existing exported-function JSDoc parameter consistency"],
}


def parse_sources(sources):
    tool = Path(__file__).resolve().parents[1] / "tools" / "frontend_ast.cjs"
    proc = subprocess.run(["node", str(tool)], input=json.dumps(sources), text=True,
                          encoding="utf-8", capture_output=True, timeout=30)
    if proc.returncode:
        raise ValueError("Frontend parser failed: " + proc.stderr[:500])
    return json.loads(proc.stdout)


def extend_result(name, state, result):
    """Append deterministic frontend results to the existing agent result shape."""
    if name == "security":
        return
    coverage = current.get()
    paths = [p for p in coverage.eligible_files if Path(p).suffix in SUFFIXES]
    if not paths:
        return
    root = state.get("workspace_path", "")
    hunks = parse_diff_hunks(state.get("diff", ""))
    result["agent_notes"][name].append("Frontend scope: exported function declarations and exported const arrow/functions. Documentation checks existing JSDoc parameter consistency; Quality requires an applicable retrieved function-length rule.")
    sources = [{"file": p, "source": safe_workspace_path(root, p).read_text(encoding="utf-8")} for p in paths]
    parsed = parse_sources(sources)
    tested = set()
    if name == "test_gap":
        tests = []
        for p in Path(root).rglob("*"):
            if {"node_modules", "vendor", ".git", "generated"}.intersection(p.parts):
                continue
            if p.suffix in SUFFIXES and re.search(r"\.(test|spec)\.[jt]sx?$", p.name):
                tests.append({"file": p.relative_to(root).as_posix(), "source": safe_workspace_path(root, p.relative_to(root).as_posix()).read_text(encoding="utf-8")})
        for test in parse_sources(tests) if tests else []:
            for item in test["imports"]:
                if not item["module"].startswith(".") or item["local"] not in test["references"]:
                    continue
                target = (Path(root) / test["file"]).parent / item["module"]
                for suffix in SUFFIXES:
                    for candidate in (target.with_suffix(suffix), target / ("index" + suffix)):
                        tested.add((str(candidate.resolve()), item["imported"]))
        result["agent_notes"][name].append("Frontend test checks use static import references; runtime coverage is unknown. No test framework is assumed.")
    passages = []
    if name == "quality":
        from backend.rag.retriever import retrieve
        retrieval = retrieve("JavaScript TypeScript function length positional parameter limits", installation_id=state.get("installation_id"), collection_name=state.get("standards_version"))
        if not retrieval.has_context:
            raise ValueError("Frontend Quality standards retrieval unavailable")
        passages = [p for p in retrieval.passages if "python" not in (p.text + p.source_file).lower()
                    or re.search(r"javascript|typescript|tsx", p.text, re.I)]
        if not passages:
            for path in paths:
                coverage.eligible_files.remove(path)
                coverage.excluded_files.append({"path": path, "reason": "No applicable frontend coding standard retrieved"})
            return
    for file in parsed:
        coverage.analyzed([file["file"]])
        for symbol in file["symbols"]:
            if not symbol["exported"] or not function_overlaps_diff(symbol["start_line"], symbol["end_line"], hunks.get(file["file"], [])):
                continue
            fn = {k: symbol[k] for k in ("name", "start_line", "end_line", "source", "params")}
            fn["file_path"] = file["file"]
            if name == "test_gap" and not re.search(r"\.(test|spec)\.[jt]sx?$", file["file"]):
                key = "default" if symbol["defaultExport"] else symbol["name"]
                if (str(safe_workspace_path(root, file["file"])), key) not in tested:
                    result["test_gap_result"][name]["gaps"].append({"function": fn, "risk_score": 0})
            if name == "documentation" and set(symbol["documented_params"]) - set(symbol["params"]):
                result["doc_result"][name]["flagged_functions"].append({"function": fn, "reason": "outdated"})
            if name == "quality":
                for passage in passages:
                    limit = re.search(r"(?:not exceed|at most|maximum of)\s+(\d+)\s+lines", passage.text.replace("*", ""), re.I)
                    if limit and "function" in passage.text.lower() and symbol["logic_lines"] > int(limit[1]):
                        result["quality_result"][name]["findings"].append({
                            "file_path": file["file"], "line": symbol["start_line"], "symbol": symbol["name"],
                            "rule_violated": "maximum_function_length", "severity": "medium", "evidence_kind": "verified",
                            "explanation": f"{symbol['logic_lines']} nonblank token-bearing body lines exceed the cited {limit[1]} line limit.",
                            "cited_passage": passage.text, "source_file": passage.source_file})
                        break
