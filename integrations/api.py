"""jarvis-life-os · integrations/api.py

JSON endpoints behind the app screens — plain functions the HTTP shell
(server.py) dispatches to. Each takes a parsed body dict and returns a
JSON-able dict; ValueError means a 400 with the message.
"""

import asyncio
import json
import time

from audit.log import today as audit_today
from integrations import content, store

_DAYS = 14

# Human-readable labels for the audit log — no cryptic codes in the UI.
_ACTIVITY = {
    "daemon_start": "Friday came online",
    "daemon_quit": "Friday went offline",
    "brief": "Morning brief",
    "wake": "Woke up",
    "stand_down": "Stood down",
    "camera_look": "Looked through the camera",
    "browser_task": "Used the web browser",
    "ig_publish": "Posted to Instagram",
}
_REASON = {
    "wake_phrase": "you said the wake phrase",
    "control_file": "from the app",
    "manual": "from the menu bar",
    "spoken_or_silence": "you said stand down (or it went quiet)",
    "spoken_kill": "spoken stand-down",
    "external_kill": "menu bar or hotkey",
}


def _humanize(kind: str, detail: str) -> str:
    """One friendly phrase for an audit row — plain English, no shorthand."""
    if kind == "tool":
        name, _, rest = detail.partition(": ")
        return f"Ran {name.replace('_', ' ')}" + (f" — {rest}" if rest else "")
    base = _ACTIVITY.get(kind, kind.replace("_", " ").capitalize())
    reason = _REASON.get(detail, "")
    if reason:
        return f"{base} — {reason}"
    return f"{base} — {detail}" if detail and kind not in ("brief",) else base


def summary(_body: dict) -> dict:
    return {
        platform: {
            metric: [{"ts": p.ts, "value": p.value, "note": p.note} for p in points]
            for metric, points in metrics.items()
        }
        for platform, metrics in store.summary(days=_DAYS).items()
    }


def today_view(_body: dict) -> dict:
    """Calendar + activity for the Today screen. Calendar degrades to None
    (permission chip in the UI); a broken audit read degrades to an empty list."""
    try:
        from adapters.calendar import events_today, format_event

        events = asyncio.run(events_today())
        calendar = [format_event(e) for e in events[:10]]
    except Exception:
        calendar = None
    activity = []
    try:
        for event in audit_today()[-40:]:
            detail = event.detail
            if event.kind == "tool" and event.detail:
                try:
                    tool = json.loads(event.detail)
                    detail = f"{tool.get('tool', '?')}: {tool.get('result', '')[:60]}"
                except json.JSONDecodeError:
                    pass
            activity.append({
                "ts": time.strftime("%H:%M", time.localtime(event.ts)),
                "kind": event.kind, "detail": detail,
                "label": _humanize(event.kind, detail),
            })
    except Exception:
        activity = []
    return {"calendar": calendar, "activity": activity}


def daemon_wake(_body: dict) -> dict:
    """UI 'ACTIVE': touch the wake control file; the dormant daemon starts a
    session within its 0.5s poll. File IPC — boring, offline, crash-safe."""
    from client import control

    control.request_wake()
    return {"requested": "wake", "daemon": control.read_state()}


def daemon_stand_down(_body: dict) -> dict:
    """UI 'DORMANT': touch the stand_down file the active session already obeys."""
    from client import control

    control.request_stand_down()
    return {"requested": "stand_down", "daemon": control.read_state()}


def status(_body: dict) -> dict:
    """Everything at a glance for the board: what's armed, what's queued, what's
    next. Flags read config only — no network calls, so the strip renders instantly."""
    from client import control
    from config.settings import get_settings

    s = get_settings()
    today = today_view({})
    events = today["calendar"] or []
    wake_ready = bool(s.wake_model_path)
    voice_lock_ready = wake_ready and bool(s.wake_verifier_path)
    return {
        "daemon": control.read_state(),
        "identity": {
            "assistant": s.assistant_name,
            "wake_phrase": s.wake_phrase_text,
            "wake_phrase_active": s.wake_phrase_text if wake_ready else "Hey Jarvis",
            "wake_phrase_ready": wake_ready,
            "stand_down_phrase": s.stand_down_phrase_text,
            "voice_lock": "strict" if s.wake_require_verifier else "open",
            "voice_lock_ready": voice_lock_ready,
            "voice_lock_scope": "wake-only",
        },
        "systems": {
            "brain": bool(s.anthropic_api_key),
            "voice keys": bool(s.deepgram_api_key and s.cartesia_api_key),
            "n8n ops": bool(s.n8n_base_url),
            "studio": bool(s.content_trending_webhook),
            "phone voice": bool(s.voice_ws_url),
            "pin": bool(s.jarvis_pin),
            "gate": bool(s.app_access_key),
            "voice lock": voice_lock_ready,
        },
        "queue": len(content.items()),
        "next_event": events[0] if events else None,
        "activity": today["activity"][-3:],
    }


def hud(_body: dict) -> dict:
    """One glanceable payload for the HUD screen: vitals, weather, the combined
    Notes & Reminders feed, automations (counts + recent runs), and agent state.
    Each source degrades independently — a dark corner never blanks the screen."""
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
        "systems": status({})["systems"],
    }


async def _weather_conditions(city: str) -> dict:
    if not city:
        return {}
    from adapters import weather

    return await weather.conditions(city)


def _reminders_feed() -> dict:
    """Notes & Reminders, all four sources combined and labelled."""
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


def vault_open(body: dict) -> dict:
    """Open the vault in Obsidian — the whole thing, or one note by name. We hand
    browsing off to the real tool. Failure -> ValueError (server maps it to 400)."""
    from adapters import vault

    return {"opened": vault.open_in_obsidian(str(body.get("note", "")))}


def gesture_state(_body: dict) -> dict:
    """Latest hand-tracking state for /gesture: per-hand {chirality, gesture,
    landmarks} + whether cursor control is armed. on_air = published < 1.5s ago;
    stale/missing -> off-air. Never crashes."""
    from pathlib import Path

    from config.settings import get_settings

    off = {"on_air": False, "control": False, "hands": []}
    try:
        data = json.loads(Path(get_settings().gesture_state_file).read_text())
    except (OSError, ValueError):
        return off
    if time.time() - float(data.get("ts", 0)) >= 1.5:
        return off
    return {"on_air": True, "control": bool(data.get("control")),
            "hands": data.get("hands", [])}


def gesture_control(body: dict) -> dict:
    """Arm (or disarm) cursor control (G2). {"on": true} creates the flag the agent
    watches; {"on": false} removes it. An open palm also clears it (agent-side)."""
    from pathlib import Path

    from config.settings import get_settings

    flag = Path(get_settings().gesture_control_file)
    if bool(body.get("on")):
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    return {"control": flag.exists()}


def vision_snaps(_body: dict) -> dict:
    """Recent camera snaps (newest first) for the dashboard confirmation tile.
    Each id maps to /api/v1/vision/snaps/<id>.jpg. Read-only, never crashes."""
    from pathlib import Path

    from config.settings import get_settings

    try:
        files = sorted(Path(get_settings().vision_snaps_dir).glob("*.jpg"), reverse=True)
    except OSError:
        files = []
    return {"snaps": [f.stem for f in files]}


def content_list(_body: dict) -> dict:
    return {
        "items": [item.model_dump() for item in content.items()],
        "armed": bool(content.get_settings().content_trending_webhook),
    }


def content_refresh(_body: dict) -> dict:
    pulled = asyncio.run(content.pull())
    return {"pulled": pulled, **content_list({})}


def content_publish(body: dict) -> dict:
    item_id = str(body.get("id", "")).strip()
    if not item_id:
        raise ValueError("missing item id")
    result = asyncio.run(content.publish(item_id, str(body.get("caption", ""))))
    return {"result": result, **content_list({})}


def content_skip(body: dict) -> dict:
    item_id = str(body.get("id", "")).strip()
    if not item_id:
        raise ValueError("missing item id")
    content.set_status(item_id, "skipped")
    return content_list({})


def voice_token(_body: dict) -> dict:
    """Room JWT for the phone's LiveKit connection (Phase 7.6). The tailnet is
    the transport boundary; this token scopes what a connected device may do."""
    from config.settings import get_settings

    settings = get_settings()
    if not settings.voice_ws_url or not settings.livekit_api_secret:
        raise ValueError("voice not configured (docs/PHONE.md, Phase 7.6)")
    from livekit import api as lk_api  # lazy — only the voice screen needs it

    token = (
        lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity("sir-phone")
        .with_name("Sir (phone)")
        .with_grants(lk_api.VideoGrants(
            room_join=True, room="phone", can_publish=True, can_subscribe=True,
        ))
        .to_jwt()
    )
    return {"url": settings.voice_ws_url, "token": token, "room": "phone"}
