"""friday · integrations/api_hud.py

The HUD glance payload, registered into the dashboard server's GET table (same
pattern as jobs_api.py). Every source degrades independently — a dark corner
never blanks the screen. The UI polls every 6s, so the network-bound sources
(weather, n8n) are memoized for a minute.
"""

import asyncio
import time

_TTL_S = 60.0
_memo: dict[str, tuple[float, dict]] = {}  # ponytail: module dict, one process, one HUD


def _cached(key: str, fetch) -> dict:
    hit = _memo.get(key)
    if hit and time.monotonic() - hit[0] < _TTL_S:
        return hit[1]
    value = fetch()
    _memo[key] = (time.monotonic(), value)
    return value


def hud(_body: dict) -> dict:
    """One glanceable payload for the HUD screen: vitals, weather, the combined
    Notes & Reminders feed, automations (counts + recent runs), and agent state."""
    from adapters import system
    from client import control
    from config.settings import get_settings

    s = get_settings()
    try:
        weather = _cached("weather", lambda: asyncio.run(_weather_conditions(s.weather_city)))
    except Exception:
        weather = {}
    try:
        from integrations import automations

        autos = _cached("automations", lambda: asyncio.run(automations.recent()))
    except Exception:
        autos = {"runs": [], "counts": {}, "armed": bool(s.n8n_base_url),
                 "error": "automations read failed"}
    return {
        "system": system.snapshot(),
        "weather": weather,
        "reminders": _reminders_feed(),
        "automations": autos,
        "daemon": control.read_state(),
        "eyes": _eyes_up(),  # truthful Snaps card: is any vision model listening?
    }


def _eyes_up() -> bool:
    try:
        from adapters.camera import _eyes_up as probe

        return probe()
    except Exception:
        return False


async def _weather_conditions(city: str) -> dict:
    if not city:
        return {}
    from adapters import weather

    return await weather.conditions(city)


def _reminders_feed() -> dict:
    """Notes & Reminders, all sources combined and labelled."""
    from integrations import reminders

    items = [{"text": r["text"], "source": "you"} for r in reminders.pending()]
    try:
        from adapters.calendar import events_today, format_event

        items += [{"text": format_event(e), "source": "calendar"}
                  for e in asyncio.run(events_today())[:6]]
    except Exception:
        pass
    notes = []
    try:
        from adapters import vault

        notes = vault.recent()
    except Exception:
        notes = []
    return {"items": items[:12], "notes": notes}


GET_API = {"/api/v1/hud": hud}
POST_API: dict = {}
