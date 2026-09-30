"""jarvis-life-os · tests/unit/test_memory.py

adapters/memory.py with chromadb mocked: stable ids, empty-store recall,
empty-fact refusal, vendor errors propagate (nodes translate to apologies).
"""

from unittest.mock import MagicMock, patch

import pytest

from adapters import memory


@pytest.fixture
def collection(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr(memory, "_client", None)
    col = MagicMock()
    col.count.return_value = 0
    with patch.object(memory, "chromadb") as chroma:
        chroma.PersistentClient.return_value.get_or_create_collection.return_value = col
        yield col


async def test_remember_upserts_with_stable_id(collection: MagicMock) -> None:
    await memory.remember("Sir's gym locker code is 4242")
    await memory.remember("sir's gym locker code is 4242  ")  # case/space-insensitive dedupe
    first, second = collection.upsert.call_args_list
    assert first.kwargs["ids"] == second.kwargs["ids"]
    assert first.kwargs["documents"] == ["Sir's gym locker code is 4242"]


async def test_remember_empty_fact_refused(collection: MagicMock) -> None:
    with pytest.raises(ValueError):
        await memory.remember("   ")
    collection.upsert.assert_not_called()


async def test_recall_empty_store_returns_nothing(collection: MagicMock) -> None:
    assert await memory.recall("locker code") == []
    collection.query.assert_not_called()


async def test_recall_clamps_k_to_count(collection: MagicMock) -> None:
    collection.count.return_value = 2
    collection.query.return_value = {"documents": [["fact a", "fact b"]]}
    assert await memory.recall("anything", k=5) == ["fact a", "fact b"]
    assert collection.query.call_args.kwargs["n_results"] == 2


async def test_chroma_failure_propagates(collection: MagicMock) -> None:
    collection.count.side_effect = RuntimeError("chroma store corrupted")
    with pytest.raises(RuntimeError, match="corrupted"):
        await memory.recall("anything")
