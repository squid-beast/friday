"""friday · tests/unit/test_camera.py

adapters/camera.py mocked: the cut flag refuses before the lens, missing
imagesnap gets a brew hint, single-invocation capture, describe wiring, and the
frame-content guard — a BLACK frame (what a TCC-blocked camera produces) is
rejected instead of narrated, a real frame is saved as a snap, and imagesnap's
stderr is surfaced (not swallowed) on failure. SAFETY (2026-09-29): with no
describer listening, the camera is never switched on at all.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from adapters import camera
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAMERA_OFF_FILE", str(tmp_path / "camera_off"))
    monkeypatch.setenv("VISION_SNAPS_DIR", str(tmp_path / "snaps"))
    monkeypatch.setattr(camera, "_eyes_up", lambda: True)  # describer "listening"
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _proc(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    proc.returncode = returncode
    return proc


def _spawn_writing(color) -> AsyncMock:
    """A fake imagesnap that writes a real JPEG of the given color to the frame path."""
    async def fake_spawn(*args, **kwargs):
        Image.new("RGB", (64, 64), color).save(args[-1])
        return _proc(0)

    return fake_spawn


async def test_camera_cut_refuses_before_any_capture() -> None:
    Path(get_settings().camera_off_file).touch()
    with (
        patch.object(camera.asyncio, "create_subprocess_exec") as spawn,
        pytest.raises(PermissionError),
    ):
        await camera.look("what am I holding?")
    spawn.assert_not_called()  # the lens is never touched while cut


async def test_no_describer_means_the_camera_never_switches_on(monkeypatch) -> None:
    monkeypatch.setattr(camera, "_eyes_up", lambda: False)
    with (
        patch.object(camera.asyncio, "create_subprocess_exec") as spawn,
        pytest.raises(ConnectionError, match="vision model"),
    ):
        await camera.look("what am I holding?")
    spawn.assert_not_called()  # no light, no frame, no snap while the eyes are down
    assert not Path(get_settings().vision_snaps_dir).exists()


def test_eyes_up_probes_the_describer_port(monkeypatch) -> None:
    monkeypatch.undo()  # the real probe, not the fixture's stub
    monkeypatch.setenv("MOONDREAM_ENDPOINT", "http://127.0.0.1:1/v1")  # nothing listens on 1
    get_settings.cache_clear()
    assert camera._eyes_up() is False


async def test_look_captures_one_frame_and_describes() -> None:
    with (
        patch.object(camera.asyncio, "create_subprocess_exec",
                     side_effect=_spawn_writing("white")) as spawn,
        patch.object(camera, "_describe", return_value="A soldering iron.") as describe,
    ):
        answer = await camera.look("what am I holding?")
    assert answer == "A soldering iron."
    assert spawn.call_count == 1  # single frame by construction
    assert spawn.call_args.args[0] == "imagesnap"
    assert describe.call_args.args[1] == "what am I holding?"


async def test_black_frame_is_rejected_not_narrated() -> None:
    # TCC-blocked camera -> black JPEG at exit 0. Must raise, never describe.
    with (
        patch.object(camera.asyncio, "create_subprocess_exec",
                     side_effect=_spawn_writing((0, 0, 0))),
        patch.object(camera, "_describe") as describe,
        pytest.raises(ValueError, match="black"),
    ):
        await camera.look("what am I holding?")
    describe.assert_not_called()  # darkness is never sent to moondream


async def test_valid_frame_is_saved_as_a_snap() -> None:
    with (
        patch.object(camera.asyncio, "create_subprocess_exec",
                     side_effect=_spawn_writing("white")),
        patch.object(camera, "_describe", return_value="ok"),
    ):
        await camera.look("q")
    snaps = list(Path(get_settings().vision_snaps_dir).glob("*.jpg"))
    assert len(snaps) == 1  # the real frame was persisted for the dashboard


async def test_missing_imagesnap_gives_brew_hint() -> None:
    with patch.object(
        camera.asyncio, "create_subprocess_exec", side_effect=FileNotFoundError
    ), pytest.raises(ValueError, match="brew install imagesnap"):
        await camera.look("q")


async def test_capture_timeout_kills_the_process() -> None:
    """A wedged imagesnap must not hold the camera open."""
    import asyncio

    proc = MagicMock()

    async def never_exits():
        await asyncio.sleep(3600)

    proc.communicate = never_exits
    with (
        patch.object(camera, "_CAPTURE_TIMEOUT_S", 0.01),
        patch.object(camera.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc)),
        pytest.raises(ValueError, match="timed out"),
    ):
        await camera.look("q")
    proc.kill.assert_called_once()  # the lens is released, not leaked


async def test_capture_failure_surfaces_stderr() -> None:
    async def fake_spawn(*args, **kwargs):
        return _proc(1, stderr=b"no camera device found")  # nonzero, no frame

    with (
        patch.object(camera.asyncio, "create_subprocess_exec", side_effect=fake_spawn),
        pytest.raises(ValueError, match="no camera device found"),  # reason not swallowed
    ):
        await camera.look("q")
