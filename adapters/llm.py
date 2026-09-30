"""friday · adapters/llm.py

Anthropic wrapper: get_llm() LiveKit component for the voice pipeline,
think() one-shot helper (smart/fast) for the brain. Retries/timeout are the
SDK's own (max_retries=1, 30s) — no hand-rolled loop.
"""

import logging

from anthropic import AsyncAnthropic
from livekit.plugins import anthropic as anthropic_plugin

from config.settings import get_settings

log = logging.getLogger(__name__)

_TIMEOUT_S = 30.0
_MAX_TOKENS = 512  # spoken replies are <=3 sentences; nothing legitimately needs more

_client: AsyncAnthropic | None = None


def _require_key() -> str:
    key = get_settings().anthropic_api_key
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return key


def get_llm() -> anthropic_plugin.LLM:
    """Configured LiveKit LLM component (voice pipeline)."""
    return anthropic_plugin.LLM(model=get_settings().model_smart, api_key=_require_key())


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=_require_key(), max_retries=1, timeout=_TIMEOUT_S)
    return _client


async def think(
    prompt: str, *, system: str | None = None, fast: bool = False, max_tokens: int = _MAX_TOKENS
) -> str:
    """One-shot completion. fast=True routes to the cheap model (routing, Phase 2+)."""
    settings = get_settings()
    kwargs: dict[str, str] = {"system": system} if system else {}
    message = await _get_client().messages.create(
        model=settings.model_fast if fast else settings.model_smart,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    log.debug(
        "think tokens in=%s out=%s", message.usage.input_tokens, message.usage.output_tokens
    )
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    if not text:
        raise ValueError("model returned no text content")
    return text


async def think_stream(
    prompt: str, *, system: str | None = None, fast: bool = False, max_tokens: int = _MAX_TOKENS
):
    """Streaming completion — yields text deltas as they generate, so the voice
    pipeline speaks on the first token instead of waiting for the whole reply."""
    settings = get_settings()
    kwargs: dict[str, str] = {"system": system} if system else {}
    async with _get_client().messages.stream(
        model=settings.model_fast if fast else settings.model_smart,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    ) as stream:
        async for delta in stream.text_stream:
            if delta:
                yield delta
