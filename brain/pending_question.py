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
