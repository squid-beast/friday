"""friday · integrations/api.py

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


def _port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), 0.2):
            return True
    except OSError:
        return False


def _turn_lock_ready(s) -> bool:
    """Per-turn owner voice is ARMED only with the switch on AND model + voiceprint present."""
    from adapters.voiceprint import _abs

    return s.voice_lock_turns and all(
        _abs(p).is_file() for p in (s.voiceprint_model_path, s.voiceprint_path))


def _phone_voice_installed() -> bool:
    """`make phone-voice` installed the worker agent (on-demand group)."""
    from pathlib import Path

    return (Path.home() / "Library/LaunchAgents/com.friday.voiceworker.plist").exists()


def status(_body: dict) -> dict:
    """Everything at a glance for the board: what's armed, what's queued, what's
    next. Flags are TRUE only when the thing can actually run: n8n ops needs a
    registered Friday n8n tool (not just a URL; `make doctor` verifies it's ACTIVE);
    phone voice needs the worker installed AND LiveKit's port."""
    from client import control
    from config.settings import get_settings
    from config.tools import load_tools

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
            "voice_lock_scope": "every turn" if _turn_lock_ready(s) else "wake-only",
        },
        "systems": {
            "brain": bool(s.anthropic_api_key),
            "voice keys": bool(s.deepgram_api_key and s.cartesia_api_key),
            "n8n ops": bool(s.n8n_base_url) and any(t.webhook_path for t in load_tools()),
            "phone voice": bool(s.voice_ws_url) and _phone_voice_installed()
            and _port_open(7880),
            "pin": bool(s.friday_pin),
            "gate": bool(s.app_access_key),
            "voice lock": voice_lock_ready,
        },
        "queue": len(content.items()),
        "next_event": events[0] if events else None,
        "activity": today["activity"][-3:],
    }


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
