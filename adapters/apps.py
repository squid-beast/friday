"""friday · adapters/apps.py

The wake launch: open sir's apps + tabs (Spotify, then Chrome with his
configured URLs including the Friday cockpit). macOS `open` only — a subprocess,
no network. On wake (voice/agent.py) ONLY while WAKE_APPS_ENABLED is on; the
`open_apps` tool ("open my apps") always works — the wake switch never disarms
the command. Each `open` is checked and logged, so a missing app or wrong name
surfaces instead of silently no-opping.
"""

import logging
import subprocess

from config.settings import get_settings

log = logging.getLogger(__name__)


def _urls(raw: str) -> list[str]:
    return [u.strip() for u in raw.split(",") if u.strip()]


def _open(run, args: list[str], label: str, launched: list[str]) -> None:
    """Run one `open`, record it on success, log (never raise) on failure."""
    try:
        result = run(["open", *args], check=False, capture_output=True, text=True)
    except Exception:
        log.warning("could not launch %s", label, exc_info=True)
        return
    if getattr(result, "returncode", 0) == 0:
        launched.append(label)
        log.info("launched %s", label)
    else:
        err = (getattr(result, "stderr", "") or "").strip()
        log.warning("open %s failed (rc=%s): %s", label, result.returncode, err)


def launch_apps(*, settings=None, run=subprocess.run, on_wake: bool = False) -> list[str]:
    """Open the configured apps/tabs; return what actually launched. Never raises.
    on_wake=True honours the WAKE_APPS_ENABLED switch; the spoken tool ignores it."""
    settings = settings or get_settings()
    if on_wake and not settings.wake_apps_enabled:
        return []
    launched: list[str] = []
    if settings.wake_launch_spotify:
        _open(run, ["-a", "Spotify"], "Spotify", launched)
    urls = _urls(settings.wake_urls)
    if urls:
        _open(run, ["-a", "Google Chrome", *urls], f"Chrome ({len(urls)} tabs)", launched)
    return launched


async def launch(arg: str, utterance: str) -> str:
    """The open_apps tool: launch on command, reply in persona-ready plain text."""
    launched = launch_apps()
    if not launched:
        return "Nothing opened, sir — no apps or tabs are configured, or they failed to launch."
    return "Opening " + " and ".join(launched) + ", sir."
