"""friday · tests/unit/test_api_v1_devices.py

The device + hand-off endpoints (gesture state/control/frame, Obsidian open,
camera snaps) through the real server — positive, negative and containment.
"""

import json
import urllib.error
from pathlib import Path

import pytest

from tests.api_harness import _code, _get, _post


def _gdir(tmp_path: Path) -> Path:
    d = tmp_path / "gesture"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_gesture_state_reports_hands_when_fresh(served: str, tmp_path: Path) -> None:
    import time

    (_gdir(tmp_path) / "state.json").write_text(json.dumps({
        "hands": [{"chirality": "right", "gesture": "point", "landmarks": {"wrist": [0.5, 0.1]}}],
        "control": True, "ts": time.time()}))
    _, body, _ = _get(served + "/api/v1/gesture/state")
    data = json.loads(body)
    assert data["on_air"] is True and data["control"] is True
    assert data["hands"][0]["gesture"] == "point"


def test_gesture_state_off_air_when_stale(served: str, tmp_path: Path) -> None:
    (_gdir(tmp_path) / "state.json").write_text(json.dumps(
        {"hands": [{"gesture": "point", "landmarks": {}}], "ts": 0}))  # ancient
    _, body, _ = _get(served + "/api/v1/gesture/state")
    data = json.loads(body)
    assert data["on_air"] is False and data["hands"] == []


def test_gesture_control_arms_and_disarms(served: str, tmp_path: Path) -> None:
    _gdir(tmp_path)
    flag = tmp_path / "gesture" / "control_on"
    _, on = _post(served + "/api/v1/gesture/control", {"on": True})
    assert on["control"] is True and flag.exists()
    _, off = _post(served + "/api/v1/gesture/control", {"on": False})
    assert off["control"] is False and not flag.exists()


def test_gesture_frame_served_when_present_else_404(served: str, tmp_path: Path) -> None:
    from PIL import Image

    with pytest.raises(urllib.error.HTTPError) as err:
        _get(served + "/api/v1/gesture/frame")
    assert _code(err) == 404  # no frame until the agent runs
    Image.new("RGB", (16, 12), "white").save(_gdir(tmp_path) / "frame.jpg")
    status, img, headers = _get(served + "/api/v1/gesture/frame")
    assert status == 200 and headers.get("Content-Type") == "image/jpeg" and img[:2] == b"\xff\xd8"



def test_vault_open_hands_off_to_obsidian(served: str, monkeypatch) -> None:
    """We no longer render the vault — we open the real app. Whole vault + one note."""
    import adapters.vault as vault_mod

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(vault_mod.subprocess, "run", fake_run)
    status, data = _post(served + "/api/v1/vault/open", {})
    assert status == 200 and "Obsidian" in data["opened"]
    assert calls[0][0] == "open" and calls[0][1].startswith("obsidian://open?vault=")
    _post(served + "/api/v1/vault/open", {"note": "med spa"})
    assert "&file=med%20spa" in calls[1][1]  # a specific note, URL-escaped


def test_vault_open_failure_is_400(served: str, monkeypatch) -> None:
    import adapters.vault as vault_mod

    monkeypatch.setattr(vault_mod.subprocess, "run",
                        lambda cmd, **kw: type("R", (), {"returncode": 1, "stderr": "no app"})())
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(served + "/api/v1/vault/open", {})
    assert _code(err) == 400

def test_vision_snaps_lists_then_serves_the_image(served: str, tmp_path: Path) -> None:
    from PIL import Image

    snaps = tmp_path / "snaps"
    snaps.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "white").save(snaps / "20260820-101112.jpg")
    _, body, _ = _get(served + "/api/v1/vision/snaps")
    assert json.loads(body)["snaps"] == ["20260820-101112"]
    status, img, headers = _get(served + "/api/v1/vision/snaps/20260820-101112")
    assert status == 200
    assert headers.get("Content-Type") == "image/jpeg" and img[:2] == b"\xff\xd8"


def test_vision_snap_traversal_is_contained(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(served + "/api/v1/vision/snaps/..%2f..%2f..%2f.env")
    assert _code(err) == 404  # never escapes the snaps dir
