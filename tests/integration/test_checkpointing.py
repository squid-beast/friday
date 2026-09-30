"""friday · tests/integration/test_checkpointing.py

L2: real SQLite checkpointer + real embedded Chroma, FakeLLM. The acceptance
path 'fact told -> full restart -> recalled', by machine: a restart is a fresh
saver/client instance over the same files on disk.

First Chroma run downloads its local ONNX embedding model (~80MB, one-time).
"""

from pathlib import Path

import aiosqlite
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from adapters import memory
from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from config.settings import get_settings
from tests.fakes import FakeLLM, FakeMemory, FakeVault

THREAD = {"configurable": {"thread_id": "t1"}}


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


def _graph(saver: AsyncSqliteSaver, llm: FakeLLM):
    vault, mem = FakeVault(), FakeMemory()
    return build_graph(
        saver, think=llm.think, search=vault.search,
        recall=mem.recall, append=vault.append_inbox, remember=mem.remember,
    )


async def test_conversation_survives_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "checkpoint.db")

    conn = await aiosqlite.connect(db)
    llm = FakeLLM(["chat", "Good evening, sir.", "NONE"])
    await _graph(AsyncSqliteSaver(conn), llm).ainvoke(_turn("good evening"), THREAD)
    await drain()
    await conn.close()

    conn = await aiosqlite.connect(db)  # the "restart"
    llm = FakeLLM(["chat", "Indeed, sir.", "NONE"])
    result = await _graph(AsyncSqliteSaver(conn), llm).ainvoke(_turn("still with me?"), THREAD)
    await drain()
    await conn.close()

    assert len(result["messages"]) == 4  # both turns present
    assert "Good evening, sir." in llm.calls[1]["prompt"]  # turn 1 fed to turn 2's chat


async def test_facts_survive_restart_real_chroma(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    get_settings.cache_clear()
    try:
        monkeypatch.setattr(memory, "_client", None)
        await memory.remember("Sir's gym locker code is 4242")
        monkeypatch.setattr(memory, "_client", None)  # the "restart"
        facts = await memory.recall("what is my locker code?")
        assert any("4242" in fact for fact in facts)
    finally:
        get_settings.cache_clear()
