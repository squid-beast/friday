"""jarvis-life-os · client/control.py

File-based IPC between the surfaces (UI/API, menu bar) and the wake daemon.
Boring, offline, crash-safe — and under the kill-path law: ZERO network
imports (proven by test_daemon_control). Files live beside stand_down:

  data/control/wake        touched -> the dormant daemon starts a session
  data/control/stand_down  touched -> the active session ends (existing)
  data/control/state       daemon-written truth: active | dormant | off
"""

from pathlib import Path

from config.settings import get_settings


def stand_down_file() -> Path:
    return Path(get_settings().stand_down_file)


def wake_file() -> Path:
    return stand_down_file().parent / "wake"


def state_file() -> Path:
    return stand_down_file().parent / "state"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def request_wake() -> None:
    _touch(wake_file())


def request_stand_down() -> None:
    _touch(stand_down_file())


def write_state(state: str) -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state)


def read_state() -> str:
    """The daemon's last written truth; a missing file is an honest 'off'."""
    try:
        return state_file().read_text().strip() or "off"
    except OSError:
        return "off"
