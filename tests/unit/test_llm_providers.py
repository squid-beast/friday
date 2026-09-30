"""friday · tests/unit/test_llm_providers.py

Phase 2: LLM_PROVIDER switches think()/think_stream()/get_llm() between the
native Anthropic path and ONE OpenAI-compatible path (openai / openrouter /
gemini / compatible). Every client is faked — no network. Missing keys raise
in the adapter (settings never raise); Claude model ids never leak to another
provider; model= overrides per call.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import adapters.llm as llm
import adapters.llm_openai as oai
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    for var in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "OPENAI_API_KEY",
                "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "MODEL_SMART", "MODEL_FAST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(oai, "_clients", {})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _provider(monkeypatch, name: str, **env: str) -> None:
    monkeypatch.setenv("LLM_PROVIDER", name)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _fake_openai(monkeypatch, reply: str = "Indeed, sir.") -> MagicMock:
    made = MagicMock()

    def factory(**kwargs):
        made.kwargs = kwargs
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]))
        made.client = client
        return client

    monkeypatch.setattr(oai, "AsyncOpenAI", factory)
    return made


async def test_openai_provider_answers_with_its_own_default_models(monkeypatch) -> None:
    _provider(monkeypatch, "openai", OPENAI_API_KEY="sk-test")
    made = _fake_openai(monkeypatch)
    assert await llm.think("hello", system="be Friday") == "Indeed, sir."
    assert made.kwargs["api_key"] == "sk-test" and made.kwargs["base_url"] is None
    call = made.client.chat.completions.create.call_args.kwargs
    assert call["model"] == "gpt-4.1-mini"  # Claude id in MODEL_SMART never sent to OpenAI
    assert call["messages"][0] == {"role": "system", "content": "be Friday"}
    assert call["max_completion_tokens"] == 512
    await llm.think("route", fast=True)
    assert made.client.chat.completions.create.call_args.kwargs["model"] == "gpt-4.1-nano"


async def test_model_override_wins_per_call(monkeypatch) -> None:
    _provider(monkeypatch, "openai", OPENAI_API_KEY="sk-test")
    made = _fake_openai(monkeypatch)
    await llm.think("code this", model="gpt-4.1")
    assert made.client.chat.completions.create.call_args.kwargs["model"] == "gpt-4.1"


@pytest.mark.parametrize(("name", "env", "base", "key"), [
    ("openrouter", {"OPENROUTER_API_KEY": "or-k"}, "https://openrouter.ai/api/v1", "or-k"),
    ("gemini", {"GOOGLE_API_KEY": "g-k"},
     "https://generativelanguage.googleapis.com/v1beta/openai/", "g-k"),
    ("compatible", {"LLM_BASE_URL": "http://127.0.0.1:11434/v1", "MODEL_SMART": "llama3.1"},
     "http://127.0.0.1:11434/v1", "not-needed"),
])
async def test_each_provider_gets_its_endpoint(monkeypatch, name, env, base, key) -> None:
    _provider(monkeypatch, name, **env)
    made = _fake_openai(monkeypatch)
    await llm.think("hi")
    assert made.kwargs["base_url"] == base and made.kwargs["api_key"] == key
    limit = made.client.chat.completions.create.call_args.kwargs
    assert "max_tokens" in limit  # compatible servers take max_tokens


@pytest.mark.parametrize(("name", "message"), [
    ("openai", "OPENAI_API_KEY not set"),
    ("openrouter", "OPENROUTER_API_KEY not set"),
    ("gemini", "GOOGLE_API_KEY not set"),
    ("compatible", "LLM_BASE_URL not set"),
    ("mystery", "unknown LLM_PROVIDER"),
])
async def test_missing_configuration_raises_in_the_adapter(monkeypatch, name, message) -> None:
    _provider(monkeypatch, name)
    _ = get_settings()  # settings themselves never raise
    with pytest.raises(ValueError, match=message):
        await llm.think("hi")


async def test_streaming_yields_deltas(monkeypatch) -> None:
    _provider(monkeypatch, "openai", OPENAI_API_KEY="sk-test")
    made = _fake_openai(monkeypatch)

    async def chunks():
        for text in ("In", "deed", None, ", sir."):
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])

    async def fake_create(**kwargs):
        assert kwargs["stream"] is True
        return chunks()

    await llm.think("warm up")  # builds the client
    made.client.chat.completions.create = fake_create
    assert [d async for d in llm.think_stream("hi")] == ["In", "deed", ", sir."]


async def test_empty_reply_raises(monkeypatch) -> None:
    _provider(monkeypatch, "openai", OPENAI_API_KEY="sk-test")
    _fake_openai(monkeypatch, reply="")
    with pytest.raises(ValueError, match="no text"):
        await llm.think("hi")


def test_voice_pipeline_uses_the_openai_plugin_for_other_providers(monkeypatch) -> None:
    from livekit.plugins import openai as openai_plugin

    _provider(monkeypatch, "openrouter", OPENROUTER_API_KEY="or-k")
    made = MagicMock()
    monkeypatch.setattr(openai_plugin, "LLM", made)
    llm.get_llm()
    assert made.call_args.kwargs == {"model": "anthropic/claude-sonnet-4.5", "api_key": "or-k",
                                     "base_url": "https://openrouter.ai/api/v1"}


def test_anthropic_stays_the_default_provider() -> None:
    assert get_settings().llm_provider == "anthropic" and llm._provider() == "anthropic"


async def test_base_url_never_redirects_a_cloud_provider(monkeypatch) -> None:
    _provider(monkeypatch, "openai", OPENAI_API_KEY="sk-real", LLM_BASE_URL="http://evil:8000/v1")
    made = _fake_openai(monkeypatch)
    await llm.think("hi")
    assert made.kwargs["base_url"] is None  # OpenAI key only ever goes to OpenAI


async def test_compatible_never_receives_the_openai_key(monkeypatch) -> None:
    _provider(monkeypatch, "compatible", OPENAI_API_KEY="sk-real", MODEL_SMART="llama3.1",
              LLM_BASE_URL="http://127.0.0.1:11434/v1")
    made = _fake_openai(monkeypatch)
    await llm.think("hi")
    assert made.kwargs["api_key"] == "not-needed"


async def test_compatible_refuses_claude_model_ids(monkeypatch) -> None:
    _provider(monkeypatch, "compatible", LLM_BASE_URL="http://127.0.0.1:11434/v1")
    _fake_openai(monkeypatch)
    with pytest.raises(ValueError, match="compatible needs MODEL_SMART"):
        await llm.think("hi")
