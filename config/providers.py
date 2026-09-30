"""friday · config/providers.py

Which keys the ACTIVE providers need — one answer shared by the status API
(dashboard chips) and `make doctor`, so they can never disagree. Pure config
reads: no network, never raises.
"""

LLM_KEY = {"anthropic": "anthropic_api_key", "openai": "openai_api_key",
           "openrouter": "openrouter_api_key", "gemini": "google_api_key"}
TTS_KEYS = {"cartesia": ("cartesia_api_key",), "openai": ("openai_api_key",),
            "fishaudio": ("fish_api_key", "fish_voice_id")}


def llm_provider(s) -> str:
    return s.llm_provider.strip().lower() or "anthropic"


def tts_provider(s) -> str:
    return s.tts_provider.strip().lower() or "cartesia"


def llm_fields(s) -> tuple[str, ...]:
    """Settings the active LLM needs (compatible: a base URL; its key is optional)."""
    provider = llm_provider(s)
    return ("llm_base_url",) if provider == "compatible" else (LLM_KEY.get(provider, ""),)


def voice_fields(s) -> tuple[str, ...]:
    """Speech-in (Deepgram) + whatever the active TTS engine needs."""
    return ("deepgram_api_key", *TTS_KEYS.get(tts_provider(s), ("cartesia_api_key",)))


def missing(s, fields: tuple[str, ...]) -> list[str]:
    return [f for f in fields if not f or not getattr(s, f, "")]


def turn_lock(s) -> str:
    """'off' | 'armed' | 'fail-closed' — mirrors voice/owner_lock: the flag alone arms it,
    and without model + voiceprint every spoken turn is refused."""
    if not s.voice_lock_turns:
        return "off"
    from adapters.voiceprint import _abs

    ready = all(_abs(p).is_file() for p in (s.voiceprint_model_path, s.voiceprint_path))
    return "armed" if ready else "fail-closed"
