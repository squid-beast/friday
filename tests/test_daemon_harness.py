"""friday · tests/test_daemon_harness.py

Shared daemon test rig: FridayDaemon wired to fakes (wake on demand, scripted
agent process, counted chimes, captured audit). No network, no real audio.
Used by test_daemon.py (state machine) and test_daemon_control.py (UI IPC).
"""

import signal
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from client.daemon import FridayDaemon, SessionState


def wait_until(cond, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return
        time.sleep(0.005)
    raise AssertionError("condition not reached in time")


class Harness:
    """Daemon wired to fakes: wake on demand, scripted agent process."""

    def __init__(self, control: Path, kill_listen=None) -> None:
        self.wake = threading.Event()
        self.proc = MagicMock()
        self.proc.poll.return_value = None  # agent "running"
        self.spawned: list[MagicMock] = []
        self.chimes = 0
        self.events: list[tuple[str, str]] = []

        def listen(on_detect, stop: threading.Event) -> None:
            while not stop.is_set():
                if self.wake.is_set():
                    self.wake.clear()
                    on_detect()
                    return
                time.sleep(0.005)

        def spawn():
            self.spawned.append(self.proc)
            return self.proc

        def chime(sound: str = "Glass") -> None:
            self.chimes += 1

        def audit(kind: str, detail: str = "") -> None:
            self.events.append((kind, detail))

        self.daemon = FridayDaemon(
            spawn=spawn,
            stop_agent=lambda p: p.send_signal(signal.SIGINT),
            listen=listen,
            kill_listen=kill_listen,
            chime=chime,
            audit=audit,
            poll_s=0.01,
        )
        self.thread = threading.Thread(target=self.daemon.run, daemon=True)

    def start_and_wake(self) -> None:
        self.thread.start()
        wait_until(lambda: self.daemon.state is SessionState.DORMANT)
        self.wake.set()
        wait_until(lambda: self.daemon.state is SessionState.ACTIVE)

    def finish(self) -> None:
        self.daemon.quit()
        self.thread.join(timeout=2)
        assert not self.thread.is_alive()
