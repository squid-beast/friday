"""friday · tests/unit/test_app_gate.py

Access-key gate for the app server (TDD — the wall the public internet hits).
Unset APP_ACCESS_KEY = open on localhost/tailnet, today's behavior. Set =
every route demands the key: one-time ?key= (sets a cookie), the cookie, or
an Authorization: Bearer header. Wrong or missing key never reaches the brain.
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import integrations.store as store_mod
from config.settings import get_settings
from integrations.server import make_server

KEY = "k" * 32


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store_mod, "_DB", tmp_path / "metrics.db")
    monkeypatch.setenv("APP_ACCESS_KEY", KEY)
    get_settings.cache_clear()
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=2)
    get_settings.cache_clear()


def _get(url: str, headers: dict | None = None):
    request = urllib.request.Request(url, headers=headers or {})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=5) as response:
        return response.status, response.read(), dict(response.headers)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # keep 303s visible
        return None


def test_unset_key_stays_open(served: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ACCESS_KEY")
    get_settings.cache_clear()
    status, body, _ = _get(f"{served}/")
    assert status == 200 and b"FRIDAY" in body.upper()


def test_missing_key_is_401(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(f"{served}/")
    assert err.value.code == 401


def test_wrong_key_is_401(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(f"{served}/?key=wrong")
    assert err.value.code == 401


def test_query_key_sets_cookie_and_redirects_clean(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:  # no-redirect opener raises on 303
        _get(f"{served}/chat?key={KEY}")
    assert err.value.code == 303
    assert err.value.headers["Location"] == "/chat"
    cookie = err.value.headers["Set-Cookie"]
    assert KEY in cookie and "HttpOnly" in cookie
    status, body, _ = _get(f"{served}/chat", headers={"Cookie": f"friday_key={KEY}"})
    assert status == 200 and b"friday" in body.lower()


def test_bearer_header_passes(served: str) -> None:
    status, body, _ = _get(
        f"{served}/api/v1/agenda", headers={"Authorization": f"Bearer {KEY}"}
    )
    assert status == 200 and b"calendar" in body


def test_post_without_key_never_reaches_brain(served: str) -> None:
    request = urllib.request.Request(
        f"{served}/api/v1/conversation",
        data=json.dumps({"text": "hello"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(request, timeout=5)
    assert err.value.code == 401
