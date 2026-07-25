"""RAG ingestion.

Chunks and embeds the team's coding-standards documents into a ChromaDB collection.
Idempotent: re-running does not duplicate entries (stable IDs via content hash).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chromadb

from backend.config import get_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "coding_standards"
_STANDARDS_DIR = Path(__file__).resolve().parent / "standards"
_CHUNK_SEPARATOR = "\n---\n"
_MIN_CHUNK_LENGTH = 30


class IngestError(Exception):
    """Base error for ingestion failures."""


class NoSourceDocumentsError(IngestError):
    """No source markdown files found or all are empty."""


class EmbeddingError(IngestError):
    """ChromaDB embedding/storage failed."""


class ChromaConnectionError(IngestError):
    """Could not connect to / initialize ChromaDB."""


def _chunk_markdown(text: str, source_file: str) -> list[dict]:
    """Split a markdown document into sections delimited by '---' separators.

    Falls back to heading-based splitting if no separators are present.
    Returns a list of dicts with keys: id, text, metadata.
    """
    if _CHUNK_SEPARATOR in text:
        raw_chunks = text.split(_CHUNK_SEPARATOR)
    else:
        raw_chunks = _split_by_headings(text)

    chunks = []
    for chunk_text in raw_chunks:
        chunk_text = chunk_text.strip()
        if len(chunk_text) < _MIN_CHUNK_LENGTH:
            continue
        chunk_id = _stable_id(chunk_text, source_file)
        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "metadata": {"source_file": source_file},
        })
    return chunks


def _split_by_headings(text: str) -> list[str]:
    """Split markdown by ## headings, keeping the heading with its content."""
    lines = text.split("\n")
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("## ") and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current))
    return sections


def _stable_id(content: str, source_file: str) -> str:
    """Generate a deterministic ID from content + source file for idempotency."""
    basis = f"{source_file}|{content}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _load_source_documents(standards_dir: Path | None = None) -> list[tuple[str, str]]:
    """Load all .md files from the standards directory.

    Returns list of (filename, content) tuples.
    Raises NoSourceDocumentsError if no usable documents are found.
    """
    directory = standards_dir or _STANDARDS_DIR
    if not directory.is_dir():
        raise NoSourceDocumentsError(
            f"Standards directory does not exist: {directory}"
        )

    docs: list[tuple[str, str]] = []
    for md_file in sorted(directory.glob("*.md")):
        if md_file.name.upper() == "README.MD":
            continue
        content = md_file.read_text(encoding="utf-8").strip()
        if content:
            docs.append((md_file.name, content))

    if not docs:
        raise NoSourceDocumentsError(
            f"No non-empty .md files found in {directory}"
        )
    return docs


def _get_chroma_client(persist_dir: str | None = None) -> chromadb.ClientAPI:
    """Create a PersistentClient, raising ChromaConnectionError on failure."""
    resolved_dir = persist_dir or get_settings().chroma_persist_dir
    try:
        return chromadb.PersistentClient(path=resolved_dir)
    except Exception as exc:
        raise ChromaConnectionError(
            f"Failed to initialize ChromaDB at {resolved_dir}: {exc}"
        ) from exc


def ingest(
    *,
    standards_dir: Path | None = None,
    persist_dir: str | None = None,
) -> int:
    """Chunk and embed all standards documents into ChromaDB.

    Returns the total number of chunks upserted.

    Raises:
        NoSourceDocumentsError: no source .md files found or all empty.
        ChromaConnectionError: cannot connect to / initialize ChromaDB.
        EmbeddingError: ChromaDB failed to embed/store chunks.
    """
    docs = _load_source_documents(standards_dir)
    client = _get_chroma_client(persist_dir)

    try:
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
    except Exception as exc:
        raise ChromaConnectionError(
            f"Failed to get/create collection '{COLLECTION_NAME}': {exc}"
        ) from exc

    all_chunks: list[dict] = []
    for filename, content in docs:
        chunks = _chunk_markdown(content, filename)
        all_chunks.extend(chunks)
        logger.info("Chunked '%s' into %d passages.", filename, len(chunks))

    if not all_chunks:
        raise NoSourceDocumentsError("All documents chunked to zero usable passages.")

    ids = [c["id"] for c in all_chunks]
    documents = [c["text"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    except Exception as exc:
        raise EmbeddingError(
            f"ChromaDB upsert failed for {len(all_chunks)} chunks: {exc}"
        ) from exc

    logger.info(
        "Ingested %d chunks from %d documents into collection '%s'.",
        len(all_chunks),
        len(docs),
        COLLECTION_NAME,
    )
    return len(all_chunks)
