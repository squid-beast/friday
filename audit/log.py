"""jarvis-life-os · audit/log.py

Append-only SQLite audit at data/audit.db. Phase 3 lands session events
(PLAN §5 P3: "session events -> audit"); Phase 4 adds tool executions on the
same table. The module exposes ONLY append + read — no update, no delete.
Fully local, zero network: this is the black box every investigation starts at.
"""

import json
import sqlite3
import time
from pathlib import Path

from pydantic import BaseModel

from config.settings import get_settings

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "ts REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '')"
)


class Event(BaseModel):
    ts: float
    kind: str
    detail: str


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=5)
    conn.execute(_SCHEMA)
    return conn


def _default_db() -> Path:
    return Path(get_settings().audit_db_path)


def log_event(kind: str, detail: str = "", *, db: Path | None = None) -> None:
    db = db or _default_db()
    conn = _connect(db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)",
                (time.time(), kind, detail),
            )
    finally:
        conn.close()


def events_since(since_ts: float, *, db: Path | None = None) -> list[Event]:
    db = db or _default_db()
    if not db.exists():
        return []
    conn = _connect(db)
    try:
        rows = conn.execute(
            "SELECT ts, kind, detail FROM events WHERE ts >= ? ORDER BY ts, id",
            (since_ts,),
        ).fetchall()
    finally:
        conn.close()
    return [Event(ts=ts, kind=kind, detail=detail) for ts, kind, detail in rows]


def log_tool(
    tool: str, args: str, result: str, *, confirmed: bool, db: Path | None = None
) -> None:
    """Phase 4: every tool execution, refusal, or failure — same append-only table."""
    detail = json.dumps(
        {"tool": tool, "args": args, "result": result[:200], "confirmed": confirmed}
    )
    log_event("tool", detail, db=db)


def today(*, db: Path | None = None) -> list[Event]:
    """Events since local midnight — 'what did you do today, sir?' reads this."""
    now = time.localtime()
    midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
    return events_since(midnight, db=db)
