"""Tests for RAG ingestion (backend/rag/ingest.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.rag.ingest import (
    ChromaConnectionError,
    EmbeddingError,
    NoSourceDocumentsError,
    _chunk_markdown,
    _stable_id,
    ingest,
)


@pytest.fixture()
def standards_dir(tmp_path: Path) -> Path:
    """Create a temporary standards directory with a sample markdown file."""
    doc = tmp_path / "test_standard.md"
    doc.write_text(
        "# Test Standard\n\n"
        "## Rule A\n\n"
        "Use snake_case for functions.\n\n"
        "---\n\n"
        "## Rule B\n\n"
        "Classes must use PascalCase naming.\n\n"
        "---\n\n"
        "## Rule C\n\n"
        "All public functions require type annotations.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def empty_standards_dir(tmp_path: Path) -> Path:
    """Create a standards directory with no .md files."""
    return tmp_path


@pytest.fixture()
def chroma_dir(tmp_path: Path) -> str:
    """Return a temp directory for ChromaDB persistence."""
    d = tmp_path / "chroma_test"
    d.mkdir()
    return str(d)


class TestChunking:
    def test_splits_on_separator(self) -> None:
        text = (
            "Section A has enough content to pass the minimum length threshold easily\n"
            "---\n"
            "Section B also has enough content to pass the minimum length threshold here"
        )
        chunks = _chunk_markdown(text, "test.md")
        assert len(chunks) == 2
        assert "Section A" in chunks[0]["text"]
        assert "Section B" in chunks[1]["text"]

    def test_splits_on_headings_when_no_separator(self) -> None:
        text = (
            "# Title\n\nIntro text that is long enough to pass.\n\n"
            "## Section One\n\nContent for section one is here.\n\n"
            "## Section Two\n\nContent for section two is here.\n"
        )
        chunks = _chunk_markdown(text, "test.md")
        assert len(chunks) >= 2

    def test_skips_short_chunks(self) -> None:
        text = "Short\n---\nAlso short\n---\nThis is a long enough chunk to pass the minimum length."
        chunks = _chunk_markdown(text, "test.md")
        assert len(chunks) == 1
        assert "long enough" in chunks[0]["text"]

    def test_stable_ids_are_deterministic(self) -> None:
        id1 = _stable_id("hello world", "file.md")
        id2 = _stable_id("hello world", "file.md")
        id3 = _stable_id("different content", "file.md")
        assert id1 == id2
        assert id1 != id3

    def test_chunk_metadata_includes_source(self) -> None:
        text = "A chunk of content that is definitely long enough to pass."
        chunks = _chunk_markdown(text, "my_standards.md")
        assert chunks[0]["metadata"]["source_file"] == "my_standards.md"


class TestIngest:
    def test_ingest_happy_path(self, standards_dir: Path, chroma_dir: str) -> None:
        count = ingest(standards_dir=standards_dir, persist_dir=chroma_dir)
        assert count >= 3  # 3 sections separated by ---

    def test_ingest_is_idempotent(self, standards_dir: Path, chroma_dir: str) -> None:
        count1 = ingest(standards_dir=standards_dir, persist_dir=chroma_dir)
        count2 = ingest(standards_dir=standards_dir, persist_dir=chroma_dir)
        assert count1 == count2

        import chromadb
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_collection("coding_standards")
        assert collection.count() == count1

    def test_ingest_no_source_docs_raises(
        self, empty_standards_dir: Path, chroma_dir: str
    ) -> None:
        with pytest.raises(NoSourceDocumentsError):
            ingest(standards_dir=empty_standards_dir, persist_dir=chroma_dir)

    def test_ingest_missing_directory_raises(self, chroma_dir: str) -> None:
        with pytest.raises(NoSourceDocumentsError):
            ingest(
                standards_dir=Path("/nonexistent/path/that/does/not/exist"),
                persist_dir=chroma_dir,
            )

    def test_ingest_empty_files_only_raises(
        self, tmp_path: Path, chroma_dir: str
    ) -> None:
        (tmp_path / "empty.md").write_text("", encoding="utf-8")
        with pytest.raises(NoSourceDocumentsError):
            ingest(standards_dir=tmp_path, persist_dir=chroma_dir)

    def test_ingest_skips_readme(
        self, tmp_path: Path, chroma_dir: str
    ) -> None:
        (tmp_path / "README.md").write_text("This is a readme, not a standard.", encoding="utf-8")
        (tmp_path / "real_standard.md").write_text(
            "## Real Rule\n\nUse type annotations on all public functions always.\n",
            encoding="utf-8",
        )
        count = ingest(standards_dir=tmp_path, persist_dir=chroma_dir)
        assert count >= 1
