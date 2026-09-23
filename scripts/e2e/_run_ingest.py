"""Populate the coding_standards ChromaDB collection in the CONFIGURED persist dir.

The Quality Agent degraded to zero findings during the E2E run because the
collection did not exist at the path `CHROMA_PERSIST_DIR` resolves to.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from backend.config import get_settings  # noqa: E402
from backend.rag.ingest import COLLECTION_NAME, ingest  # noqa: E402
from backend.rag.retriever import retrieve  # noqa: E402

settings = get_settings()
print(f"CHROMA_PERSIST_DIR = {settings.chroma_persist_dir}")
print(f"resolved           = {Path(settings.chroma_persist_dir).resolve()}\n")

count = ingest()
print(f"\nupserted {count} chunk(s) into collection '{COLLECTION_NAME}'\n")

result = retrieve("maximum function length complexity nesting depth naming conventions")
print(f"retrieval check: has_context={result.has_context} "
      f"passages={len(result.passages)} error={result.error}")
for i, p in enumerate(result.passages):
    print(f"  [{i}] {p.source_file}: {p.text[:140]!r}")
