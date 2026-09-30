"""config/settings.py — env parsing, defaults, blank-key tolerance."""

import pytest

from config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("MODEL_SMART", "MODEL_FAST", "CHROMA_PATH", "LIVEKIT_URL", "FRIDAY_STATE_DIR"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.model_smart == "claude-sonnet-5"  # real ID, not PLAN's dead `claude-sonnet-latest`
    assert s.model_fast == "claude-haiku-4-5"
    assert s.chroma_path.endswith("/Library/Application Support/Friday/db/chroma")
    assert s.checkpoint_db_path.endswith("/Library/Application Support/Friday/db/checkpoint.db")
    assert s.livekit_url == "ws://127.0.0.1:7880"
    assert s.assistant_name == "Friday"
    assert s.wake_phrase_text == "Hey Friday"
    assert s.stand_down_phrase_text == "Stand Down"
    assert s.wake_verifier_path == ""
    assert s.wake_require_verifier is False


def test_state_dir_prefixes_relative_runtime_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRIDAY_STATE_DIR", "/tmp/friday-state")
    s = Settings(_env_file=None)
    assert s.logs_dir == "/tmp/friday-state/logs"
    assert s.audit_db_path == "/tmp/friday-state/db/audit.db"
    assert s.vision_snaps_dir == "/tmp/friday-state/images/vision/snaps"


def test_blank_keys_do_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    s = Settings(_env_file=None)
    assert s.anthropic_api_key == ""  # factories raise, Settings never does


def test_env_overrides_and_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_FAST", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("SESSION_SILENCE_TIMEOUT_S", "90")
    monkeypatch.setenv("WAKE_THRESHOLD", "0.8")
    s = Settings(_env_file=None)
    assert s.model_fast == "claude-haiku-4-5-20251001"
    assert s.session_silence_timeout_s == 90
    assert s.wake_threshold == 0.8


def test_get_settings_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_settings() is get_settings()
