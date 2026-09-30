"""jarvis-life-os · client/killswitch.py

Menu-bar killswitch (rumps) + global hotkey (pynput): the always-available,
zero-network hard cut. The icon is TRUTHFUL — it polls the daemon's real state
every second, never assumes. Hotkey (default ⌥⌘J) is kill-only, not a toggle.

Run: uv run python -m client.killswitch
macOS will ask for Accessibility (hotkey) and Microphone permissions on first run.
"""

import threading

import rumps
from pynput import keyboard

from client.daemon import JarvisDaemon, SessionState
from config.settings import get_settings

_ICONS = {SessionState.DORMANT: "😴", SessionState.ACTIVE: "🎙"}
_KEYMAP = {
    "cmd": "<cmd>",
    "alt": "<alt>",
    "opt": "<alt>",
    "option": "<alt>",
    "ctrl": "<ctrl>",
    "shift": "<shift>",
}


def parse_hotkey(spec: str) -> str:
    """'cmd+alt+j' -> '<cmd>+<alt>+j' (pynput GlobalHotKeys syntax)."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"empty hotkey spec: {spec!r}")
    return "+".join(_KEYMAP.get(p, p) for p in parts)


class KillswitchApp(rumps.App):
    def __init__(self, daemon: JarvisDaemon, daemon_thread: threading.Thread) -> None:
        super().__init__(_ICONS[SessionState.DORMANT], quit_button=None)
        self._daemon = daemon
        self._thread = daemon_thread
        self._toggle = rumps.MenuItem("Wake", callback=self._on_toggle)
        self.menu = [self._toggle, rumps.MenuItem("Quit Jarvis", callback=self._on_quit)]
        self._shown: SessionState | None = None
        rumps.Timer(self._refresh, 1).start()

    def _refresh(self, _timer: rumps.Timer) -> None:
        state = self._daemon.state
        if state is self._shown:  # skip the NSStatusItem redraw when nothing changed
            return
        self._shown = state
        self.title = _ICONS[state]
        self._toggle.title = "Stand down" if state is SessionState.ACTIVE else "Wake"

    def _on_toggle(self, _item: rumps.MenuItem) -> None:
        if self._daemon.state is SessionState.ACTIVE:
            self._daemon.request_stand_down()
        else:
            self._daemon.request_wake()

    def _on_quit(self, _item: rumps.MenuItem) -> None:
        self._daemon.quit()
        self._thread.join(timeout=15)  # let the daemon tear the agent down — no orphaned mic
        rumps.quit_application()


def main() -> None:
    daemon = JarvisDaemon()
    thread = threading.Thread(target=daemon.run, daemon=True)
    thread.start()
    spec = get_settings().hotkey.strip()
    if spec:  # blank = hotkey OFF: skip pynput's costly global keyboard hook
        hotkey = keyboard.GlobalHotKeys({parse_hotkey(spec): daemon.request_stand_down})
        hotkey.daemon = True
        hotkey.start()
    KillswitchApp(daemon, thread).run()


if __name__ == "__main__":
    main()
