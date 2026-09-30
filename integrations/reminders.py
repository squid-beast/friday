"""jarvis-life-os · integrations/reminders.py

The "remind me to ..." store — the spoken/typed reminder source for the HUD.
A tiny append-only JSON list beside the other data; no server, no creds. The
`remind` tool (tools.yaml, risk safe) captures them; pending() feeds the card.
"""

import json
import re
import time
from pathlib import Path

from config.settings import get_settings

_DB: Path | None = None
_STRIP = re.compile(r"^\s*(?:remind me to|remind me|reminder:|note to self:?)\s*",
                    re.IGNORECASE)


def _default_db() -> Path:
    return _DB or Path(get_settings().reminders_path)


def _load(db: Path) -> list[dict]:
    try:
        return json.loads(db.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def _save(db: Path, items: list[dict]) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text(json.dumps(items, indent=2))


def add(text: str, *, db: Path | None = None) -> str:
    db = db or _default_db()
    text = _STRIP.sub("", text).strip(" .")
    if not text:
        return ""
    items = _load(db)
    items.append({"text": text, "ts": time.time(), "done": False})
    _save(db, items)
    return text


def pending(*, db: Path | None = None) -> list[dict]:
    return [i for i in _load(db or _default_db()) if not i.get("done")]


async def remind(_arg: str, utterance: str) -> str:
    """tools.yaml contract: fn(arg, utterance). Stores a spoken reminder."""
    text = add(utterance)
    return f"Noted — I'll keep '{text}' on your reminders, sir." if text \
        else "What shall I remind you of, sir?"
