"""friday · tests/unit/test_wakeword.py

adapters/wakeword.py with sounddevice + openwakeword mocked: detection at
threshold, stop event, model selection (bundled fallback vs custom paths).
"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import adapters.wakeword as ww
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WAKE_MODEL_PATH", raising=False)
    monkeypatch.delenv("KILL_MODEL_PATH", raising=False)
    monkeypatch.delenv("WAKE_VERIFIER_PATH", raising=False)
    monkeypatch.delenv("WAKE_VERIFIER_THRESHOLD", raising=False)
    monkeypatch.delenv("WAKE_REQUIRE_VERIFIER", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stream_with(frames: list[np.ndarray]) -> MagicMock:
    stream = MagicMock()
    stream.__enter__ = MagicMock(return_value=stream)
    stream.__exit__ = MagicMock(return_value=False)
    stream.read.side_effect = [(f, False) for f in frames]
    return stream


def _model(scores: list[float]) -> SimpleNamespace:
    it = iter(scores)
    return SimpleNamespace(predict=lambda frame: {"m": next(it)})


def test_listen_detects_at_threshold() -> None:
    frames = [np.zeros((ww.FRAME_SAMPLES, 1), dtype=np.int16)] * 3
    detected = []
    with patch.object(ww.sd, "InputStream", return_value=_stream_with(frames)):
        ww.listen(
            lambda: detected.append(True),
            threading.Event(),
            model=_model([0.1, 0.62, 0.99]),
            threshold=0.6,
        )
    assert detected == [True]  # fired once at 0.62 and returned — 0.99 never read


def test_listen_respects_stop_event() -> None:
    stop = threading.Event()
    stop.set()
    stream = _stream_with([])
    with patch.object(ww.sd, "InputStream", return_value=stream):
        ww.listen(lambda: pytest.fail("must not detect"), stop, model=_model([]), threshold=0.6)
    stream.read.assert_not_called()


def test_listen_below_threshold_keeps_listening_until_stop() -> None:
    stop = threading.Event()
    scores = iter([0.2, 0.3, 0.5])

    def predict(frame):
        score = next(scores, None)
        if score is None:
            stop.set()
            return {"m": 0.0}
        return {"m": score}

    frames = [np.zeros((ww.FRAME_SAMPLES, 1), dtype=np.int16)] * 10
    with patch.object(ww.sd, "InputStream", return_value=_stream_with(frames)):
        ww.listen(
            lambda: pytest.fail("must not detect below threshold"),
            stop,
            model=SimpleNamespace(predict=predict),
            threshold=0.6,
        )


def test_wake_model_bundled_fallback_when_unset() -> None:
    with patch.object(ww, "Model") as model_cls:
        ww.get_wake_model()
    path = model_cls.call_args.kwargs["wakeword_model_paths"][0]
    assert "hey_jarvis" in path


def test_wake_model_custom_path_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAKE_MODEL_PATH", "voice/wakeword/wake.onnx")
    get_settings.cache_clear()
    with patch.object(ww, "Model") as model_cls:
        ww.get_wake_model()
    assert model_cls.call_args.kwargs["wakeword_model_paths"] == ["voice/wakeword/wake.onnx"]


def test_wake_model_passes_owner_verifier_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WAKE_MODEL_PATH", "voice/wakeword/wake.onnx")
    monkeypatch.setenv("WAKE_VERIFIER_PATH", "voice/wakeword/owner.joblib")
    monkeypatch.setenv("WAKE_VERIFIER_THRESHOLD", "0.22")
    get_settings.cache_clear()
    with patch.object(ww, "Model") as model_cls:
        ww.get_wake_model()
    assert model_cls.call_args.kwargs["custom_verifier_models"] == {
        "wake": "voice/wakeword/owner.joblib"
    }
    assert model_cls.call_args.kwargs["custom_verifier_threshold"] == 0.22


def test_strict_owner_voice_requires_verifier_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAKE_REQUIRE_VERIFIER", "true")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="WAKE_VERIFIER_PATH"):
        ww.get_wake_model()


def test_kill_model_unarmed_when_unset() -> None:
    assert ww.get_kill_model() is None


def test_kill_listen_no_model_returns_without_opening_mic() -> None:
    with patch.object(ww.sd, "InputStream") as stream_cls:
        ww.kill_listen(lambda: pytest.fail("unarmed"), threading.Event())
    stream_cls.assert_not_called()


def test_kill_listen_armed_model_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KILL_MODEL_PATH", "voice/wakeword/standdown.onnx")
    get_settings.cache_clear()
    frames = [np.zeros((ww.FRAME_SAMPLES, 1), dtype=np.int16)] * 2
    detected = []
    with (
        patch.object(ww, "Model", return_value=_model([0.95])),
        patch.object(ww.sd, "InputStream", return_value=_stream_with(frames)),
    ):
        ww.kill_listen(lambda: detected.append(True), threading.Event())
    assert detected == [True]
