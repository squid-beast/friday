"""friday · tests/unit/test_adapters.py

Each Phase 1 adapter, vendor SDK mocked: happy path, timeout, malformed
response, auth failure, missing key. No network. See docs/TESTING.md.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

import adapters.llm as llm_mod
from adapters.llm import get_llm, think
from adapters.stt import get_stt, get_vad
from adapters.tts import get_tts
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch):
    for var, val in (
        ("ANTHROPIC_API_KEY", "sk-test"),
        ("DEEPGRAM_API_KEY", "dg-test"),
        ("CARTESIA_API_KEY", "ca-test"),
        ("TTS_VOICE_ID", "voice-42"),
    ):
        monkeypatch.setenv(var, val)
    get_settings.cache_clear()
    monkeypatch.setattr(llm_mod, "_client", None)
    yield
    get_settings.cache_clear()


def _response(content: list) -> SimpleNamespace:
    return SimpleNamespace(
        content=content, usage=SimpleNamespace(input_tokens=1, output_tokens=2)
    )


def _mock_anthropic(create: AsyncMock) -> MagicMock:
    client = MagicMock()
    client.messages.create = create
    return client


def _auth_error() -> anthropic.AuthenticationError:
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
    return anthropic.AuthenticationError("invalid key", response=response, body=None)


# --- llm ---


async def test_think_happy_path_and_sdk_retry_config() -> None:
    create = AsyncMock(return_value=_response([SimpleNamespace(type="text", text="Indeed, sir.")]))
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        assert await think("hello") == "Indeed, sir."
    assert cls.call_args.kwargs["max_retries"] == 1
    assert cls.call_args.kwargs["timeout"] == 30.0
    assert create.call_args.kwargs["model"] == get_settings().model_smart
    assert create.call_args.kwargs["max_tokens"] == 512  # replies are <=3 spoken sentences


async def test_think_max_tokens_passthrough() -> None:
    create = AsyncMock(return_value=_response([SimpleNamespace(type="text", text="ok")]))
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        await think("route this", fast=True, max_tokens=16)
    assert create.call_args.kwargs["max_tokens"] == 16


async def test_think_fast_uses_cheap_model() -> None:
    create = AsyncMock(return_value=_response([SimpleNamespace(type="text", text="ok")]))
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        await think("route this", fast=True)
    assert create.call_args.kwargs["model"] == get_settings().model_fast


async def test_think_timeout_propagates() -> None:
    create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=httpx.Request("POST", "https://x"))
    )
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        with pytest.raises(anthropic.APITimeoutError):
            await think("hello")


async def test_think_auth_failure_propagates() -> None:
    create = AsyncMock(side_effect=_auth_error())
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        with pytest.raises(anthropic.AuthenticationError):
            await think("hello")


async def test_think_malformed_response_raises() -> None:
    create = AsyncMock(return_value=_response([]))  # no text blocks
    with patch.object(llm_mod, "AsyncAnthropic") as cls:
        cls.return_value = _mock_anthropic(create)
        with pytest.raises(ValueError, match="no text"):
            await think("hello")


def test_llm_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_llm()


def test_get_llm_configured() -> None:
    with patch.object(llm_mod, "anthropic_plugin") as plugin:
        get_llm()
    assert plugin.LLM.call_args.kwargs == {
        "model": get_settings().model_smart,
        "api_key": "sk-test",
    }


# --- stt ---


def test_stt_configured() -> None:
    with patch("adapters.stt.deepgram") as deepgram:
        get_stt()
    assert deepgram.STT.call_args.kwargs == {"model": "nova-3", "api_key": "dg-test"}


def test_stt_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
        get_stt()


def test_vad_is_local_silero() -> None:
    with patch("adapters.stt.silero") as silero:
        get_vad()
    silero.VAD.load.assert_called_once_with()


# --- tts ---


def test_tts_configured_with_voice() -> None:
    with patch("adapters.tts.cartesia") as cartesia:
        get_tts()
    assert cartesia.TTS.call_args.kwargs == {"api_key": "ca-test", "voice": "voice-42"}


def test_tts_default_voice_when_id_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TTS_VOICE_ID", "")
    get_settings.cache_clear()
    with patch("adapters.tts.cartesia") as cartesia:
        get_tts()
    assert cartesia.TTS.call_args.kwargs == {"api_key": "ca-test"}


def test_tts_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTESIA_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="CARTESIA_API_KEY"):
        get_tts()
