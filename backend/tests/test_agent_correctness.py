import json
from pathlib import Path
from dataclasses import asdict

import pytest

from backend.agents.quality_agent import QualityAgent, QualityAgentResult, QualityFinding, canonical_rule
from backend.agents.frontend_analysis import parse_sources
from backend.services.agent_coverage import Coverage, classify
from backend.services.report_builder import AgentStatus, AggregatedReport, format_pr_comment
from backend.agents.state import AgentOutcome


@pytest.mark.parametrize("alias", ["Maximum Function Length", "function_too_long", "FunctionLengthExceeded"])
@pytest.mark.parametrize("symbol,count", [("club_summary", 39), ("membership_breakdown", 42), ("event_attendance", 49), ("revenue_by_type", 35)])
def test_measurable_aliases_share_one_validator(tmp_path, alias, symbol, count):
    source = "def " + symbol + "():\n" + "    x = 1\n" * count
    file = tmp_path / "analytics.py"
    file.write_text(source)
    kind, explanation = QualityAgent._verify_supported_rule(
        {"rule_violated": alias}, "Functions should not exceed **40 lines** of logic (excluding blank lines, decorators, and the docstring).", symbol, file)
    assert kind == ("verified" if count > 40 else "contradicted")
    assert f"{count} nonblank logic lines" in explanation
    assert canonical_rule(alias) == "maximum_function_length"


def test_aliases_deduplicate():
    values = [QualityFinding("x.py", 1, rule, "detail", "high", "standard", "guide", "f", "verified")
              for rule in ["Maximum Function Length", "function_too_long", "FunctionLengthExceeded"]]
    assert len(QualityAgent._deduplicate(values, QualityAgentResult())) == 1


def test_parameter_violation_requires_real_limit_and_measurement(tmp_path):
    file = tmp_path / "params.py"
    file.write_text("def build(a, b, c, d):\n    return a\n")
    kind, detail = QualityAgent._verify_supported_rule({"rule_violated": "Parameter Count"},
        "Functions should accept 3 or fewer positional parameters.", "build", file)
    assert kind == "verified"
    assert "4 positional parameters" in detail


def test_partial_and_failed_counts_are_visible():
    for outcome in (AgentOutcome.DEGRADED, AgentOutcome.FAILED):
        report = AggregatedReport(agent_statuses=[AgentStatus("quality", outcome, 21)])
        markdown = format_pr_comment(report, pr_number=1)
        assert "| 21 |" in markdown
        assert "did not run" not in markdown
        assert "Coverage not recorded" in markdown


def test_coverage_classification_and_failure():
    coverage = classify(["app.py", "view.tsx", "generated/api.ts", "x.d.ts", "schema.json"], "quality")
    assert coverage.eligible_files == ["app.py", "view.tsx"]
    assert len(coverage.excluded_files) == 3
    coverage.analyzed(["app.py"])
    coverage.finish("failed")
    assert coverage.execution == "failed" and coverage.status == "partial"
    assert Coverage().status == "unknown"


def test_frontend_parser_handles_tsx_and_comments():
    result = parse_sources([{"file": "view.tsx", "source": "export const View = (props: {x: string}) => {\n// comment\nreturn <div>{props.x}</div>;\n};"}])[0]
    symbol = result["symbols"][0]
    assert symbol["exported"] and symbol["name"] == "View"
    assert symbol["params"] == ["props"]
    assert symbol["logic_lines"] == 1


def test_frontend_parser_rejects_invalid_source():
    with pytest.raises(ValueError, match="parser failed"):
        parse_sources([{"file": "bad.ts", "source": "export function ( {"}])


def test_original_pinned_odoo_functions(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/odooxldce_quality.json").read_text())
    counts = {"club_summary": 39, "membership_breakdown": 42, "event_attendance": 49, "revenue_by_type": 35}
    assert set(fixture["functions"]) == set(counts), "Pinned regression must exercise every audited async function"
    for symbol, source in fixture["functions"].items():
        file = tmp_path / (symbol + ".py")
        file.write_text(source)
        for alias in ["Maximum Function Length", "function_too_long", "FunctionLengthExceeded"]:
            kind, detail = QualityAgent._verify_supported_rule({"rule_violated": alias},
                "A single function should not exceed **40 lines** of logic (excluding blank lines, decorators, and the docstring).", symbol, file)
            assert kind == ("verified" if counts[symbol] > 40 else "contradicted")
            assert f"{counts[symbol]} nonblank logic lines" in detail


def test_frontend_agents_run_applicable_checks(tmp_path, monkeypatch):
    from backend.agents.frontend_analysis import extend_result
    from backend.services.agent_coverage import current
    from backend.rag.retriever import RetrievalResult, RetrievedPassage
    (tmp_path / "view.tsx").write_text('/** @param obsolete removed argument */\nexport function View(value: string) {\nconst output = <div>{value}</div>;\nreturn output;\n}\n')
    (tmp_path / "view.test.tsx").write_text("import { View as RenderView } from './view';\nRenderView('hello');")
    state = {"workspace_path": str(tmp_path), "diff": "diff --git a/view.tsx b/view.tsx\n--- a/view.tsx\n+++ b/view.tsx\n@@ -0,0 +1,4 @@\n+export function View(value: string) {\n+return <div>{value}</div>;\n+}\n"}
    monkeypatch.setattr("backend.rag.retriever.retrieve", lambda *a, **k: RetrievalResult(passages=[
        RetrievedPassage("TypeScript functions should not exceed 1 lines of logic.", "frontend.md", 0, "1")]))
    for name, result in [
        ("test_gap", {"test_gap_result": {"test_gap": {"gaps": []}}}),
        ("documentation", {"doc_result": {"documentation": {"flagged_functions": []}}}),
        ("quality", {"quality_result": {"quality": {"findings": []}}}),
    ]:
        result["agent_notes"] = {name: []}
        coverage = classify(["view.tsx"], name)
        token = current.set(coverage)
        try:
            extend_result(name, state, result)
        finally:
            current.reset(token)
        assert coverage.analyzed_files == ["view.tsx"]
        if name == "test_gap":
            assert result["test_gap_result"][name]["gaps"] == []
        elif name == "documentation":
            assert result["doc_result"][name]["flagged_functions"][0]["reason"] == "outdated"
        else:
            assert result["quality_result"][name]["findings"][0]["evidence_kind"] == "verified"


def test_checkpoint_identity_changes_with_validator(monkeypatch):
    from backend.services.agent_checkpoints import validation_fingerprint
    before = validation_fingerprint()
    read = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda p: read(p) + (b"changed semantics" if p.name == "frontend_analysis.py" else b""))
    assert validation_fingerprint() != before
