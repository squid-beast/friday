"""jarvis-life-os · tests/unit/test_record_wakeword.py

Recorder plan math + wav writing (sounddevice mocked — no real mic).
"""

import wave
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np

import scripts.record_wakeword as rec


def test_plan_is_50_takes_across_scenarios() -> None:
    takes = rec.plan()
    assert len(takes) == 50
    assert Counter(s for s, _ in takes) == {"near": 15, "far": 15, "quiet": 10, "loud": 10}
    assert all(scenario in rec.TIPS for scenario, _ in takes)  # every take has guidance


def test_record_one_writes_valid_16k_mono_wav(tmp_path: Path) -> None:
    frames = np.zeros((rec.SAMPLE_RATE * rec.SECONDS, 1), dtype=np.int16)
    out = tmp_path / "near_01.wav"
    with patch.object(rec.sd, "rec", return_value=frames), patch.object(rec.sd, "wait"):
        rec.record_one(out)
    with wave.open(str(out)) as f:
        assert f.getframerate() == 16_000
        assert f.getnchannels() == 1
        assert f.getsampwidth() == 2
        assert f.getnframes() == rec.SAMPLE_RATE * rec.SECONDS


def test_both_phrases_have_prompts() -> None:
    assert set(rec.PHRASES) == {"wake", "standdown"}


def test_main_records_all_takes_and_resumes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rec, "_OUT_ROOT", tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    recorded: list[Path] = []

    def fake_record(path: Path, seconds: int = rec.SECONDS) -> None:
        path.write_bytes(b"wav")
        recorded.append(path)

    monkeypatch.setattr(rec, "record_one", fake_record)
    assert rec.main([]) == 0
    assert len(recorded) == 50
    # resume: existing takes are kept, nothing re-recorded
    recorded.clear()
    assert rec.main([]) == 0
    assert recorded == []
    # the standdown phrase records into its own folder
    assert rec.main(["--phrase", "standdown"]) == 0
    assert len(list((tmp_path / "standdown").glob("*.wav"))) == 50
