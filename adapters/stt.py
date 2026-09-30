"""friday · adapters/stt.py

Deepgram STT + Silero VAD factories (LiveKit components). Swap for local
whisper later = change this file only.
"""

from livekit.plugins import deepgram, silero

from config.settings import get_settings


def get_stt() -> deepgram.STT:
    key = get_settings().deepgram_api_key
    if not key:
        raise ValueError("DEEPGRAM_API_KEY not set")
    return deepgram.STT(model="nova-3", api_key=key)


def get_vad() -> silero.VAD:
    """Local Silero VAD — no key, weights pre-fetched by `make setup`."""
    return silero.VAD.load()
