"""jarvis-life-os · client/local_intents.py

OFFLINE intent matcher + capture-cut executor — zero network, zero vendor
SDKs. match() runs on every transcript BEFORE any graph/LLM dispatch
(PLAN §1.5: local overrides beat cloud). cut() executes camera/screen cuts:
control flags the adapters obey + a local pkill of screenpipe. Works with
the Wi-Fi dead, enforced by test_cuts.py.

Direction rules: capability-REDUCING intents (stand down, camera off, mute)
match by containment — firing too eagerly is the safe failure. Capability-
RESTORING intents (resume) and bare one-word kills ("dismissed") match only as
the standalone utterance, so a passing mention never re-arms or misfires.
"""

import enum
import re
import subprocess
from pathlib import Path

from config.settings import get_settings


class Intent(enum.Enum):
    STAND_DOWN = "stand_down"
    CAMERA_OFF = "camera_off"
    SCREEN_OFF = "screen_off"
    MUTE = "mute"
    RESUME = "resume"


# Priority order: the hard kill is checked first and wins inside one utterance.
_CONTAINED: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.STAND_DOWN, ("stand down", "go to sleep", "that will be all")),
    (Intent.CAMERA_OFF, ("camera off", "turn off the camera", "stop looking")),
    (Intent.SCREEN_OFF, ("stop watching my screen", "screen off", "stop screen recording")),
    (Intent.MUTE, ("mute yourself", "be quiet")),
]

_STANDALONE: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.STAND_DOWN, ("dismissed",)),
    (Intent.RESUME, ("resume", "as you were", "unmute")),
]


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def match(text: str) -> Intent | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    padded = f" {normalized} "
    for intent, phrases in _CONTAINED:
        if any(f" {phrase} " in padded for phrase in phrases):
            return intent
    for intent, phrases in _STANDALONE:
        if normalized in phrases:
            return intent
    return None


# --- capture cuts (Phase 5): flags the vision adapters obey, fully offline ---


def _touch(path_str: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def is_camera_off() -> bool:
    return Path(get_settings().camera_off_file).exists()


def is_screen_off() -> bool:
    return Path(get_settings().screen_off_file).exists()


def cut(intent: Intent) -> str:
    """Execute a capture cut; returns the spoken confirmation line."""
    settings = get_settings()
    if intent is Intent.CAMERA_OFF:
        _touch(settings.camera_off_file)
        return "Camera disabled, sir."
    if intent is Intent.SCREEN_OFF:
        _touch(settings.screen_off_file)
        # not-running is not an error; the flag alone keeps recall dark
        subprocess.run(["pkill", "-f", "screenpipe"], check=False)
        return "I've stopped watching your screen, sir."
    if intent is Intent.RESUME:
        Path(settings.camera_off_file).unlink(missing_ok=True)
        Path(settings.screen_off_file).unlink(missing_ok=True)
        return "At your service, sir."
    raise ValueError(f"not a capture cut: {intent}")  # stand-down is the daemon's job
