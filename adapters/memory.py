"""jarvis-life-os · adapters/memory.py

Long-term facts: embedded Chroma (PersistentClient under CHROMA_PATH), local
ONNX embeddings. remember(fact) / recall(query) — the whole interface.
mem0 was dropped: its local embedder options need torch or an OpenAI key
(DECISIONS.md 2026-08-09). Swapping it back in = this one file.
"""

import asyncio
import hashlib

import chromadb

from config.settings import get_settings

_COLLECTION = "jarvis_facts"
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
    _collection().upsert(ids=[fact_id], documents=[fact])


async def recall(query: str, k: int = 3) -> list[str]:
    return await asyncio.to_thread(_recall_sync, query, k)


def _recall_sync(query: str, k: int) -> list[str]:
    collection = _collection()
    n = min(k, collection.count())
    if n == 0:
        return []
    result = collection.query(query_texts=[query], n_results=n)
    return result["documents"][0]
