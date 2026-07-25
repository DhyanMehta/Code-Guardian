"""Tests for RAG retriever (backend/rag/retriever.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.rag.ingest import ingest
from backend.rag.retriever import (
    CollectionEmptyError,
    CollectionNotFoundError,
    RetrievalResult,
    retrieve,
)


@pytest.fixture()
def populated_chroma(tmp_path: Path) -> str:
    """Ingest a test standards doc and return the ChromaDB persist dir."""
    standards = tmp_path / "standards"
    standards.mkdir()
    (standards / "naming.md").write_text(
        "## Naming Conventions\n\n"
        "Use snake_case for all function and method names.\n"
        "Use PascalCase for class names.\n"
        "Constants must be UPPER_SNAKE_CASE.\n\n"
        "---\n\n"
        "## Type Annotations\n\n"
        "All public functions must have complete type annotations including "
        "parameter types and return types.\n",
        encoding="utf-8",
    )
    chroma_dir = str(tmp_path / "chroma")
    ingest(standards_dir=standards, persist_dir=chroma_dir)
    return chroma_dir


@pytest.fixture()
def empty_chroma(tmp_path: Path) -> str:
    """Return a ChromaDB dir with no collection ingested."""
    d = tmp_path / "empty_chroma"
    d.mkdir()
    return str(d)


class TestRetrieverHappyPath:
    def test_returns_relevant_passages(self, populated_chroma: str) -> None:
        result = retrieve("def getUserName():", persist_dir=populated_chroma)
        assert result.has_context
        assert len(result.passages) >= 1
        assert result.error is None

    def test_passages_include_metadata(self, populated_chroma: str) -> None:
        result = retrieve("MY_CONSTANT = 42", persist_dir=populated_chroma)
        if result.has_context:
            assert result.passages[0].source_file == "naming.md"
            assert result.passages[0].chunk_id != ""
            assert result.passages[0].distance >= 0

    def test_top_k_limits_results(self, populated_chroma: str) -> None:
        result = retrieve(
            "def some_function() -> str:", persist_dir=populated_chroma, top_k=1
        )
        assert len(result.passages) <= 1


class TestRetrieverErrorHandling:
    def test_empty_query_returns_error(self, populated_chroma: str) -> None:
        result = retrieve("", persist_dir=populated_chroma)
        assert not result.has_context
        assert result.error is not None
        assert "empty" in result.error.lower() or "Empty" in result.error

    def test_whitespace_query_returns_error(self, populated_chroma: str) -> None:
        result = retrieve("   \n\t  ", persist_dir=populated_chroma)
        assert not result.has_context
        assert result.error is not None

    def test_no_collection_returns_error(self, empty_chroma: str) -> None:
        result = retrieve("def foo():", persist_dir=empty_chroma)
        assert not result.has_context
        assert result.error is not None
        assert "not found" in result.error.lower() or "ingestion" in result.error.lower()

    def test_nonexistent_dir_returns_error(self) -> None:
        result = retrieve(
            "def foo():", persist_dir="/nonexistent/chroma/path/xyz"
        )
        assert not result.has_context
        assert result.error is not None

    def test_collection_param_bypasses_client_init(self) -> None:
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "ids": [["id1"]],
            "documents": [["Use snake_case for functions."]],
            "metadatas": [[{"source_file": "test.md"}]],
            "distances": [[0.3]],
        }
        result = retrieve("def myFunc():", collection=mock_col)
        assert result.has_context
        assert result.passages[0].text == "Use snake_case for functions."
        mock_col.query.assert_called_once()

    def test_query_failure_returns_error(self) -> None:
        mock_col = MagicMock()
        mock_col.query.side_effect = RuntimeError("ChromaDB exploded")
        result = retrieve("def foo():", collection=mock_col)
        assert not result.has_context
        assert "query failed" in result.error.lower()
