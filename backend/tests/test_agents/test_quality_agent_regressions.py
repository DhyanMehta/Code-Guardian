"""Regression tests for Quality Agent root-cause fixes.

Covers:
1. test_rag_function_length_retrieval
2. test_groq_rate_limit_delay_extraction
3. test_chromadb_path_invariance
4. test_module_reanchoring_word_collision
5. test_module_reanchoring_valid_symbol
6. test_gate_6_constant_naming
7. test_gate_3_git_b_prefix
8. test_overlong_function_real_pipeline
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents._validation import (
    SymbolInfo,
    collect_defined_symbols,
    validate_naming_convention,
)
from backend.agents.quality_agent import QualityAgent
from backend.agents.state import AgentOutcome
from backend.config import Settings, get_settings
from backend.rag.retriever import _get_collection, retrieve
from backend.tools.llm_client import _extract_retry_delay


def test_rag_function_length_retrieval() -> None:
    """Query representative structural facts and verify Function Length is retrieved."""
    query = (
        "Python coding standards function length complexity naming conventions "
        "type annotations docstrings"
    )
    result = retrieve(query)
    assert result.has_context
    assert any("Function Length" in p.text for p in result.passages), (
        "Function Length & Complexity standard was not retrieved by query"
    )

    # Also test realistic AST-derived facts from a 52-line function
    structural_query = (
        "Structure of the changed code (measured):\n"
        "sample.py defines 1 function(s) and 0 class(es).\n"
        "function process_large_dataset in sample.py is 52 lines long"
    )
    result_facts = retrieve(structural_query)
    assert result_facts.has_context
    assert any("Function Length" in p.text for p in result_facts.passages), (
        "Function Length & Complexity standard was not retrieved for 52-line facts query"
    )


def test_groq_rate_limit_delay_extraction() -> None:
    """Extract retry delay from both Groq error formats."""
    # Format 1: Groq live API format
    msg1 = (
        "Rate limit reached for model `openai/gpt-oss-20b` in organization `org_xxx` "
        "on tokens per minute (TPM). Please try again in 18.62s."
    )
    delay1 = _extract_retry_delay(msg1)
    assert delay1 == 18.62

    # Format 2: Standard retry in format
    msg2 = "rate limited: retry in 4.5s"
    delay2 = _extract_retry_delay(msg2)
    assert delay2 == 4.5

    # Format 3: No delay specified
    msg3 = "rate limit reached, no retry header provided"
    assert _extract_retry_delay(msg3) is None


def test_chromadb_path_invariance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ChromaDB persist_dir resolves to the same intended directory regardless of CWD."""
    settings = Settings()
    persist_path = Path(settings.chroma_persist_dir)
    assert persist_path.is_absolute(), f"chroma_persist_dir is not absolute: {persist_path}"
    assert persist_path == Path(get_settings().chroma_persist_dir)
    assert persist_path.is_dir(), f"chroma_persist_dir does not exist: {persist_path}"

    # Verify collection can be opened regardless of cwd
    collection = _get_collection(persist_dir=str(persist_path))
    assert collection.count() >= 4


def test_module_reanchoring_word_collision(tmp_path: Path) -> None:
    """AST contains variable 'line'; explanation has 'line'; symbol remains '<module>'."""
    src = tmp_path / "sample.py"
    src.write_text("line = 1\n", encoding="utf-8")

    table = collect_defined_symbols(str(src))
    assert table is not None
    assert "line" in table

    # 'line' is a variable and a common prose word; should NOT be re-anchored
    explanation = "Function exceeds maximum line count"
    reanchored = QualityAgent._first_symbol_mentioned(explanation, table)
    assert reanchored is None, f"Incorrectly re-anchored to variable {reanchored!r}"


def test_module_reanchoring_valid_symbol(tmp_path: Path) -> None:
    """Legitimate function or class mentions should still be anchored correctly."""
    src = tmp_path / "sample.py"
    src.write_text(
        "def process_data(records):\n"
        "    return len(records)\n\n"
        "class ReportBuilder:\n"
        "    pass\n",
        encoding="utf-8",
    )
    table = collect_defined_symbols(str(src))
    assert table is not None

    # Qualified mention
    res1 = QualityAgent._first_symbol_mentioned(
        "The function process_data is too long", table
    )
    assert res1 == "process_data"

    # Backtick-quoted mention
    res2 = QualityAgent._first_symbol_mentioned(
        "Definition `process_data` exceeds allowed complexity", table
    )
    assert res2 == "process_data"

    # Class mention
    res3 = QualityAgent._first_symbol_mentioned(
        "The class ReportBuilder lacks docstrings", table
    )
    assert res3 == "ReportBuilder"


def test_gate_6_constant_naming() -> None:
    """Test Gate 6 naming validation for constants, functions, classes, and variables."""
    # 1. Valid UPPER_SNAKE_CASE constant -> passes validation (not rejected)
    const_info = SymbolInfo(name="MAX_RETRIES", kind="constant", start_line=1, end_line=1)
    violates, reason = validate_naming_convention(
        "MAX_RETRIES", const_info, "Constant MAX_RETRIES naming"
    )
    assert not violates
    assert "UPPER_SNAKE_CASE" in reason

    # 2. Invalid lowercase constant -> flagged as naming violation
    invalid_const = SymbolInfo(name="max_retries", kind="constant", start_line=1, end_line=1)
    violates, reason = validate_naming_convention(
        "max_retries", invalid_const, "Constant max_retries should be UPPER_SNAKE_CASE"
    )
    assert violates

    # 3. Valid snake_case function -> passes validation
    func_info = SymbolInfo(name="calculate_total", kind="function", start_line=1, end_line=5)
    violates, reason = validate_naming_convention("calculate_total", func_info)
    assert not violates
    assert "snake_case" in reason

    # 4. Valid snake_case variable -> passes validation
    var_info = SymbolInfo(name="item_count", kind="variable", start_line=1, end_line=1)
    violates, reason = validate_naming_convention("item_count", var_info)
    assert not violates
    assert "snake_case" in reason

    # 5. Valid PascalCase class -> passes validation
    class_info = SymbolInfo(name="InvoiceProcessor", kind="class", start_line=1, end_line=10)
    violates, reason = validate_naming_convention("InvoiceProcessor", class_info)
    assert not violates
    assert "PascalCase" in reason


def test_gate_3_git_b_prefix() -> None:
    """Verify b/ path prefix is normalized and unrelated files are still rejected."""
    # Prefix normalization
    assert QualityAgent._normalize_path("b/utils.py") == "utils.py"
    assert QualityAgent._normalize_path("a/utils.py") == "utils.py"
    assert QualityAgent._normalize_path("b/backend/utils.py") == "backend/utils.py"
    assert QualityAgent._normalize_path("utils.py") == "utils.py"

    # Gate 3 integration check
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "utils.py"
        src.write_text("def helper(): pass\n", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps({
            "findings": [
                {
                    "passage_index": 0,
                    "file_path": "b/utils.py",
                    "symbol": "helper",
                    "line": 1,
                    "rule_violated": "Test Rule",
                    "explanation": "test explanation",
                    "severity": "low",
                },
                {
                    "passage_index": 0,
                    "file_path": "b/unrelated.py",
                    "symbol": "other",
                    "line": 1,
                    "rule_violated": "Test Rule",
                    "explanation": "unrelated file",
                    "severity": "low",
                },
            ]
        })
        agent = QualityAgent(llm_client=mock_llm)
        diff = "--- a/utils.py\n+++ b/utils.py\n@@ -0,0 +1,1 @@\n+def helper(): pass\n"
        result = agent.run(diff, ["utils.py"], tmpdir)

        # b/utils.py accepted, b/unrelated.py rejected
        assert len(result.findings) == 1
        assert result.findings[0].file_path == "utils.py"
        assert any("outside the PR" in note for note in result.notes)


def test_overlong_function_real_pipeline(tmp_path: Path) -> None:
    """Verify real pipeline on a 52-line function / 40-line standard."""
    func_lines = ["def process_large_dataset(records):"]
    func_lines.extend(f"    x_{i} = {i} * 2" for i in range(50))
    func_lines.append("    return x_49\n")
    code = "\n".join(func_lines)

    src = tmp_path / "sample.py"
    src.write_text(code, encoding="utf-8")

    diff = (
        "--- a/sample.py\n+++ b/sample.py\n@@ -0,0 +1,52 @@\n"
        + "".join(f"+{line}\n" for line in code.splitlines())
    )

    # 1. Verify RAG retrieval directly on agent's query
    agent = QualityAgent()
    query = agent._build_retrieval_query(diff, ["sample.py"], str(tmp_path))
    retrieval = retrieve(query)
    assert retrieval.has_context

    # Identify the passage index for Function Length
    length_idx = None
    for i, p in enumerate(retrieval.passages):
        if "Function Length" in p.text:
            length_idx = i
            break
    assert length_idx is not None, "Function Length passage not retrieved by RAG"

    # 2. Run agent with mocked LLM returning a valid finding referencing that passage
    mock_llm = MagicMock()
    mock_llm.complete.return_value = json.dumps({
        "findings": [
            {
                "passage_index": length_idx,
                "file_path": "b/sample.py",
                "symbol": "process_large_dataset",
                "line": 1,
                "rule_violated": "Maximum Function Length",
                "explanation": (
                    "function process_large_dataset is 52 lines long, exceeding the 40-line limit"
                ),
                "severity": "high",
            }
        ]
    })
    agent_with_llm = QualityAgent(llm_client=mock_llm)
    result = agent_with_llm.run(diff, ["sample.py"], str(tmp_path))

    assert result.outcome == AgentOutcome.OK
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.symbol == "process_large_dataset"
    assert finding.file_path == "sample.py"
    assert finding.line == 1
    assert finding.rule_violated == "Maximum Function Length"
