"""scripts/record_voice_verifier.py — prompt loop and resume behavior."""

from pathlib import Path

import scripts.record_voice_verifier as rec


def test_main_records_negative_set_and_resumes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rec, "_OUT_DIR", tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    recorded: list[Path] = []

    def fake_record(path: Path, seconds: int = rec.SECONDS) -> None:
        path.write_bytes(b"wav")
        recorded.append(path)

    monkeypatch.setattr(rec, "record_one", fake_record)
    assert rec.main() == 0
    assert len(recorded) == rec.COUNT
    recorded.clear()
    assert rec.main() == 0
    assert recorded == []
