"""friday · integrations/store.py

Metrics store: append-only SQLite at data/metrics.db. Collectors write points;
the dashboard (and later, Friday's voice) reads summaries. Boring persistence,
same shape as audit/log.py.
"""

import sqlite3
import time
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from config.settings import get_settings

_DB: Path | None = None
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS metrics ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, "
    "platform TEXT NOT NULL, metric TEXT NOT NULL, "
    "value REAL NOT NULL, note TEXT NOT NULL DEFAULT '')"
)
_DAY_S = 86_400


def _default_db() -> Path:
    return _DB or Path(get_settings().metrics_db_path)


class Point(BaseModel):
    ts: float
    platform: str
    metric: str
    value: float
    note: str = ""


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=5)
    conn.execute(_SCHEMA)
    return conn


def record(
    platform: str, metric: str, value: float, note: str = "", *, db: Path | None = None
) -> None:
    conn = _connect(db or _default_db())
    try:
        with conn:
            conn.execute(
                "INSERT INTO metrics (ts, platform, metric, value, note) VALUES (?, ?, ?, ?, ?)",
                (time.time(), platform, metric, float(value), note),
            )
    finally:
        conn.close()


def series(
    platform: str, metric: str, *, days: int = 7, db: Path | None = None
) -> list[Point]:
    db = db or _default_db()
    if not db.exists():
        return []
    conn = _connect(db)
    try:
        rows = conn.execute(
            "SELECT ts, platform, metric, value, note FROM metrics "
            "WHERE platform = ? AND metric = ? AND ts >= ? ORDER BY ts, id",
            (platform, metric, time.time() - days * _DAY_S),
        ).fetchall()
    finally:
        conn.close()
    return [Point(ts=t, platform=p, metric=m, value=v, note=n) for t, p, m, v, n in rows]


def summary(*, days: int = 7, db: Path | None = None) -> dict[str, dict[str, list[Point]]]:
    """{platform: {metric: [points, oldest->newest]}} for the dashboard."""
    db = db or _default_db()
    if not db.exists():
        return {}
    conn = _connect(db)
    try:
        rows = conn.execute(
            "SELECT ts, platform, metric, value, note FROM metrics "
            "WHERE ts >= ? ORDER BY ts, id",
            (time.time() - days * _DAY_S,),
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, dict[str, list[Point]]] = defaultdict(lambda: defaultdict(list))
    for t, p, m, v, n in rows:
        out[p][m].append(Point(ts=t, platform=p, metric=m, value=v, note=n))
    return {platform: dict(metrics) for platform, metrics in out.items()}
