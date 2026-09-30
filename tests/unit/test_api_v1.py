"""jarvis-life-os · tests/unit/test_api_v1.py

The professional API surface + the SvelteKit SPA shell, tested three ways:
POSITIVE (every endpoint's happy path), NEGATIVE (bad input, wrong method,
unknown routes), EXCEPTIONAL (traversal attacks, null bytes, unicode, oversized
bodies — the creative abuse a public URL will eventually meet).
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import integrations.server as server_mod
import integrations.store as store_mod
from integrations.server import make_server


class FakeBridge:
    def __init__(self) -> None:
        self.asked: list[str] = []

    def ask(self, text: str) -> dict:
        self.asked.append(text)
        return {"reply": f"Indeed, sir. ({len(text)} chars heard)", "pending": False}


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store_mod, "_DB", tmp_path / "metrics.db")
    monkeypatch.setattr(server_mod, "_bridge", FakeBridge())
    monkeypatch.setenv("STAND_DOWN_FILE", str(tmp_path / "control" / "stand_down"))
    monkeypatch.setenv("VISION_SNAPS_DIR", str(tmp_path / "snaps"))
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VAULT_PATH", str(tmp_path / "vault"))
    monkeypatch.setenv("GESTURE_STATE_FILE", str(tmp_path / "gesture" / "state.json"))
    monkeypatch.setenv("GESTURE_FRAME_FILE", str(tmp_path / "gesture" / "frame.jpg"))
    monkeypatch.setenv("GESTURE_CONTROL_FILE", str(tmp_path / "gesture" / "control_on"))
    from config.settings import get_settings

    get_settings.cache_clear()
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=2)
    get_settings.cache_clear()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read(), dict(r.headers)


def _post(url: str, payload, raw: bytes | None = None):
    data = raw if raw is not None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=5) as r:
        return r.status, json.loads(r.read())


def _code(err) -> int:
    return err.value.code


# --- POSITIVE: the surface works as documented ---


def test_every_v1_read_endpoint_answers_with_its_shape(served: str) -> None:
    for path, key in [("/api/v1/system/status", "systems"),
                      ("/api/v1/metrics", None),
                      ("/api/v1/agenda", "calendar"),
                      ("/api/v1/studio/queue", "items")]:
        status, body, _ = _get(served + path)
        data = json.loads(body)
        assert status == 200 and (key is None or key in data), path


def test_conversation_round_trip_on_v1_and_legacy_alias(served: str) -> None:
    for path in ("/api/v1/conversation", "/api/ask"):
        status, data = _post(served + path, {"text": "status report"})
        assert status == 200 and data["reply"].startswith("Indeed"), path


def test_spa_shell_served_on_all_screens(served: str) -> None:
    for route in ("/", "/hud", "/chat", "/studio", "/today"):
        status, body, headers = _get(served + route)
        assert status == 200 and b"/_app/" in body, route
        assert "text/html" in headers["Content-Type"]


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


def test_immutable_assets_serve_with_cache_header(served: str) -> None:
    _, shell, _ = _get(served + "/")
    asset = "/_app/" + shell.split(b"/_app/")[1].split(b'"')[0].decode()
    status, _, headers = _get(served + asset)
    assert status == 200
    if "/immutable/" in asset:
        assert headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_manifest_is_a_built_file_opening_the_cockpit(served: str) -> None:
    status, body, _ = _get(served + "/manifest.webmanifest")
    manifest = json.loads(body)
    assert status == 200 and manifest["start_url"] == "/"


def test_page_routes_tolerate_query_strings(served: str) -> None:
    status, body, _ = _get(served + "/chat?utm_source=homescreen")
    assert status == 200 and b"/_app/" in body


def test_daemon_wake_and_stand_down_write_control_files(
    served: str, tmp_path: Path
) -> None:
    status, data = _post(served + "/api/v1/daemon/wake", {})
    assert status == 200 and data["requested"] == "wake"
    assert (tmp_path / "control" / "wake").exists()  # the daemon's 0.5s poll acts
    status, data = _post(served + "/api/v1/daemon/stand-down", {})
    assert status == 200 and data["requested"] == "stand_down"
    assert (tmp_path / "control" / "stand_down").exists()


def test_status_reports_the_daemon_truthfully(served: str, tmp_path: Path) -> None:
    _, body, _ = _get(served + "/api/v1/system/status")
    assert json.loads(body)["daemon"] == "off"  # no state file = honest "off"
    (tmp_path / "control").mkdir(parents=True, exist_ok=True)
    (tmp_path / "control" / "state").write_text("active")
    _, body, _ = _get(served + "/api/v1/system/status")
    assert json.loads(body)["daemon"] == "active"


# --- NEGATIVE: wrong input gets refused, not obeyed ---


def test_unknown_api_404_but_clean_pages_fall_back_to_the_app(served: str) -> None:
    for path in ("/api/v1/nope", "/api/v2/conversation"):
        with pytest.raises(urllib.error.HTTPError) as err:
            _get(served + path)
        assert _code(err) == 404, path
    # a clean unknown route serves the single-page app shell (client-side routing)
    status, body, _ = _get(served + "/some/deep/link")
    assert status == 200 and b"/_app/" in body


def test_conversation_requires_text(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(served + "/api/v1/conversation", {"words": "hello"})
    assert _code(err) == 400


def test_malformed_and_non_object_json_400(served: str) -> None:
    for raw in (b"{not json", b'"just a string"', b"[1,2,3]"):
        with pytest.raises(urllib.error.HTTPError) as err:
            _post(served + "/api/v1/conversation", None, raw=raw)
        assert _code(err) == 400, raw


def test_studio_publish_requires_id(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(served + "/api/v1/studio/publish", {"caption": "x"})
    assert _code(err) == 400


def test_voice_session_unconfigured_refuses_honestly(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(served + "/api/v1/voice/session")
    assert _code(err) == 400  # blank VOICE_WS_URL in tests


def test_get_on_a_post_route_is_not_found(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(served + "/api/v1/conversation")
    assert _code(err) == 404


# --- EXCEPTIONAL: creative abuse bounces off ---


@pytest.mark.parametrize("attack", [
    "/_app/../../.env",
    "/_app/%2e%2e/%2e%2e/.env",
    "/_app/..%2f..%2fconfig/settings.py",
    "//_app/../server.py",
    "/_app/%00.js",
])
def test_traversal_and_poison_paths_are_contained(served: str, attack: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(served + attack)
    assert _code(err) == 404, attack  # never 200, never a 500 crash


def test_unicode_and_emoji_survive_the_conversation(served: str) -> None:
    text = "जार्विस, नमस्ते 🤖 — status?"
    status, data = _post(served + "/api/v1/conversation", {"text": text})
    assert status == 200 and "chars heard" in data["reply"]


def test_oversized_body_is_handled_not_fatal(served: str) -> None:
    status, _data = _post(served + "/api/v1/conversation", {"text": "a" * 100_000})
    assert status == 200  # the server survives; the brain decides what to do


def test_head_requests_are_declined_loudly(served: str) -> None:
    request = urllib.request.Request(served + "/", method="HEAD")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(request, timeout=5)
    assert _code(err) == 501  # documented: this shell speaks GET and POST only
