"""friday · tests/unit/test_api_v1.py

The professional API surface + the SvelteKit SPA shell, tested three ways:
POSITIVE (every endpoint's happy path), NEGATIVE (bad input, wrong method,
unknown routes), EXCEPTIONAL (traversal attacks, null bytes, unicode, oversized
bodies — the creative abuse a public URL will eventually meet).
"""

import json
import urllib.error
from pathlib import Path

import pytest

from tests.api_harness import _code, _get, _post

# --- POSITIVE: the surface works as documented ---


def test_every_v1_read_endpoint_answers_with_its_shape(served: str) -> None:
    for path, key in [("/api/v1/system/status", "systems"),
                      ("/api/v1/metrics", None),
                      ("/api/v1/agenda", "calendar"),
                      ("/api/v1/studio/queue", "items")]:
        status, body, _ = _get(served + path)
        data = json.loads(body)
        assert status == 200 and (key is None or key in data), path


def test_conversation_round_trip_and_legacy_aliases_are_gone(served: str) -> None:
    status, data = _post(served + "/api/v1/conversation", {"text": "status report"})
    assert status == 200 and data["reply"].startswith("Indeed")
    for path in ("/api/ask", "/api/status", "/api/today", "/api/content", "/api/voice-token"):
        with pytest.raises(urllib.error.HTTPError) as err:
            _get(served + path)
        assert _code(err) == 404, path  # unversioned aliases removed 2026-09-29


def test_spa_shell_served_on_all_screens(served: str) -> None:
    for route in ("/", "/hud", "/chat", "/studio", "/today"):
        status, body, headers = _get(served + route)
        assert status == 200 and b"/_app/" in body, route
        assert "text/html" in headers["Content-Type"]


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
