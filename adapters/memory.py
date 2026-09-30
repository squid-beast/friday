"""friday · adapters/memory.py

Long-term facts: embedded Chroma (PersistentClient under CHROMA_PATH), local
ONNX embeddings. remember(fact) / recall(query) — the whole interface.
mem0 was dropped: its local embedder options need torch or an OpenAI key
(DECISIONS.md 2026-08-09). Swapping it back in = this one file.
"""

import asyncio
import hashlib
import time

import chromadb

from config.settings import get_settings

_COLLECTION = "friday_facts"
_client: chromadb.ClientAPI | None = None


def _collection() -> chromadb.Collection:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=get_settings().chroma_path)
    return _client.get_or_create_collection(_COLLECTION)


async def remember(fact: str) -> None:
    fact = fact.strip()
    if not fact:
        raise ValueError("refusing to remember an empty fact")
    await asyncio.to_thread(_remember_sync, fact)


def _remember_sync(fact: str) -> None:
    fact_id = hashlib.sha1(fact.lower().encode()).hexdigest()  # same fact twice = one entry
    # ts = when sir last said it (re-remembering refreshes it) — lets callers ask for RECENT facts
    _collection().upsert(ids=[fact_id], documents=[fact], metadatas=[{"ts": time.time()}])


async def recall(query: str, k: int = 3, *, max_age_s: float | None = None) -> list[str]:
    """Nearest facts; max_age_s keeps only facts (re)stated that recently (older facts
    from before timestamps existed are then excluded — the quiet, safe direction)."""
    return await asyncio.to_thread(_recall_sync, query, k, max_age_s)


def _recall_sync(query: str, k: int, max_age_s: float | None = None) -> list[str]:
    collection = _collection()
    n = min(k, collection.count())
    if n == 0:
        return []
    where = {"ts": {"$gte": time.time() - max_age_s}} if max_age_s else None
    result = collection.query(query_texts=[query], n_results=n,
                              **({"where": where} if where else {}))
    return result["documents"][0]
