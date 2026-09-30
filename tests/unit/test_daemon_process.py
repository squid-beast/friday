"""client/daemon.py — agent subprocess lifecycle (kept from v0) + the
no-network proof: the whole kill path imports without any network stack.
State-machine tests live in test_daemon.py.
"""

import signal
import subprocess
from unittest.mock import MagicMock

import pytest

import client.daemon as daemon_mod


def test_spawn_agent_detaches_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Console mode's key-listener thread must not fight the tty."""
    popen = MagicMock()
    monkeypatch.setattr(daemon_mod.subprocess, "Popen", popen)
    daemon_mod._spawn_agent()
    assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL


def test_stop_graceful_sigint() -> None:
    proc = MagicMock()
    daemon_mod._stop(proc)
    proc.send_signal.assert_called_once_with(signal.SIGINT)
    proc.kill.assert_not_called()


def test_stop_escalates_to_kill_on_wedged_teardown() -> None:
    proc = MagicMock()
    proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="agent", timeout=10), 0]
    daemon_mod._stop(proc)  # must not raise
    proc.kill.assert_called_once()


def test_daemon_module_imports_no_network_stacks() -> None:
    """The whole kill path must exist without any network stack loaded."""
    import sys

    code = (
        "import sys, client.daemon, client.local_intents, audit.log\n"
        "banned = ('httpx', 'anthropic', 'livekit', 'deepgram', 'cartesia', 'websockets')\n"
        "hit = [m for m in sys.modules if m.split('.')[0] in banned]\n"
        "assert not hit, hit\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)


def test_listener_crash_still_allows_manual_wake(tmp_path, monkeypatch) -> None:
    """A dead mic (no permission, device gone) must not take the daemon down."""
    from config.settings import get_settings
    from tests.unit.test_daemon import Harness, SessionState, wait_until

    monkeypatch.setenv("STAND_DOWN_FILE", str(tmp_path / "stand_down"))
    get_settings.cache_clear()
    try:
        h = Harness(tmp_path / "stand_down")

        def exploding_listen(on_detect, stop) -> None:
            raise OSError("no input device")

        h.daemon._listen = exploding_listen
        h.thread.start()
        wait_until(lambda: h.daemon.state is SessionState.DORMANT)
        h.daemon.request_wake()  # the manual path survives the dead listener
        wait_until(lambda: h.daemon.state is SessionState.ACTIVE)
        h.finish()
    finally:
        get_settings.cache_clear()
