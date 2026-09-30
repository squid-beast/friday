"""friday · integrations/api_conversation.py

The dashboard's "Recent conversation" card: the last few turns of whichever
brain thread spoke most recently (Mac voice or phone), read straight from the
LangGraph SQLite checkpoint store — READ-ONLY (mode=ro), no brain boot, no LLM.
Registered into the dashboard server's GET table (jobs_api.py pattern).
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from config.settings import get_settings

_TURNS = 6
_EMPTY = {"thread": "", "messages": []}


def recent(_body: dict) -> dict:
    db = Path(get_settings().checkpoint_db_path)
    if not db.is_file():
        return _EMPTY
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2) as conn:
            row = conn.execute(
                "SELECT thread_id, type, checkpoint FROM checkpoints "
                "WHERE checkpoint_ns = '' ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return _EMPTY
    if row is None:
        return _EMPTY
    thread, kind, blob = row
    try:
        values = JsonPlusSerializer().loads_typed((kind, blob)).get("channel_values", {})
    except Exception:
        return _EMPTY
    messages = [
        {"who": "me" if m.get("role") == "user" else "friday", "text": str(m.get("content", ""))}
        for m in values.get("messages", [])[-_TURNS:]
        if isinstance(m, dict) and m.get("content")
    ]
    return {"thread": thread, "messages": messages}


GET_API = {"/api/v1/conversation/recent": recent}
POST_API: dict = {}
