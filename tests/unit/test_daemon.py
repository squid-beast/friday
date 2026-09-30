"""client/daemon.py — v1 state machine (TDD: kill paths written before the daemon).

Every path back to DORMANT is exercised with fakes: spoken/silence control
file, external kill (hotkey/menu-bar), spoken offline kill model, agent exit.
No network, no real audio, no real subprocesses. Harness: tests/test_daemon_harness.py.
"""

import signal
import threading
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


def test_wake_phrase_starts_session(control: Path) -> None:
    h = Harness(control)
    h.start_and_wake()
    assert h.spawned and h.chimes == 1
    assert ("wake", "wake_phrase") in h.events
    h.finish()


def test_control_file_ends_session(control: Path) -> None:
    """The spoken/silence kill: agent (or watchdog) touches the file, daemon acts."""
    h = Harness(control)
    h.start_and_wake()
    control.parent.mkdir(parents=True, exist_ok=True)
    control.touch()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    h.proc.send_signal.assert_called_with(signal.SIGINT)
    assert not control.exists()  # consumed, not left to re-trigger
    assert ("stand_down", "spoken_or_silence") in h.events
    h.finish()


def test_external_kill_ends_session(control: Path) -> None:
    """Hotkey / menu-bar path — must work with zero network."""
    h = Harness(control)
    h.start_and_wake()
    h.daemon.request_stand_down()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    h.proc.send_signal.assert_called_with(signal.SIGINT)
    assert ("stand_down", "external_kill") in h.events
    h.finish()


def test_spoken_offline_kill_model_ends_session(control: Path) -> None:
    """A trained stand-down model fires during ACTIVE -> session ends, offline."""
    heard = threading.Event()

    def kill_listen(on_detect, stop: threading.Event) -> None:
        while not stop.is_set():
            if heard.is_set():
                on_detect()
                return
            time.sleep(0.005)

    h = Harness(control, kill_listen=kill_listen)
    h.start_and_wake()
    heard.set()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    assert ("stand_down", "spoken_kill") in h.events
    h.finish()


def test_agent_exit_returns_to_dormant_without_double_kill(control: Path) -> None:
    h = Harness(control)
    h.start_and_wake()
    h.proc.poll.return_value = 0  # agent died on its own
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    h.proc.send_signal.assert_not_called()
    assert any(k == "stand_down" and "agent_exit" in d for k, d in h.events)
    h.finish()


def test_manual_wake_from_menu(control: Path) -> None:
    h = Harness(control)
    h.thread.start()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    h.daemon.request_wake()
    wait_until(lambda: h.daemon.state is SessionState.ACTIVE)
    assert ("wake", "manual") in h.events
    h.finish()


def test_stale_control_file_cleared_on_wake(control: Path) -> None:
    """A leftover file from a crash must not instantly kill the fresh session."""
    control.parent.mkdir(parents=True, exist_ok=True)
    control.touch()
    h = Harness(control)
    h.start_and_wake()
    time.sleep(0.05)
    assert h.daemon.state is SessionState.ACTIVE
    h.finish()


def test_quit_from_dormant_exits_loop(control: Path) -> None:
    h = Harness(control)
    h.thread.start()
    wait_until(lambda: h.daemon.state is SessionState.DORMANT)
    h.finish()


def test_audit_failure_never_kills_the_daemon(control: Path) -> None:
    h = Harness(control)

    def exploding_audit(kind: str, detail: str = "") -> None:
        raise OSError("disk full")

    h.daemon._audit = exploding_audit
    h.start_and_wake()  # wake path logs audit; must survive
    assert h.daemon.state is SessionState.ACTIVE
    h.finish()


# subprocess lifecycle + no-network proofs live in test_daemon_process.py
