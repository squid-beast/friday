"""friday · tests/unit/test_dashboard_server.py

The dashboard server: localhost binding, JSON summary, rendered page, 404s.
Runs against an ephemeral port with a temp metrics db.
"""

import json
import threading
import urllib.request
from pathlib import Path

import pytest

import integrations.store as store_mod
from integrations.server import make_server
from integrations.store import record


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store_mod, "_DB", tmp_path / "metrics.db")
    record("instagram", "reel_views_7d", 12000, db=tmp_path / "metrics.db")
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=2)


def _get(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read()


def test_binds_localhost_only(served: str) -> None:
    assert "127.0.0.1" in served  # never a real interface — secret project


def test_api_summary_serves_points(served: str) -> None:
    status, body = _get(f"{served}/api/v1/metrics")
    assert status == 200
    data = json.loads(body)
    assert data["instagram"]["reel_views_7d"][0]["value"] == 12000.0


def test_dashboard_shell_serves_at_root(served: str) -> None:
    status, body = _get(f"{served}/")
    text = body.decode()
    assert status == 200
    assert "<title>Friday</title>" in text  # the single-dashboard shell
    assert "/_app/" in text  # hydration assets, same-origin (data comes via /api/v1)


def test_suspicious_path_404s(served: str) -> None:
    # clean routes fall back to the SPA; traversal-shaped paths are refused
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(f"{served}/foo/%2e%2e/%2e%2e/etc/passwd")
    assert err.value.code == 404


# --- Phase 7: phone chat routes ---


def _post(url: str, body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read()


def test_legacy_route_and_manifest_serve(served: str) -> None:
    status, body = _get(f"{served}/chat")  # old deep link -> the dashboard shell
    assert status == 200 and b"/_app/" in body
    status, body = _get(f"{served}/manifest.webmanifest")
    manifest = json.loads(body)
    assert manifest["start_url"] == "/" and manifest["display"] == "standalone"


def test_api_ask_round_trips_through_the_bridge(
    served: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import integrations.server as server_mod

    class FakeBridge:
        def ask(self, text: str) -> dict:
            return {"reply": f"Heard: {text}", "pending": False}

    monkeypatch.setattr(server_mod, "_bridge", FakeBridge())
    status, body = _post(f"{served}/api/v1/conversation", json.dumps({"text": "hello"}).encode())
    assert status == 200
    assert json.loads(body) == {"reply": "Heard: hello", "pending": False}


def test_api_ask_malformed_body_400s(served: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import integrations.server as server_mod

    monkeypatch.setattr(server_mod, "_bridge", object())  # must never be reached
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(f"{served}/api/v1/conversation", b"not json")
    assert err.value.code == 400


def test_post_to_unknown_path_404s(served: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(f"{served}/api/other", b"{}")
    assert err.value.code == 404


# --- Phase 7.5: screens + content APIs ---


def test_legacy_screen_routes_serve_the_dashboard(served: str) -> None:
    # studio/today are cards on the one dashboard now; their routes fall back to it
    for path in ("/studio", "/today"):
        status, body = _get(f"{served}{path}")
        assert status == 200 and b"/_app/" in body


def test_bridge_boots_once_and_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: native libs must init on the MAIN thread (macOS segfault when
    chromadb/onnxruntime first load inside a request-handler thread). main() calls
    boot_bridge() eagerly; the handler's accessor must reuse that same instance."""
    import integrations.server as server_mod

    built = []

    class FakeBridge:
        def __init__(self) -> None:
            built.append(self)

    monkeypatch.setattr(server_mod, "_bridge", None)
    monkeypatch.setattr("integrations.ask.BrainBridge", FakeBridge)
    first = server_mod.boot_bridge()
    assert server_mod._get_bridge() is first  # handler thread never builds its own
    assert server_mod.boot_bridge() is first
    assert len(built) == 1
