"""friday · tests/unit/conftest.py

`served`: a real dashboard server on an ephemeral port with every stateful
path pointed at tmp_path. Suites that need a different server define their own.
"""

import threading
from pathlib import Path

import pytest

import integrations.api_hud as api_hud_mod
import integrations.server as server_mod
import integrations.store as store_mod
from integrations.server import make_server
from tests.api_harness import FakeBridge


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


@pytest.fixture(autouse=True)
def _fresh_hud_memo():
    """api_hud memoizes weather/n8n for 60s; never let one test's payload leak."""
    api_hud_mod._memo.clear()
    yield
    api_hud_mod._memo.clear()
