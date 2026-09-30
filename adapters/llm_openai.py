"""friday · adapters/llm_openai.py

The ONE OpenAI-compatible path behind adapters/llm.py: OpenAI, OpenRouter,
Gemini (Google's OpenAI-compatible endpoint) and any local/self-hosted server
(vLLM, Ollama, LM Studio) via LLM_BASE_URL. Same think()/think_stream()/get_llm()
contract as the Anthropic path; a missing key raises ValueError here (settings
never raise). Only adapters/ import vendor SDKs.
"""

import asyncio

from openai import AsyncOpenAI

from config.settings import get_settings

_TIMEOUT_S = 30.0
_BASE_URLS = {
    "openai": None,  # SDK default
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "compatible": None,  # LLM_BASE_URL is required
}
_KEY_FIELDS = {
    "openai": "openai_api_key",
    "openrouter": "openrouter_api_key",
    "gemini": "google_api_key",
    "compatible": "openai_api_key",  # optional for local servers
}
# Used when MODEL_SMART/FAST still hold Claude ids: flipping LLM_PROVIDER alone must work.
_DEFAULT_MODELS = {  # (smart, fast)
    "openai": ("gpt-4.1-mini", "gpt-4.1-nano"),
    "openrouter": ("anthropic/claude-sonnet-4.5", "openai/gpt-4.1-nano"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-flash-lite"),
}
_clients: dict[tuple[str, int], AsyncOpenAI] = {}


def endpoint(provider: str) -> tuple[str | None, str]:
    """(base_url, api_key) for a provider; ValueError if it can't be reached."""
    if provider not in _BASE_URLS:
        raise ValueError(f"unknown LLM_PROVIDER '{provider}'")
    s = get_settings()
    base = s.llm_base_url or _BASE_URLS[provider]
    key = getattr(s, _KEY_FIELDS[provider])
    if provider == "compatible":
        if not base:
            raise ValueError("LLM_BASE_URL not set (needed for LLM_PROVIDER=compatible)")
        return base, key or "not-needed"  # local servers ignore the key
    if not key:
        raise ValueError(f"{_KEY_FIELDS[provider].upper()} not set")
    return base, key


def model_for(provider: str, *, fast: bool, override: str | None = None) -> str:
    if override:
        return override
    s = get_settings()
    configured = s.model_fast if fast else s.model_smart
    if configured.startswith("claude") and provider in _DEFAULT_MODELS:
        return _DEFAULT_MODELS[provider][1 if fast else 0]
    return configured


def _client(provider: str) -> AsyncOpenAI:
    """One client per (provider, event loop): an async client is bound to the loop
    that first used it, so a new loop (tests, a restarted bridge) gets a fresh one."""
    cache_key = (provider, id(asyncio.get_running_loop()))
    if cache_key not in _clients:
        base, key = endpoint(provider)
        _clients[cache_key] = AsyncOpenAI(api_key=key, base_url=base,
                                          max_retries=1, timeout=_TIMEOUT_S)
    return _clients[cache_key]


def _request(provider: str, prompt: str, system: str | None, model: str,
             max_tokens: int) -> dict:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    # OpenAI's current models take max_completion_tokens; compatible servers take max_tokens.
    limit = "max_completion_tokens" if provider == "openai" else "max_tokens"
    return {"model": model, "messages": messages, limit: max_tokens}


async def think(provider: str, prompt: str, *, system: str | None, model: str,
                max_tokens: int) -> str:
    response = await _client(provider).chat.completions.create(
        **_request(provider, prompt, system, model, max_tokens))
    text = (response.choices[0].message.content or "") if response.choices else ""
    if not text:
        raise ValueError("model returned no text content")
    return text


async def think_stream(provider: str, prompt: str, *, system: str | None, model: str,
                       max_tokens: int):
    stream = await _client(provider).chat.completions.create(
        stream=True, **_request(provider, prompt, system, model, max_tokens))
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


def get_llm(provider: str):
    """LiveKit's OpenAI plugin pointed at any compatible endpoint (voice pipeline)."""
    from livekit.plugins import openai as openai_plugin  # lazy: only non-Anthropic voice

    base, key = endpoint(provider)
    return openai_plugin.LLM(model=model_for(provider, fast=False), api_key=key,
                             base_url=base)
