"""friday · integrations/api_devices.py

Endpoints for the Mac's senses and hand-offs — Obsidian, gesture tracking,
camera snaps — registered into the dashboard server's GET/POST tables (same
pattern as jobs_api.py). Read paths never crash; bad input -> ValueError (400).
"""

import json
import time
from pathlib import Path

from config.settings import get_settings


def vault_open(body: dict) -> dict:
    """Open the vault in Obsidian — the whole thing, or one note by name. We hand
    browsing off to the real tool. Failure -> ValueError (server maps it to 400)."""
    from adapters import vault

    return {"opened": vault.open_in_obsidian(str(body.get("note", "")))}


def gesture_state(_body: dict) -> dict:
    """Latest hand-tracking state for /gesture: per-hand {chirality, gesture,
    landmarks} + whether cursor control is armed. on_air = published < 1.5s ago;
    stale/missing -> off-air. Never crashes."""
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
    try:
        files = sorted(Path(get_settings().vision_snaps_dir).glob("*.jpg"), reverse=True)
    except OSError:
        files = []
    return {"snaps": [f.stem for f in files]}


GET_API = {
    "/api/v1/vision/snaps": vision_snaps,
    "/api/v1/gesture/state": gesture_state,
}
POST_API = {
    "/api/v1/vault/open": vault_open,
    "/api/v1/gesture/control": gesture_control,
}
