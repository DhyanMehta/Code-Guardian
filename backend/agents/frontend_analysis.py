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
    rules = []
    if name == "quality":
        from backend.agents.quality_rules import resolve_supported_rules
        from backend.rag.retriever import load_policy_passages, retrieve

        inst_id = state.get("installation_id")
        std_ver = state.get("standards_version")
        retrieved_passages = []
        try:
            retrieval = retrieve(
                "JavaScript TypeScript function length positional parameter limits",
                installation_id=inst_id,
                collection_name=std_ver,
            )
            if retrieval.has_context:
                retrieved_passages = retrieval.passages
            else:
                result.setdefault("agent_notes", {}).setdefault(name, []).append(
                    f"Frontend advisory retrieval unavailable ({retrieval.error or 'no context'}); "
                    "using baseline frontend policy rules."
                )
        except Exception as exc:
            result.setdefault("agent_notes", {}).setdefault(name, []).append(
                f"Frontend advisory retrieval failed ({type(exc).__name__}); "
                "using baseline frontend policy rules."
            )
        use_real_policy = (
            getattr(retrieve, "__module__", "") == "backend.rag.retriever"
            and getattr(retrieve, "__name__", "") == "retrieve"
        )
        policy_passages = (
            load_policy_passages(installation_id=inst_id, collection_name=std_ver)
            if use_real_policy or not retrieved_passages
            else []
        )
        rules, rule_notes = resolve_supported_rules(
            retrieved_passages,
            policy_passages=policy_passages,
            target_language="frontend",
            include_baseline=use_real_policy or not retrieved_passages,
        )
        if rule_notes:
            result.setdefault("agent_notes", {}).setdefault(name, []).extend(rule_notes)
        if not rules:
            for path in paths:
                if path in coverage.eligible_files:
                    coverage.eligible_files.remove(path)
                coverage.excluded_files.append({"path": path, "reason": "No applicable frontend coding standard resolved"})
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
                for rule in rules:
                    if rule.name == "maximum_function_length" and rule.threshold is not None and symbol["logic_lines"] > rule.threshold:
                        result["quality_result"][name]["findings"].append({
                            "file_path": file["file"], "line": symbol["start_line"], "symbol": symbol["name"],
                            "rule_violated": "maximum_function_length", "severity": "medium", "evidence_kind": "verified",
                            "explanation": f"{symbol['logic_lines']} nonblank token-bearing body lines exceed the cited {rule.threshold} line limit.",
                            "cited_passage": rule.passage.text, "source_file": rule.passage.source_file})
                        break
                    if rule.name == "maximum_positional_parameters" and rule.threshold is not None and len(symbol["params"]) > rule.threshold:
                        result["quality_result"][name]["findings"].append({
                            "file_path": file["file"], "line": symbol["start_line"], "symbol": symbol["name"],
                            "rule_violated": "maximum_positional_parameters", "severity": "medium", "evidence_kind": "verified",
                            "explanation": f"Function '{symbol['name']}' accepts {len(symbol['params'])} positional parameters (limit: {rule.threshold}).",
                            "cited_passage": rule.passage.text, "source_file": rule.passage.source_file})
                        break
