"""friday · adapters/tts.py

Speech synthesis factory (LiveKit component), switched by TTS_PROVIDER:
- cartesia (default) — fast, reliable; never receives emotion tags.
- openai — gpt-4o-mini-tts; emotion arrives as per-turn tone *instructions*
  (voice/emotion.py sets them via update_options). Works on the OpenAI key alone.
- fishaudio — Fish Audio S1 speaking in a cloned voice (FISH_VOICE_ID); emotion
  arrives as an inline "(worried)"-style tag on the first chunk. Dormant until
  FISH_API_KEY + FISH_VOICE_ID are set.
Every branch raises ValueError on a missing key (settings never raise). The
voice agent asks tts_provider() how to style a line — nothing else changes.
"""

from livekit.plugins import cartesia

from config.settings import get_settings
from voice.emotion import NEUTRAL_INSTRUCTIONS

PROVIDERS = ("cartesia", "openai", "fishaudio")


def tts_provider() -> str:
    provider = get_settings().tts_provider.strip().lower() or "cartesia"
    if provider not in PROVIDERS:
        raise ValueError(f"unknown TTS_PROVIDER '{provider}'")
    return provider


def get_tts():
    provider = tts_provider()
    settings = get_settings()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set (needed for TTS_PROVIDER=openai)")
        from livekit.plugins import openai as openai_plugin

        return openai_plugin.TTS(model=settings.openai_tts_model,
                                 voice=settings.openai_tts_voice,
                                 instructions=NEUTRAL_INSTRUCTIONS,
                                 api_key=settings.openai_api_key)
    if provider == "fishaudio":
        if not settings.fish_api_key:
            raise ValueError("FISH_API_KEY not set (needed for TTS_PROVIDER=fishaudio)")
        if not settings.fish_voice_id:
            raise ValueError("FISH_VOICE_ID not set — clone the target voice in Fish Audio")
        from livekit.plugins import fishaudio

        return fishaudio.TTS(api_key=settings.fish_api_key, model=settings.fish_model,
                             voice_id=settings.fish_voice_id)
    if not settings.cartesia_api_key:
        raise ValueError("CARTESIA_API_KEY not set")
    kwargs: dict[str, str] = {"api_key": settings.cartesia_api_key}
    if settings.tts_voice_id:
        kwargs["voice"] = settings.tts_voice_id
    return cartesia.TTS(**kwargs)
