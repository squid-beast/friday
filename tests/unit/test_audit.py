"""friday · tests/unit/test_audit.py

audit/log.py: append + read roundtrip, ordering, since-filter, missing db.
"""

import time
from pathlib import Path

from audit.log import events_since, log_event, today


def test_append_and_read_roundtrip_in_order(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    log_event("wake", db=db)
    log_event("stand_down", "hotkey", db=db)
    events = events_since(0, db=db)
    assert [(e.kind, e.detail) for e in events] == [("wake", ""), ("stand_down", "hotkey")]
    assert events[0].ts <= events[1].ts


def test_events_since_filters(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    log_event("old", db=db)
    cutoff = time.time()
    log_event("new", db=db)
    assert [e.kind for e in events_since(cutoff, db=db)] == ["new"]


def test_missing_db_reads_empty(tmp_path: Path) -> None:
    assert events_since(0, db=tmp_path / "nope.db") == []


def test_today_covers_recent_events(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    log_event("wake", db=db)
    assert [e.kind for e in today(db=db)] == ["wake"]


def test_db_file_created_under_parent_dirs(tmp_path: Path) -> None:
    db = tmp_path / "deep" / "nested" / "audit.db"
    log_event("wake", db=db)
    assert db.exists()


def test_log_tool_roundtrip(tmp_path: Path) -> None:
    import json

    from audit.log import log_tool

    db = tmp_path / "audit.db"
    log_tool("content_pipeline", "/webhook/content", "started " + "x" * 500, confirmed=True, db=db)
    (event,) = events_since(0, db=db)
    assert event.kind == "tool"
    payload = json.loads(event.detail)
    assert payload["tool"] == "content_pipeline"
    assert payload["confirmed"] is True
    assert len(payload["result"]) <= 200  # truncated, the log is a black box not a dump
