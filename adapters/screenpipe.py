"""jarvis-life-os · adapters/screenpipe.py

Screen recall against the LOCAL screenpipe HTTP API (127.0.0.1 — nothing
leaves the machine). Defense in depth: SCREENPIPE_EXCLUDE apps are filtered
out of results here even if screenpipe records them, and the screen_off cut
flag makes search refuse outright (PermissionError).
"""

from pathlib import Path

import httpx
from pydantic import BaseModel

from config.settings import get_settings

_TIMEOUT_S = 5.0
_TEXT_CHARS = 300


class ScreenHit(BaseModel):
    text: str
    app: str
    window: str
    timestamp: str


def _excluded_apps() -> list[str]:
    raw = get_settings().screenpipe_exclude
    return [a.strip().lower() for a in raw.split(",") if a.strip()]


async def search(query: str, *, limit: int = 15) -> list[ScreenHit]:
    settings = get_settings()
    if Path(settings.screen_off_file).exists():
        raise PermissionError("screen watching is cut")
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.get(
            f"{settings.screenpipe_url}/search",
            params={"q": query, "content_type": "ocr", "limit": limit},
        )
        response.raise_for_status()
    excluded = _excluded_apps()
    hits = []
    for item in response.json().get("data", []):
        content = item.get("content") or {}
        app = str(content.get("app_name") or "")
        if any(bad in app.lower() for bad in excluded):
            continue
        text = str(content.get("text") or "").strip()
        if not text:
            continue
        hits.append(
            ScreenHit(
                text=text[:_TEXT_CHARS],
                app=app,
                window=str(content.get("window_name") or ""),
                timestamp=str(content.get("timestamp") or ""),
            )
        )
    return hits
