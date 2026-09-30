"""friday · tests/unit/test_voiceprint.py

adapters/voiceprint.py against the REAL CAM++ ONNX model (skipped where the
gitignored model isn't downloaded): 512-d L2-normalised embeddings, identical
audio scores ~1, enrollment writes a .npy voiceprint, and a missing voiceprint
or model makes score_if_ready return None so the lock fails closed.
"""

import wave
from pathlib import Path

import numpy as np
import pytest

from adapters import voiceprint
from config.settings import Settings

MODEL = Settings.model_fields["voiceprint_model_path"].default
pytestmark = pytest.mark.skipif(not voiceprint._abs(MODEL).is_file(),
                                reason="speaker model not downloaded (voice/models/)")


def _speechy(seed: int, seconds: float = 2.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(16_000 * seconds)) / 16_000
    tone = sum(np.sin(2 * np.pi * f * t) for f in (140 + seed * 30, 280, 560))
    return (0.1 * tone * (1 + 0.5 * np.sin(2 * np.pi * 3 * t)) +
            0.01 * rng.standard_normal(len(t))).astype(np.float32)


def _wav(path: Path, pcm: np.ndarray) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return path


def test_embeddings_are_512d_and_normalised() -> None:
    vec = voiceprint.embed(_speechy(1), MODEL)
    assert vec.shape == (512,) and abs(np.linalg.norm(vec) - 1) < 1e-4


def test_enroll_then_score(tmp_path: Path) -> None:
    wavs = [_wav(tmp_path / f"c{i}.wav", _speechy(1)) for i in range(3)]
    out = voiceprint.enroll(wavs, MODEL, str(tmp_path / "print.npy"))
    same = voiceprint.score(_speechy(1), str(out), MODEL)
    other = voiceprint.score(_speechy(7), str(out), MODEL)
    assert same > 0.95 and other < same


def test_missing_voiceprint_fails_closed(tmp_path: Path) -> None:
    assert voiceprint.score_if_ready(_speechy(1), str(tmp_path / "none.npy"), MODEL) is None
    assert voiceprint.score_if_ready(_speechy(1), str(tmp_path / "x.npy"),
                                     str(tmp_path / "no-model.onnx")) is None


def test_enroll_script_needs_enough_clips(tmp_path: Path) -> None:
    from scripts import enroll_voice

    assert enroll_voice.main([], root=tmp_path) == 1  # no recordings yet -> refuses
