"""friday · adapters/spotify.py

Control the Spotify desktop app via macOS `osascript` (AppleScript) — no
dependency, no API key, no OAuth. Handles play / pause / skip / previous /
now-playing. It plays whatever is queued or last-played; playing a SPECIFIC song
by name would need the Spotify Web API (deliberately not wired). `tell … to play`
auto-launches Spotify if it isn't open, so this never re-opens Chrome — it just
plays music (that was the "play songs re-opens everything" bug).
"""

import asyncio
import logging

log = logging.getLogger(__name__)

_TIMEOUT_S = 8
# utterance keyword(s) -> (AppleScript, spoken reply). First match wins; order matters.
_ACTIONS = [
    (("pause", "stop"), "pause", "Paused, sir."),
    (("next", "skip", "forward"), "next track", "Skipping ahead, sir."),
    (("previous", "back", "last track", "go back"), "previous track", "Back a track, sir."),
]
_NOW = ("what's playing", "what is playing", "what song", "current track",
        "now playing", "who is this", "what's this")
_NOW_SCRIPT = ('tell application "Spotify" to '
               'name of current track & " — " & artist of current track')


async def _osascript(command: str) -> str:
    """Run one AppleScript line against Spotify; return stdout, raise on failure."""
    script = command if command.startswith("tell") else f'tell application "Spotify" to {command}'
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_S)
    if proc.returncode != 0:
        raise RuntimeError((err or b"").decode(errors="replace").strip() or "osascript failed")
    return (out or b"").decode(errors="replace").strip()


async def control(arg: str, utterance: str) -> str:
    """spotify_play tool: map the utterance to a playback action. Default = play."""
    u = utterance.lower()
    try:
        if any(k in u for k in _NOW):
            track = await _osascript(_NOW_SCRIPT)
            return f"Now playing: {track}, sir." if track else "Nothing is playing, sir."
        for keys, command, reply in _ACTIONS:
            if any(k in u for k in keys):
                await _osascript(command)
                return reply
        await _osascript("play")  # default: play / resume
        return "Playing, sir."
    except Exception:
        log.warning("spotify control failed", exc_info=True)
        return "I couldn't reach Spotify, sir — is it installed and open?"
