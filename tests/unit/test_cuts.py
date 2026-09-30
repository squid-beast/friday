"""friday · tests/unit/test_cuts.py

Capture cuts (TDD — written before the cut() executor). "camera off" and
"stop watching my screen" must flip offline flags the adapters obey, kill the
real screenpipe process, and be reversible only by an explicit resume.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import client.local_intents as li
from client.local_intents import Intent, cut, is_camera_off, is_screen_off
from config.settings import get_settings


@pytest.fixture
def flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    camera = tmp_path / "control" / "camera_off"
    screen = tmp_path / "control" / "screen_off"
    monkeypatch.setenv("CAMERA_OFF_FILE", str(camera))
    monkeypatch.setenv("SCREEN_OFF_FILE", str(screen))
    get_settings.cache_clear()
    yield camera, screen
    get_settings.cache_clear()


@pytest.fixture
def pkill(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    run = MagicMock()
    monkeypatch.setattr(li.subprocess, "run", run)
    return run


def test_camera_off_sets_flag_and_speaks(flags, pkill: MagicMock) -> None:
    camera, _ = flags
    line = cut(Intent.CAMERA_OFF)
    assert camera.exists() and is_camera_off()
    assert "amera" in line and "sir" in line
    pkill.assert_not_called()  # no camera process exists — single frames only


def test_screen_off_sets_flag_and_kills_screenpipe(flags, pkill: MagicMock) -> None:
    _, screen = flags
    line = cut(Intent.SCREEN_OFF)
    assert screen.exists() and is_screen_off()
    assert "screen" in line.lower()
    args = pkill.call_args.args[0]
    assert args[0] == "pkill" and "screenpipe" in args
    assert pkill.call_args.kwargs.get("check") is False  # not-running is not an error


def test_resume_clears_both_flags(flags, pkill: MagicMock) -> None:
    cut(Intent.CAMERA_OFF)
    cut(Intent.SCREEN_OFF)
    line = cut(Intent.RESUME)
    assert not is_camera_off() and not is_screen_off()
    assert line == "At your service, sir."


def test_flags_survive_restart_semantics(flags, pkill: MagicMock) -> None:
    """The flag is a file: a crashed agent must come back up still cut."""
    cut(Intent.CAMERA_OFF)
    get_settings.cache_clear()  # simulates a fresh process re-reading settings
    assert is_camera_off()


def test_cut_rejects_non_cut_intents(flags, pkill: MagicMock) -> None:
    with pytest.raises(ValueError):
        cut(Intent.STAND_DOWN)  # stand-down is the daemon's job, not a flag


def test_cuts_stay_offline_no_network_modules() -> None:
    """cut() must be executable with the Wi-Fi dead — no network stack imports."""
    import subprocess
    import sys

    code = (
        "import sys, client.local_intents\n"
        "banned = ('httpx', 'anthropic', 'livekit', 'deepgram', 'cartesia', 'websockets')\n"
        "hit = [m for m in sys.modules if m.split('.')[0] in banned]\n"
        "assert not hit, hit\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)
