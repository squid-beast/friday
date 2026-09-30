"""friday · adapters/tts.py

Cartesia speech synthesis factory (LiveKit component). ElevenLabs fallback is
a documented env var only until it's actually needed.
"""

from livekit.plugins import cartesia

from config.settings import get_settings


def get_tts() -> cartesia.TTS:
    settings = get_settings()
    if not settings.cartesia_api_key:
        raise ValueError("CARTESIA_API_KEY not set")
    kwargs: dict[str, str] = {"api_key": settings.cartesia_api_key}
    if settings.tts_voice_id:
        kwargs["voice"] = settings.tts_voice_id
    return cartesia.TTS(**kwargs)
