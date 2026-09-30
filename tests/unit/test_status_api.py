"""friday · tests/unit/test_status_api.py

/api/v1/system/status — the board's everything-at-a-glance payload: armed flags mirror
config, queue counts the review items, shape is stable for the UI.
"""

import pytest

from config.settings import get_settings
from integrations import api


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch, tmp_path):
    import integrations.content as content_mod

    monkeypatch.setattr(content_mod, "_DB", tmp_path / "content.db")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_status_all_dark_by_default() -> None:
    data = api.status({})
    assert set(data) == {"daemon", "identity", "systems", "queue", "next_event", "activity"}
    assert data["identity"]["assistant"] == "Friday"
    assert data["identity"]["wake_phrase"] == "Hey Friday"
    assert data["identity"]["wake_phrase_active"] == "Hey Jarvis"
    assert data["identity"]["wake_phrase_ready"] is False
    assert data["identity"]["voice_lock_scope"] == "wake-only"
    assert all(v is False for v in data["systems"].values())
    assert data["queue"] == 0
    assert isinstance(data["activity"], list)


def test_status_flags_arm_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example")
    monkeypatch.setenv("APP_ACCESS_KEY", "k" * 32)
    monkeypatch.setenv("WAKE_MODEL_PATH", "voice/wakeword/wake.onnx")
    monkeypatch.setenv("WAKE_VERIFIER_PATH", "voice/wakeword/owner.joblib")
    monkeypatch.setenv("WAKE_REQUIRE_VERIFIER", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("config.tools.load_tools", lambda: [])  # no Friday n8n tool
    data = api.status({})
    systems = data["systems"]
    assert systems["brain"] is True
    assert systems["n8n ops"] is False  # a URL alone arms nothing: no Friday n8n tool
    assert systems["gate"] is True
    assert systems["voice lock"] is True
    assert systems["voice keys"] is False  # deepgram+cartesia still dark
    assert data["identity"]["wake_phrase_active"] == "Hey Friday"
    assert data["identity"]["wake_phrase_ready"] is True
    assert data["identity"]["voice_lock"] == "strict"
    assert data["identity"]["voice_lock_ready"] is True


def test_status_counts_review_queue() -> None:
    import integrations.content as content_mod

    content_mod.upsert([{"id": "a", "title": "Reel", "score": 1}])
    assert api.status({})["queue"] == 1


def test_n8n_ops_arms_only_with_a_registered_friday_n8n_tool(monkeypatch) -> None:
    from config.tools import Tool

    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example")
    get_settings.cache_clear()
    tool = Tool(name="x", description="x", adapter="adapters.n8n:run",
                webhook_path="/webhook/x", risk="confirm")
    monkeypatch.setattr("config.tools.load_tools", lambda: [tool])
    assert api.status({})["systems"]["n8n ops"] is True


def test_phone_voice_needs_the_worker_and_livekit(monkeypatch) -> None:
    monkeypatch.setenv("VOICE_WS_URL", "wss://mac.example:8443")
    get_settings.cache_clear()
    monkeypatch.setattr(api, "_phone_voice_installed", lambda: True)
    monkeypatch.setattr(api, "_port_open", lambda port: False)
    assert api.status({})["systems"]["phone voice"] is False
    monkeypatch.setattr(api, "_port_open", lambda port: port == 7880)
    assert api.status({})["systems"]["phone voice"] is True
    monkeypatch.setattr(api, "_phone_voice_installed", lambda: False)  # stray container only
    assert api.status({})["systems"]["phone voice"] is False


def test_voice_lock_scope_says_every_turn_only_when_truly_armed(monkeypatch, tmp_path) -> None:
    model, voice = tmp_path / "m.onnx", tmp_path / "v.npy"
    monkeypatch.setenv("VOICEPRINT_MODEL_PATH", str(model))
    monkeypatch.setenv("VOICEPRINT_PATH", str(voice))
    monkeypatch.setenv("VOICE_LOCK_TURNS", "true")
    get_settings.cache_clear()
    model.write_bytes(b"onnx")
    ident = api.status({})["identity"]  # flag on, no voiceprint: the agent refuses EVERY turn
    assert ident["voice_lock_scope"] == "every turn — no voiceprint, refusing"
    assert ident["turn_lock"] == "fail-closed" and ident["voice_lock_ready"] is False
    voice.write_bytes(b"npy")
    ident = api.status({})["identity"]
    assert ident["voice_lock_scope"] == "every turn" and ident["voice_lock_ready"] is True
    monkeypatch.setenv("VOICE_LOCK_TURNS", "false")
    get_settings.cache_clear()
    assert api.status({})["identity"]["voice_lock_scope"] == "wake-only"


def test_brain_and_voice_chips_follow_the_active_providers(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("TTS_PROVIDER", "openai")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg")
    monkeypatch.setenv("CARTESIA_API_KEY", "")
    get_settings.cache_clear()
    systems = api.status({})["systems"]
    assert systems["brain"] is True and systems["voice keys"] is True  # no Anthropic/Cartesia
    monkeypatch.setenv("TTS_PROVIDER", "fishaudio")
    get_settings.cache_clear()
    assert api.status({})["systems"]["voice keys"] is False  # Fish key + voice id missing
