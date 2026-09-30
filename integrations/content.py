"""jarvis-life-os · integrations/content.py

Content Studio: n8n pulls what's TRENDING (its credentials, its scrapers);
sir reviews here, edits the caption, and publishes to Instagram through n8n.
The Mac never holds an Instagram token; every publish is audited. Items are
deduped by id and carry a status: new -> posted | skipped.
"""

import logging
import sqlite3
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from audit.log import log_tool
from config.settings import get_settings

log = logging.getLogger(__name__)

_DB: Path | None = None
_TIMEOUT_S = 20.0
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS items ("
    "id TEXT PRIMARY KEY, ts REAL NOT NULL, title TEXT NOT NULL, "
    "hook TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', "
    "url TEXT NOT NULL DEFAULT '', score REAL NOT NULL DEFAULT 0, "
    "note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'new', "
    "caption TEXT NOT NULL DEFAULT '')"
)
STATUSES = ("new", "posted", "skipped")


def _default_db() -> Path:
    return _DB or Path(get_settings().content_db_path)


class ContentItem(BaseModel):
    id: str
    ts: float
    title: str
    hook: str = ""
    source: str = ""
    url: str = ""
    score: float = 0
    note: str = ""
    status: str = "new"
    caption: str = ""


def _connect(db: Path | None = None) -> sqlite3.Connection:
    db = db or _default_db()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def upsert(rows: list[dict], *, db: Path | None = None) -> int:
    """Insert new trending items; existing ids keep their status/caption."""
    written = 0
    conn = _connect(db)
    try:
        with conn:
            for row in rows:
                try:
                    item = ContentItem(ts=time.time(), **{
                        k: row[k] for k in
                        ("id", "title", "hook", "source", "url", "score", "note")
                        if k in row
                    })
                except Exception:
                    log.warning("malformed trending row skipped: %r", row)
                    continue
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO items "
                    "(id, ts, title, hook, source, url, score, note) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (item.id, item.ts, item.title, item.hook,
                     item.source, item.url, item.score, item.note),
                )
                written += cursor.rowcount
    finally:
        conn.close()
    return written


def items(status: str | None = "new", limit: int = 50, *, db: Path | None = None):
    query = "SELECT * FROM items"
    args: tuple = ()
    if status:
        query += " WHERE status = ?"
        args = (status,)
    query += " ORDER BY score DESC, ts DESC LIMIT ?"
    conn = _connect(db)
    try:
        rows = conn.execute(query, (*args, limit)).fetchall()
    finally:
        conn.close()
    return [ContentItem(**dict(row)) for row in rows]


def set_status(item_id: str, status: str, caption: str = "", *, db: Path | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    conn = _connect(db)
    try:
        with conn:
            changed = conn.execute(
                "UPDATE items SET status = ?, caption = ? WHERE id = ?",
                (status, caption, item_id),
            ).rowcount
    finally:
        conn.close()
    if not changed:
        raise ValueError(f"no such item: {item_id}")


def _webhook_url(path: str) -> tuple[str, str]:
    settings = get_settings()
    if not path:
        raise ValueError("content webhook not configured (docs/CONTENT-STUDIO.md)")
    if not settings.n8n_base_url or not settings.n8n_webhook_secret:
        raise ValueError("N8N_BASE_URL / N8N_WEBHOOK_SECRET not set")
    url = settings.n8n_base_url.rstrip("/") + (path if path.startswith("/") else f"/{path}")
    return url, settings.n8n_webhook_secret


async def pull(*, store=upsert) -> int:
    """Fetch trending items from n8n; returns how many NEW items landed."""
    url, secret = _webhook_url(get_settings().content_trending_webhook)
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.post(url, json={}, headers={"X-Jarvis-Secret": secret})
        response.raise_for_status()
        rows = response.json()
    return store(rows if isinstance(rows, list) else [])


async def publish(item_id: str, caption: str, *, audit=log_tool,
                  mark=set_status, db: Path | None = None) -> str:
    """Send one reviewed item to n8n for the Instagram publish. Audited, always."""
    (item,) = [i for i in items(status=None, db=db) if i.id == item_id] or [None]
    if item is None:
        raise ValueError(f"no such item: {item_id}")
    url, secret = _webhook_url(get_settings().content_publish_webhook)
    payload = {"id": item.id, "title": item.title, "url": item.url,
               "source": item.source, "caption": caption or item.hook or item.title}
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.post(url, json=payload, headers={"X-Jarvis-Secret": secret})
        response.raise_for_status()
        result = response.text[:300]
    mark(item_id, "posted", payload["caption"], db=db)
    audit("ig_publish", item_id, result, confirmed=True)
    return result
