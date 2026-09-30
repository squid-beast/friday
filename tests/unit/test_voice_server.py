"""friday · tests/unit/test_voice_server.py

Phase 7.6 voice routes: page + vendored SDK serve, token refusal when
unconfigured, and the JWT is scoped to the phone room only.
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import integrations.store as store_mod
from integrations.server import make_server


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store_mod, "_DB", tmp_path / "metrics.db")
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=2)


def _get(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read()


def _post(url: str, body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read()


def test_voice_page_removed_from_ui(served: str) -> None:
    # The /voice screen is gone (voice runs by wake word); the endpoint stays.
    # /voice is no longer a distinct page — it falls back to the single dashboard.
    status, body, *_ = _get(f"{served}/voice")
    assert status == 200 and b"/_app/" in body


def test_voice_token_unconfigured_400s(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(f"{served}/api/voice-token")
    assert err.value.code == 400  # blank VOICE_WS_URL in tests — honest refusal


def test_voice_token_configured_returns_scoped_jwt(
    served: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import base64

    from config.settings import get_settings

    monkeypatch.setenv("VOICE_WS_URL", "wss://mac.tail.ts.net:8443")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s" * 32)
    get_settings.cache_clear()
    try:
        status, body = _get(f"{served}/api/voice-token")
        data = json.loads(body)
        assert status == 200 and data["url"].startswith("wss://")
        payload = data["token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        assert claims["video"]["room"] == "phone"  # scoped to the phone room only
        assert claims["video"]["roomJoin"] is True
    finally:
        get_settings.cache_clear()


def test_api_content_lists_from_store(
    served: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import integrations.content as content_mod

    monkeypatch.setattr(content_mod, "_DB", tmp_path / "content.db")
    content_mod.upsert([{"id": "t1", "title": "Storefront reel", "score": 91}])
    status, body = _get(f"{served}/api/content")
    data = json.loads(body)
    assert status == 200
    assert data["items"][0]["title"] == "Storefront reel"
    assert data["armed"] is False  # no webhooks configured in tests


def test_api_content_publish_requires_id(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(f"{served}/api/content/publish", json.dumps({"caption": "x"}).encode())
    assert err.value.code == 400


def test_api_content_skip_roundtrip(
    served: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import integrations.content as content_mod

    monkeypatch.setattr(content_mod, "_DB", tmp_path / "content.db")
    content_mod.upsert([{"id": "t1", "title": "Reel", "score": 50}])
    status, body = _post(f"{served}/api/content/skip", json.dumps({"id": "t1"}).encode())
    assert status == 200
    assert json.loads(body)["items"] == []  # skipped items leave the review queue


def test_api_today_shape(served: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import integrations.api as api_mod

    monkeypatch.setattr(api_mod, "audit_today", list)
    status, body = _get(f"{served}/api/today")
    data = json.loads(body)
    assert status == 200
    assert "calendar" in data and "activity" in data


