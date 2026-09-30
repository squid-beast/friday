"""friday · brain/pending_question.py

The last question Friday asked sir OUTSIDE the graph (the wake check-in, a
proactive nudge) — kept for 15 minutes so memory_writer stores his answer even
when it carries none of the usual fact hints. Taken once. One JSON file under
the runtime state dir; any I/O failure degrades to "no pending question".
"""

import json
import time
from pathlib import Path

from config.settings import get_settings

MAX_AGE_S = 900


def _path() -> Path:
    return Path(get_settings().pending_question_file)


def mark(question: str, *, now: float | None = None) -> None:
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"q": question.strip(), "ts": now or time.time()}))
    except OSError:
        pass  # the answer just won't get the special treatment


def take(*, now: float | None = None, max_age_s: float = MAX_AGE_S) -> str:
    path = _path()
    try:
        data = json.loads(path.read_text())
        path.unlink(missing_ok=True)
    except (OSError, ValueError):
        return ""
    fresh = (now or time.time()) - float(data.get("ts", 0)) <= max_age_s
    return str(data.get("q", "")) if fresh else ""


# --- proactive nudges: asked by notification, followed up at the NEXT wake ---

WAKE_MAX_AGE_S = 12 * 3600


def _wake_path() -> Path:
    return _path().with_name("pending_for_wake.json")


def queue_for_wake(question: str, *, now: float | None = None) -> None:
    try:
        path = _wake_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"q": question.strip(), "ts": now or time.time()}))
    except OSError:
        pass


def take_for_wake(*, now: float | None = None) -> str:
    """The latest proactive question (<12h old), consumed once; "" if none."""
    path = _wake_path()
    try:
        data = json.loads(path.read_text())
        path.unlink(missing_ok=True)
    except (OSError, ValueError):
        return ""
    fresh = (now or time.time()) - float(data.get("ts", 0)) <= WAKE_MAX_AGE_S
    return str(data.get("q", "")) if fresh else ""
