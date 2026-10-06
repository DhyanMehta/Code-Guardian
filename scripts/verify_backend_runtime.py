"""Read-only integration diagnostics using synthetic code, never a live PR.

Run from the repository root with the backend venv active:
python -m scripts.verify_backend_runtime [--github] [--llm]
"""
import argparse
import json
import tempfile
from pathlib import Path

from backend.tools import bandit_runner, semgrep_runner, gitleaks_runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    checks = {}
    with tempfile.TemporaryDirectory(prefix="cg_runtime_") as folder:
        Path(folder, "sample.py").write_text("def run(value):\n    assert value\n    return eval(value)\n", encoding="utf-8")
        for name, module in [("bandit", bandit_runner), ("semgrep", semgrep_runner), ("gitleaks", gitleaks_runner)]:
            try:
                findings = module.run(folder, timeout=45)
                checks[name] = {"status": "ok", "finding_count": len(findings), "rules": sorted({f.rule_id for f in findings})}
            except Exception as exc:
                checks[name] = {"status": "unavailable", "error_type": type(exc).__name__}
    if args.github:
        try:
            from backend.tools.github_app import get_integration
            installations = get_integration().get_installations()
            next(iter(installations), None)
            checks["github_app"] = {"status": "ok"}
        except Exception as exc:
            checks["github_app"] = {"status": "unavailable", "error_type": type(exc).__name__}
    if args.llm:
        try:
            from backend.tools.llm_client import LLMClient
            response = LLMClient().complete(system_prompt="Return JSON only.", user_prompt='Return {"ok":true}.', max_tokens=256, json_mode=True)
            checks["llm"] = {"status": "ok" if json.loads(response).get("ok") is True else "unexpected_response"}
        except Exception as exc:
            checks["llm"] = {"status": "unavailable", "error_type": type(exc).__name__}
    print(json.dumps(checks, indent=2))
    return 0 if all(value["status"] == "ok" for value in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
