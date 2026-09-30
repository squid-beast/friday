"""friday · adapters/wakeword.py

openwakeword + sounddevice: LOCAL phrase detection. This is the only audio
path in DORMANT — nothing streams off the machine, and nothing here imports a
network stack. openwakeword is pinned to 0.4.0, the last release that runs on
macOS with pure onnxruntime (newer ones require tflite, Linux-only wheels).

Bundled "hey jarvis" serves only as the temporary fallback while Friday's wake
model is being trained. Strict owner-only mode can also arm a verifier model
that fails closed until Lohith provides it.
"""

import threading

import numpy as np
import openwakeword
import sounddevice as sd
from openwakeword.model import Model

from config.settings import get_settings

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1280  # 80 ms — openwakeword's expected hop


def _bundled_fallback_wake() -> str:
    return next(p for p in openwakeword.get_pretrained_model_paths() if "hey_jarvis" in p)


def _wake_path() -> str:
    return get_settings().wake_model_path or _bundled_fallback_wake()


def _model_key(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".onnx")


def _verifier_kwargs(path: str) -> dict:
    settings = get_settings()
    if settings.wake_require_verifier and not settings.wake_verifier_path:
        raise ValueError("strict voice lock is on, but WAKE_VERIFIER_PATH is not set")
    if not settings.wake_verifier_path:
        return {}
    return {
        "custom_verifier_models": {_model_key(path): settings.wake_verifier_path},
        "custom_verifier_threshold": settings.wake_verifier_threshold,
    }


def get_wake_model() -> Model:
    path = _wake_path()
    return Model(wakeword_model_paths=[path], **_verifier_kwargs(path))


def get_kill_model() -> Model | None:
    """Spoken OFFLINE kill during ACTIVE — armed once a stand-down model is trained."""
    path = get_settings().kill_model_path
    return Model(wakeword_model_paths=[path]) if path else None


def listen(
    on_detect,
    stop: threading.Event,
    *,
    model: Model | None = None,
    threshold: float | None = None,
) -> None:
    """Block until the phrase is heard (call on_detect, return) or stop is set."""
    model = model or get_wake_model()
    threshold = get_settings().wake_threshold if threshold is None else threshold
    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SAMPLES
    ) as stream:
        while not stop.is_set():
            frame, _overflowed = stream.read(FRAME_SAMPLES)
            scores = model.predict(np.squeeze(frame))
            if max(scores.values()) >= threshold:
                on_detect()
                return


def kill_listen(on_detect, stop: threading.Event) -> None:
    """listen() bound to the stand-down model; no-ops instantly when unarmed."""
    model = get_kill_model()
    if model is None:
        return
    listen(on_detect, stop, model=model)
