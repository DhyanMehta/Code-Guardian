"""Measure which deterministic query shape actually retrieves the length rule.

The relevance cutoff (1.5) and top_k (5) stay untouched; only the query text varies.
Prints the distance of every chunk for each variant so the choice is evidence-based.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)

import chromadb  # noqa: E402

from backend.agents.quality_agent import QualityAgent  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.rag.ingest import COLLECTION_NAME  # noqa: E402
from backend.tools.workspace import checkout_pr  # noqa: E402

state = json.loads((Path(__file__).parent / "e2e_target.json").read_text(encoding="utf-8"))
settings = get_settings()
token = settings.require("github_token")

client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
collection = client.get_collection(name=COLLECTION_NAME)

print("=== chunks in the collection ===")
everything = collection.get()
for cid, doc in zip(everything["ids"], everything["documents"]):
    head = doc.strip().splitlines()[0]
    print(f"  {cid}  {len(doc):5d} chars  {head}")
print()


def is_length_chunk(text: str) -> bool:
    return "40 lines" in text or "Function Length" in text


with checkout_pr(state["repo_full_name"], state["head_sha"], token) as ws:
    diff = subprocess.run(
        ["git", "diff", "HEAD~1"], cwd=ws.path, capture_output=True, text=True, timeout=30
    ).stdout
    changed = [state["file_path"]]
    agent = QualityAgent()
    facts = agent._structural_facts(changed, ws.path)
    files_line = "Files changed: " + ", ".join(changed)

    variants = {
        "A facts only": facts,
        "B facts + files": "\n".join([facts, files_line]),
        "C facts + files + diff400": "\n".join([facts, files_line, diff[:400]]),
        "D facts + files + diff800 (current)": "\n".join([facts, files_line, diff[:800]]),
        "E facts + files + diff3000": "\n".join([facts, files_line, diff[:3000]]),
        "F diff only 3000 (original)": "\n".join([files_line, diff[:3000]]),
    }

    for name, query in variants.items():
        res = collection.query(query_texts=[query], n_results=5)
        docs = res["documents"][0]
        dists = res["distances"][0]
        print(f"--- {name}  ({len(query)} chars) ---")
        best_length = None
        for doc, dist in zip(docs, dists):
            head = doc.strip().splitlines()[0]
            marker = "  <== LENGTH RULE" if is_length_chunk(doc) else ""
            passes = "keep" if dist <= 1.5 else "CUT "
            print(f"    {passes} distance={dist:.3f}  {head}{marker}")
            if is_length_chunk(doc):
                best_length = dist
        if best_length is None:
            print("    length rule: not in top 5 at all")
        else:
            print(f"    length rule distance={best_length:.3f} "
                  f"({'RETRIEVED' if best_length <= 1.5 else 'cut by threshold'})")
        print()
