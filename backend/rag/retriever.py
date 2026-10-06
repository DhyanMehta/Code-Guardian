"""RAG retriever.

Queries the ChromaDB coding-standards collection for passages relevant to a given
code snippet or diff context. Returns typed results with explicit handling for
empty/unreachable ChromaDB states.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import chromadb

from backend.config import get_settings
from backend.rag.ingest import COLLECTION_NAME, ChromaConnectionError, resolve_active_collection

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
_MIN_RELEVANCE_SCORE = 1.65  # ChromaDB L2 distance; lower = more similar


class RetrieverError(Exception):
    """Base error for retriever failures."""


class CollectionEmptyError(RetrieverError):
    """The standards collection exists but contains no documents."""


class CollectionNotFoundError(RetrieverError):
    """The standards collection does not exist (ingestion not run)."""


@dataclass
class RetrievedPassage:
    """A single retrieved standards passage with its relevance metadata."""

    text: str
    source_file: str
    distance: float
    chunk_id: str


@dataclass
class RetrievalResult:
    """Outcome of a retrieval query."""

    passages: list[RetrievedPassage] = field(default_factory=list)
    query_text: str = ""
    error: str | None = None

    @property
    def has_context(self) -> bool:
        return len(self.passages) > 0


def _get_collection(
    persist_dir: str | None = None,
    installation_id: int | None = None,
    collection_name: str | None = None,
) -> chromadb.Collection:
    """Open the standards collection.

    If *installation_id* is provided and a custom collection exists with documents,
    returns that collection. Otherwise falls back to the default collection.

    Raises:
        ChromaConnectionError: cannot initialize ChromaDB client.
        CollectionNotFoundError: collection doesn't exist.
        CollectionEmptyError: collection has zero documents.
    """
    resolved_dir = persist_dir or get_settings().chroma_persist_dir
    try:
        client = chromadb.PersistentClient(path=resolved_dir)
    except Exception as exc:
        raise ChromaConnectionError(
            f"Failed to connect to ChromaDB at {resolved_dir}: {exc}"
        ) from exc

    if collection_name:
        try:
            col = client.get_collection(name=collection_name)
            if not col.count():
                raise CollectionEmptyError("Selected standards version is empty.")
            return col
        except CollectionEmptyError:
            raise
        except Exception as exc:
            raise CollectionNotFoundError("Selected standards version is unavailable.") from exc
    if installation_id is not None:
        custom_name = f"coding_standards_{installation_id}"
        try:
            custom_col = client.get_collection(name=custom_name)
            if custom_col.count() > 0:
                return custom_col
            logger.info("Custom collection '%s' is empty; falling back to default.", custom_name)
        except Exception as exc:
            from chromadb.errors import NotFoundError
            if not isinstance(exc, NotFoundError):
                raise ChromaConnectionError("Custom standards could not be read.") from exc

    try:
        collection = client.get_collection(name=resolve_active_collection(resolved_dir))
    except Exception as exc:
        raise CollectionNotFoundError(
            f"Collection '{COLLECTION_NAME}' not found. Run ingestion first. "
            f"Error: {exc}"
        ) from exc

    if collection.count() == 0:
        raise CollectionEmptyError(
            f"Collection '{COLLECTION_NAME}' exists but is empty. "
            "Re-run ingestion with valid standards documents."
        )
    return collection


def retrieve(
    query_text: str,
    *,
    top_k: int | None = None,
    persist_dir: str | None = None,
    collection: chromadb.Collection | None = None,
    installation_id: int | None = None,
    collection_name: str | None = None,
) -> RetrievalResult:
    """Query ChromaDB for standards passages relevant to the given code/diff context.

    Args:
        query_text: the code snippet or diff text to find relevant standards for.
        top_k: number of results to return (default: DEFAULT_TOP_K).
        persist_dir: override for ChromaDB persistence directory.
        collection: pre-built collection (for testing); skips client init if provided.
        installation_id: optional GitHub App installation ID to query custom standards.

    Returns:
        RetrievalResult with passages on success, or with error string on failure.
        Never raises — errors are captured in the result for the agent to handle.
    """
    k = top_k if top_k is not None else DEFAULT_TOP_K
    result = RetrievalResult(query_text=query_text)

    if not query_text.strip():
        result.error = "Empty query text; cannot retrieve relevant standards."
        return result

    try:
        col = collection or _get_collection(persist_dir, installation_id=installation_id, collection_name=collection_name)
    except (ChromaConnectionError, CollectionNotFoundError, CollectionEmptyError) as exc:
        result.error = str(exc)
        logger.warning("Retriever could not access collection: %s", exc)
        return result

    try:
        query_result = col.query(query_texts=[query_text], n_results=k)
    except Exception as exc:
        result.error = f"ChromaDB query failed: {exc}"
        logger.warning("ChromaDB query failed: %s", exc)
        return result

    ids = query_result.get("ids", [[]])[0]
    documents = query_result.get("documents", [[]])[0]
    metadatas = query_result.get("metadatas", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    for i, doc_text in enumerate(documents):
        distance = distances[i] if i < len(distances) else 999.0
        if distance > _MIN_RELEVANCE_SCORE:
            continue
        metadata = metadatas[i] if i < len(metadatas) else {}
        result.passages.append(
            RetrievedPassage(
                text=doc_text,
                source_file=(metadata or {}).get("source_file", "unknown"),
                distance=distance,
                chunk_id=ids[i] if i < len(ids) else "",
            )
        )

    if not result.passages:
        result.error = (
            "No sufficiently relevant standards passages found for the given context."
        )
    return result
