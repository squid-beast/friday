"""friday · voice/styling.py

Glue between the mood engine and the TTS engine for every line Friday speaks.
The agent says what KIND of line it is (reply / greeting / checkin, or a gated
kind: kill / cut / confirm / pin / refusal / apology); canned safety constants
from the brain are recognised and gated even when they arrive as a plain reply.
voice/emotion.py decides whether the line may carry the mood; this module then
applies it: Fish gets an inline tag, OpenAI TTS gets tone instructions right
before synthesis, Cartesia gets clean text. Failures fall back to flat speech.
"""

import logging

from voice import emotion

log = logging.getLogger(__name__)


def _gated_lines() -> dict[str, str]:
    """Canned brain lines that must stay flat, mapped to their kind. Explicit imports:
    renaming a constant breaks this loudly instead of silently un-gating a line."""
    from brain.graph import UNARMED_REPLY
    from brain.nodes.chat import LLM_APOLOGY
    from brain.nodes.ops import ABORTED, BLOCKED_LINE, NO_MATCH, NO_PIN_SET, NO_TOOLS, PIN_REFUSED
    from brain.nodes.vault import VAULT_APOLOGY
    from brain.nodes.vision import (
        BROWSER_APOLOGY,
        CAMERA_CUT,
        RECALL_APOLOGY,
        RECALL_OFF,
        SIGHT_APOLOGY,
    )

    refusals = (UNARMED_REPLY, NO_TOOLS, NO_MATCH, BLOCKED_LINE, ABORTED, NO_PIN_SET,
                PIN_REFUSED, CAMERA_CUT, RECALL_OFF)
    apologies = (LLM_APOLOGY, VAULT_APOLOGY, SIGHT_APOLOGY, BROWSER_APOLOGY, RECALL_APOLOGY)
    return {**dict.fromkeys(refusals, "refusal"), **dict.fromkeys(apologies, "apology")}


def _mood_now() -> tuple[str, float, float]:
    from brain import mood

    state = mood.load()
    named, intensity = mood.named_mood(state)
    return named, intensity, state.dims["concern"]


def _provider() -> str:
    from adapters.tts import tts_provider

    return tts_provider()


class Styler:
    """One per voice session. line(text, kind) -> text ready for the TTS engine."""

    def __init__(self, tts=None, *, provider=_provider, mood_now=_mood_now,
                 enabled: bool | None = None) -> None:
        from config.settings import get_settings

        self._tts = tts
        self._provider = provider
        self._mood_now = mood_now
        self._enabled = get_settings().fish_emotion_enabled if enabled is None else enabled
        self._gated = _gated_lines()

    def kind_of(self, text: str, default: str = "reply") -> str:
        return self._gated.get(text.strip(), default)

    def line(self, text: str, kind: str = "reply") -> str:
        try:
            provider = self._provider()
            style = None
            if self._enabled:
                named, intensity, concern = self._mood_now()
                style = emotion.style_for(named, intensity, concern=concern,
                                          kind=self.kind_of(text, kind))
            if provider == "openai" and self._tts is not None:
                self._tts.update_options(instructions=emotion.instructions_for(style))
            return emotion.decorate(text, style, provider)
        except Exception:
            log.warning("styling failed — speaking flat", exc_info=True)
            return emotion.decorate(text, None, "cartesia")
