"""client/daemon.py + client/control.py — UI wake/stand-down over control files
(TDD: written before the implementation). The cockpit's ACTIVE/DORMANT toggle
rides these: a wake file wakes the dormant daemon, the existing stand_down file
ends a session, and a state file stays TRUTHFUL for the UI to display.
Stale files must never fire on their own after a crash.
"""

import time
from pathlib import Path

import pytest

from client.daemon import SessionState
from config.settings import get_settings
from tests.test_daemon_harness import Harness, wait_until


@pytest.fixture
def control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "control" / "stand_down"
    monkeypatch.setenv("STAND_DOWN_FILE", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def test_wake_file_wakes_the_dormant_daemon(control: Path) -> None:
    h = Harness(control)
    h.thread.start()
    wait_until(lambda: (control.parent / "state").exists())
    (control.parent / "wake").touch()
    wait_until(lambda: h.daemon.state is SessionState.ACTIVE)
    assert not (control.parent / "wake").exists()  # consumed, not left to re-fire
    assert ("wake", "control_file") in h.events
    h.finish()


def test_stale_wake_file_never_insta_wakes(control: Path) -> None:
    """A wake file left by a crash must be cleared at dormant entry, not obeyed."""
    control.parent.mkdir(parents=True, exist_ok=True)
    (control.parent / "wake").touch()  # stale, pre-dates the daemon
    h = Harness(control)
    h.thread.start()
    wait_until(lambda: not (control.parent / "wake").exists())
    time.sleep(0.05)  # several poll cycles
    assert h.daemon.state is SessionState.DORMANT
    assert h.spawned == []
    h.finish()


def test_state_file_is_truthful_through_the_lifecycle(control: Path) -> None:
    state = control.parent / "state"
    h = Harness(control)
    h.start_and_wake()
    assert state.read_text() == "active"  # written only once the agent exists
    control.touch()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    wait_until(lambda: state.read_text() == "dormant")
    h.finish()
    assert state.read_text() == "off"  # quit = nobody is listening; say so


def test_stand_down_gives_instant_audible_feedback(control: Path) -> None:
    """He must HEAR the kill land within one poll — the agent teardown that
    follows can take seconds, silently. (Found live: spoken stand-down worked
    but felt dead for ~10s.)"""
    h = Harness(control)
    h.start_and_wake()
    assert h.chimes == 1  # the wake chime
    control.touch()
    wait_until(lambda: h.chimes == 2)  # sleep chime BEFORE teardown completes
    h.finish()


def test_agent_teardown_grace_is_snappy() -> None:
    """SIGINT grace before SIGKILL: 4s — long enough for a clean close, short
    enough that stand-down never feels broken."""
    import inspect

    from client import daemon as daemon_mod

    assert "timeout=4" in inspect.getsource(daemon_mod._stop)


def test_control_module_roundtrip(control: Path) -> None:
    from client import control as ctl

    ctl.request_wake()
    assert (control.parent / "wake").exists()
    ctl.request_stand_down()
    assert control.exists()
    ctl.write_state("active")
    assert ctl.read_state() == "active"


def test_read_state_reports_off_when_daemon_never_ran(control: Path) -> None:
    from client import control as ctl

    assert ctl.read_state() == "off"  # missing file = honest "off", not a crash


def test_control_module_has_no_network_imports() -> None:
    """The kill-path law extends to the new IPC module."""
    import subprocess
    import sys

    code = ("import sys, client.control; "
            "banned = {'httpx', 'anthropic', 'livekit', 'deepgram', 'cartesia', "
            "'websockets', 'requests'}; "
            "loaded = banned & {m.split('.')[0] for m in sys.modules}; "
            "sys.exit(1 if loaded else 0)")
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
