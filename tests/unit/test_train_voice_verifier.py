"""scripts/train_voice_verifier.py — validates inputs and forwards clip paths."""

from pathlib import Path

import pytest

import scripts.train_voice_verifier as trainer


def _wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"wav")


def test_main_trains_and_writes_output_parent(tmp_path: Path, monkeypatch) -> None:
    pos = tmp_path / "pos"
    neg = tmp_path / "neg"
    _wav(pos / "a.wav")
    _wav(neg / "b.wav")
    wake = tmp_path / "wake.onnx"
    wake.write_bytes(b"onnx")
    out = tmp_path / "models" / "owner.joblib"
    called = {}

    def fake_train(**kwargs) -> None:
        called.update(kwargs)

    monkeypatch.setattr(trainer, "train_custom_verifier", fake_train)
    assert trainer.main([
        "--positive-dir", str(pos),
        "--negative-dir", str(neg),
        "--wake-model", str(wake),
        "--output", str(out),
    ]) == 0
    assert called["positive_reference_clips"] == [str(pos / "a.wav")]
    assert called["negative_reference_clips"] == [str(neg / "b.wav")]
    assert called["model_name"] == str(wake)
    assert called["output_path"] == str(out)
    assert out.parent.is_dir()


def test_main_requires_clips_and_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="wake phrase clips missing"):
        trainer.main(["--positive-dir", str(tmp_path / "missing")])
