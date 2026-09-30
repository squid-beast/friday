"""jarvis-life-os · client/daemon.py

v1 wake-word daemon. DORMANT: only the local wake model listens, zero
streaming. ACTIVE: console agent subprocess runs the voice pipeline. Back to
DORMANT on any of: stand-down control file (spoken kill / silence watchdog,
written by the agent), external request (hotkey / menu-bar), the trained
offline stand-down model, agent exit, or quit. The kill path needs no network.
"""

import enum
import logging
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from adapters import wakeword
from audit.log import log_event
from client import control as control_files
from config.settings import get_settings

log = logging.getLogger(__name__)


class SessionState(enum.Enum):
    DORMANT = "dormant"
    ACTIVE = "active"


def _spawn_agent() -> subprocess.Popen[bytes]:
    # stdin detached: console mode's key-listener thread would otherwise fight
    # our tty (dropped keystrokes, terminal left in raw mode).
    return subprocess.Popen(
        [sys.executable, "-m", "voice.agent", "console"], stdin=subprocess.DEVNULL
    )


def _stop(proc: subprocess.Popen[bytes]) -> None:
    proc.send_signal(signal.SIGINT)
    try:
        # 4s grace: enough for a clean close; short enough that a spoken
        # "stand down" never feels ignored (found live at the old 10s).
        proc.wait(timeout=4)
    except subprocess.TimeoutExpired:
        # The agent CLI traps SIGTERM too; a wedged teardown only yields to SIGKILL.
        proc.kill()
        proc.wait()


def _chime(sound: str = "Glass") -> None:
    try:
        subprocess.Popen(["afplay", f"/System/Library/Sounds/{sound}.aiff"])
    except OSError:  # no chime is never a reason to miss a wake (or a kill)
        log.warning("chime failed", exc_info=True)


class JarvisDaemon:
    def __init__(
        self,
        *,
        spawn=_spawn_agent,
        stop_agent=_stop,
        listen=wakeword.listen,
        kill_listen=wakeword.kill_listen,
        chime=_chime,
        audit=log_event,
        poll_s: float = 0.5,
    ) -> None:
        self._spawn = spawn
        self._stop_agent = stop_agent
        self._listen = listen
        self._kill_listen = kill_listen
        self._chime = chime
        self._audit = audit
        self._poll_s = poll_s
        self.state = SessionState.DORMANT
        self._stand_down = threading.Event()  # hotkey / menu-bar
        self._spoken_kill = threading.Event()  # offline stand-down model
        self._wake_request = threading.Event()  # menu-bar manual wake
        self._quit = threading.Event()

    # -- external controls (hotkey, menu-bar) --

    def request_stand_down(self) -> None:
        self._stand_down.set()

    def request_wake(self) -> None:
        self._wake_request.set()

    def quit(self) -> None:
        self._quit.set()

    # -- lifecycle --

    def run(self) -> None:
        self._audit_safe("daemon_start")
        while not self._quit.is_set():
            reason = self._dormant_wait()
            if reason == "quit":
                break
            self._active_session(reason)
        self._state_safe("off")  # quit: nobody is listening — say so, truthfully
        self._audit_safe("daemon_quit")

    def _dormant_wait(self) -> str:
        self.state = SessionState.DORMANT
        self._stand_down.clear()
        wake_file = control_files.wake_file()
        wake_file.unlink(missing_ok=True)  # a stale wake must never fire on its own
        self._state_safe("dormant")
        woke, stop = threading.Event(), threading.Event()
        thread = threading.Thread(
            target=self._listen_safe, args=(self._listen, woke.set, stop), daemon=True
        )
        thread.start()
        try:
            while not (woke.is_set() or self._wake_request.is_set()
                       or wake_file.exists() or self._quit.is_set()):
                time.sleep(self._poll_s)
        finally:
            stop.set()
        if self._quit.is_set():
            return "quit"
        if woke.is_set():
            return "wake_phrase"
        if wake_file.exists():
            wake_file.unlink(missing_ok=True)  # consumed, exactly once
            return "control_file"
        self._wake_request.clear()
        return "manual"

    def _active_session(self, reason: str) -> None:
        self._stand_down.clear()
        self._spoken_kill.clear()
        control = Path(get_settings().stand_down_file)
        control.unlink(missing_ok=True)  # a stale file must not kill the fresh session
        self._chime_safe("Glass")
        self._audit_safe("wake", reason)
        proc = self._spawn()
        self.state = SessionState.ACTIVE  # truthful: flips only once the agent exists
        self._state_safe("active")
        kill_stop = threading.Event()
        if self._kill_listen is not None:
            threading.Thread(
                target=self._listen_safe,
                args=(self._kill_listen, self._spoken_kill.set, kill_stop),
                daemon=True,
            ).start()
        try:
            end_reason = self._watch(proc, control)
        finally:
            kill_stop.set()
        # He must HEAR the kill land NOW — teardown below may take seconds.
        self._chime_safe("Submarine")
        if proc.poll() is None:
            self._stop_agent(proc)
        control.unlink(missing_ok=True)
        self._audit_safe("stand_down", end_reason)
        self.state = SessionState.DORMANT

    def _watch(self, proc, control: Path) -> str:
        while True:
            if self._quit.is_set() or self._stand_down.is_set():
                return "external_kill"
            if self._spoken_kill.is_set():
                return "spoken_kill"
            if control.exists():
                return "spoken_or_silence"
            if proc.poll() is not None:
                return f"agent_exit:{proc.returncode}"
            time.sleep(self._poll_s)

    # -- crash-proof wrappers: audio/audit failure must never take the daemon down --

    def _listen_safe(self, listen, on_detect, stop: threading.Event) -> None:
        try:
            listen(on_detect, stop)
        except Exception:
            log.warning("listener failed; manual wake still available", exc_info=True)

    def _chime_safe(self, sound: str = "Glass") -> None:
        try:
            self._chime(sound)
        except Exception:
            log.warning("chime failed", exc_info=True)

    def _audit_safe(self, kind: str, detail: str = "") -> None:
        try:
            self._audit(kind, detail)
        except Exception:
            log.warning("audit write failed", exc_info=True)

    def _state_safe(self, state: str) -> None:
        try:
            control_files.write_state(state)
        except Exception:  # a full disk must never take the daemon down
            log.warning("state write failed", exc_info=True)
