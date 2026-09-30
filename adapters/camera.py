"""jarvis-life-os · adapters/camera.py

Single-frame sight. Capture via imagesnap — one frame, then the process exits,
so the camera is released by construction and continuous capture is impossible
from this code path (the OS green light is the truthful indicator). Description
via the LOCAL Moondream Station. The camera_off cut flag refuses before the
lens is ever touched.

A frame is VALIDATED before it is described: a black/unreadable frame (what a
TCC-blocked camera produces — imagesnap writes black and still exits 0) is
rejected, so Jarvis never narrates darkness as if it saw something. Every real
frame is saved to the snaps dir so the dashboard can show what it saw.
"""

import asyncio
import logging
import shutil
import tempfile
import time
from pathlib import Path

from config.settings import get_settings

log = logging.getLogger(__name__)

_WARMUP_S = "1"  # imagesnap -w: give the sensor a beat, avoids black frames
_CAPTURE_TIMEOUT_S = 15
_BLACK_MEAN = 8.0  # mean luma < this = the lens saw nothing. ponytail: tune per camera


async def look(question: str) -> str:
    """One frame in, one answer out. Raises PermissionError while the camera is cut,
    ValueError if the capture is missing/black (so darkness is never narrated)."""
    settings = get_settings()
    if Path(settings.camera_off_file).exists():
        raise PermissionError("camera is cut")
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.jpg"
        await _capture(frame)
        await asyncio.to_thread(_validate_and_save, frame, settings)
        return await asyncio.to_thread(_describe, frame, question)


async def _capture(frame: Path) -> None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "imagesnap", "-w", _WARMUP_S, str(frame),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,  # keep the reason — don't swallow it
        )
    except FileNotFoundError as exc:
        raise ValueError("imagesnap not installed (brew install imagesnap)") from exc
    try:
        _out, err = await asyncio.wait_for(proc.communicate(), timeout=_CAPTURE_TIMEOUT_S)
    except TimeoutError as exc:
        proc.kill()
        raise ValueError("camera capture timed out") from exc
    if proc.returncode != 0 or not frame.exists():
        detail = (err or b"").decode(errors="replace").strip()
        log.warning("imagesnap failed rc=%s: %s", proc.returncode, detail)
        raise ValueError(f"camera capture failed (permission not granted?) {detail}".strip())


def _validate_and_save(frame: Path, settings) -> None:
    """Reject a black/unreadable frame; save a real one to the snaps dir for the UI."""
    from PIL import Image, ImageStat

    try:
        img = Image.open(frame)
        img.load()
    except Exception as exc:
        raise ValueError("camera produced an unreadable frame") from exc
    mean = ImageStat.Stat(img.convert("L")).mean[0]
    if mean < _BLACK_MEAN:
        log.warning("camera frame is black (mean=%.1f) — Camera permission likely denied", mean)
        raise ValueError("camera saw only black — grant Camera access in System Settings")
    _save_snap(frame, settings)


def _save_snap(frame: Path, settings) -> None:
    """Copy the validated frame into the snaps dir; keep the most recent N."""
    try:
        snaps = Path(settings.vision_snaps_dir)
        snaps.mkdir(parents=True, exist_ok=True)
        shutil.copy2(frame, snaps / f"{time.strftime('%Y%m%d-%H%M%S')}.jpg")
        keep = settings.vision_snaps_keep
        for old in sorted(snaps.glob("*.jpg"))[:-keep] if keep > 0 else []:
            old.unlink(missing_ok=True)
    except Exception:
        log.warning("could not save camera snap", exc_info=True)  # never break the look


def _describe(frame: Path, question: str) -> str:
    import moondream as md  # lazy: keep module import cheap for the no-network kill path
    from PIL import Image

    model = md.vl(endpoint=get_settings().moondream_endpoint)
    answer = model.query(Image.open(frame), question)["answer"]
    if not answer:
        raise ValueError("moondream returned no answer")
    return str(answer).strip()
