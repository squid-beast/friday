"""friday · adapters/llm.py

The brain's LLM seam: get_llm() (LiveKit component for the voice pipeline) and
think()/think_stream() (one-shot helpers, smart/fast). LLM_PROVIDER picks the
backend — anthropic (default, native SDK) or any OpenAI-compatible provider via
adapters/llm_openai.py (openai | openrouter | gemini | compatible). `model=`
overrides the model per call (per-task routing) without touching callers.
Retries/timeout are the SDKs' own (max_retries=1, 30s) — no hand-rolled loop.
"""

import asyncio
import logging

from anthropic import AsyncAnthropic
from livekit.plugins import anthropic as anthropic_plugin

from adapters import llm_openai
from config.settings import get_settings

log = logging.getLogger(__name__)

_TIMEOUT_S = 30.0
_MAX_TOKENS = 512  # spoken replies are <=3 sentences; nothing legitimately needs more

_clients: dict[int, AsyncAnthropic] = {}  # per event loop: an async client binds to its loop


def _provider() -> str:
    return get_settings().llm_provider.strip().lower() or "anthropic"


def _require_key() -> str:
    key = get_settings().anthropic_api_key
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return key


def get_llm():
    """Configured LiveKit LLM component (voice pipeline) for the active provider."""
    provider = _provider()
    if provider != "anthropic":
        return llm_openai.get_llm(provider)
    return anthropic_plugin.LLM(model=get_settings().model_smart, api_key=_require_key())


def _get_client() -> AsyncAnthropic:
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _clients:
        _clients[loop_id] = AsyncAnthropic(api_key=_require_key(), max_retries=1,
                                           timeout=_TIMEOUT_S)
    return _clients[loop_id]


def _anthropic_model(fast: bool, model: str | None) -> str:
    settings = get_settings()
    return model or (settings.model_fast if fast else settings.model_smart)


async def think(
    prompt: str, *, system: str | None = None, fast: bool = False,
    max_tokens: int = _MAX_TOKENS, model: str | None = None,
) -> str:
    """One-shot completion. fast=True routes to the cheap model; model= overrides."""
    provider = _provider()
    if provider != "anthropic":
        return await llm_openai.think(
            provider, prompt, system=system, max_tokens=max_tokens,
            model=llm_openai.model_for(provider, fast=fast, override=model))
    kwargs: dict[str, str] = {"system": system} if system else {}
    message = await _get_client().messages.create(
        model=_anthropic_model(fast, model),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    log.debug("think tokens in=%s out=%s", message.usage.input_tokens,
              message.usage.output_tokens)
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    if not text:
        raise ValueError("model returned no text content")
    return text


async def think_stream(
    prompt: str, *, system: str | None = None, fast: bool = False,
    max_tokens: int = _MAX_TOKENS, model: str | None = None,
):
    """Streaming completion — yields text deltas as they arrive (voice: speak
    the first words while the rest is still being generated)."""
    provider = _provider()
    if provider != "anthropic":
        async for delta in llm_openai.think_stream(
            provider, prompt, system=system, max_tokens=max_tokens,
            model=llm_openai.model_for(provider, fast=fast, override=model)):
            yield delta
        return
    kwargs: dict[str, str] = {"system": system} if system else {}
    async with _get_client().messages.stream(
        model=_anthropic_model(fast, model),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    ) as stream:
        async for delta in stream.text_stream:
            if delta:
                yield delta
