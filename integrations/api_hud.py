"""friday · integrations/api_hud.py

The HUD glance payload + automation drill-down, registered into the dashboard
server's GET/POST tables (same pattern as jobs_api.py). Every source degrades
independently — a dark corner never blanks the screen.
"""

import asyncio

from integrations import api


def hud(_body: dict) -> dict:
    """One glanceable payload for the HUD screen: vitals, weather, the combined
    Notes & Reminders feed, automations (counts + recent runs), and agent state."""
    from adapters import system
    from client import control
    from config.settings import get_settings

    s = get_settings()
    weather = {}
    try:
        weather = asyncio.run(_weather_conditions(s.weather_city))
    except Exception:
        weather = {}
    autos = {"runs": [], "counts": {}, "armed": bool(s.n8n_base_url)}
    try:
        from integrations import automations

        autos = asyncio.run(automations.recent())
    except Exception:
        pass
    return {
        "system": system.snapshot(),
        "weather": weather,
        "reminders": _reminders_feed(),
        "automations": autos,
        "daemon": control.read_state(),
        "systems": api.status({})["systems"],
    }


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


def automation_detail(body: dict) -> dict:
    """Tap-to-expand: one automation run's outcome and a data preview."""
    from integrations import automations

    return asyncio.run(automations.detail(str(body.get("id", ""))))


GET_API = {"/api/v1/hud": hud}
POST_API = {"/api/v1/automations/detail": automation_detail}
