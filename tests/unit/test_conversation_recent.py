"""friday · tests/unit/test_conversation_recent.py

GET /api/v1/conversation/recent feeds the dashboard's "Recent conversation"
card from the REAL LangGraph SQLite checkpoint format (written here by
SqliteSaver itself): newest thread wins, last 6 turns, read-only, and a missing
or empty store is an empty card — never an error.
"""

import sqlite3
from pathlib import Path

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.sqlite import SqliteSaver

from config.settings import get_settings
from integrations import api_conversation


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "checkpoint.db"
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def _write(db: Path, thread: str, messages: list[dict]) -> None:
    with sqlite3.connect(db, check_same_thread=False) as conn:
        saver = SqliteSaver(conn)
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"messages": messages}
        saver.put({"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
                  checkpoint, {}, {})


def test_missing_store_is_an_empty_card(db: Path) -> None:
    assert api_conversation.recent({}) == {"thread": "", "messages": []}


def test_newest_thread_last_six_turns(db: Path) -> None:
    _write(db, "phone", [{"role": "user", "content": "old phone turn"}])
    turns = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"t{i}"}
             for i in range(8)]
    _write(db, "console", turns)  # the Mac voice session spoke last
    out = api_conversation.recent({})
    assert out["thread"] == "console"
    assert [m["text"] for m in out["messages"]] == ["t2", "t3", "t4", "t5", "t6", "t7"]
    assert out["messages"][0]["who"] == "me" and out["messages"][1]["who"] == "friday"


def test_store_is_opened_read_only(db: Path) -> None:
    _write(db, "console", [{"role": "user", "content": "hi"}])
    before = db.stat().st_mtime_ns
    api_conversation.recent({})
    assert db.stat().st_mtime_ns == before  # the card never writes to the brain's store


def test_corrupt_store_degrades_to_empty(db: Path) -> None:
    db.write_bytes(b"not a sqlite database")
    assert api_conversation.recent({}) == {"thread": "", "messages": []}
