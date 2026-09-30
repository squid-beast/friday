"""adapters/spotify.py — osascript playback control (subprocess mocked). The
utterance maps to the right AppleScript; a missing/closed Spotify degrades to an
apology instead of raising (ops turns a raise into its own apology anyway)."""

from unittest.mock import AsyncMock, MagicMock, patch

from adapters import spotify


def _proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def _spawn(proc: MagicMock):
    async def fake(*args, **kwargs):
        fake.script = args[-1]  # the AppleScript passed to `osascript -e`
        return proc

    return fake


async def test_default_intent_is_play() -> None:
    spawn = _spawn(_proc(0))
    with patch.object(spotify.asyncio, "create_subprocess_exec", side_effect=spawn):
        assert await spotify.control("", "play some music on spotify") == "Playing, sir."
    assert "to play" in spawn.script  # not a re-open of Chrome — real playback


async def test_pause() -> None:
    spawn = _spawn(_proc(0))
    with patch.object(spotify.asyncio, "create_subprocess_exec", side_effect=spawn):
        assert await spotify.control("", "pause the music") == "Paused, sir."
    assert "to pause" in spawn.script


async def test_next_track() -> None:
    spawn = _spawn(_proc(0))
    with patch.object(spotify.asyncio, "create_subprocess_exec", side_effect=spawn):
        assert await spotify.control("", "skip to the next song") == "Skipping ahead, sir."
    assert "next track" in spawn.script


async def test_now_playing_reads_the_track() -> None:
    spawn = _spawn(_proc(0, stdout=b"Song X \xe2\x80\x94 Artist Y"))
    with patch.object(spotify.asyncio, "create_subprocess_exec", side_effect=spawn):
        out = await spotify.control("", "what's playing right now?")
    assert out.startswith("Now playing:") and "Artist Y" in out


async def test_spotify_absent_degrades_to_apology() -> None:
    spawn = _spawn(_proc(1, stderr=b"application isn't running"))
    with patch.object(spotify.asyncio, "create_subprocess_exec", side_effect=spawn):
        out = await spotify.control("", "play music")
    assert "couldn't reach Spotify" in out  # never raises
