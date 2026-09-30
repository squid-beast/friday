"""friday · voice/styling.py

Glue between the mood engine and the TTS engine for every line Friday speaks.
The agent says what KIND of line it is (reply / greeting / checkin, or a gated
kind: kill / cut / confirm / pin / refusal / apology); canned safety constants
from the brain are recognised and gated even when they arrive as a plain reply.
voice/emotion.py decides whether the line may carry the mood; this module then
applies it: Fish gets an inline tag, OpenAI TTS gets tone instructions (a shared
option, so after any flat line the tone stays neutral until the session is back to
listening — release()), Cartesia gets clean text. Failures fall back to flat speech.
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
        from brain.nodes.ops import TOOL_FAILED

        self._failed_prefix = TOOL_FAILED.split("{}")[0]  # dynamic tool-failure apology
        self._hold = False  # a gated line may still be synthesizing: stay flat until release()

    def kind_of(self, text: str, default: str = "reply") -> str:
        t = text.strip()
        return "apology" if t.startswith(self._failed_prefix) else self._gated.get(t, default)

    def release(self) -> None:
        """The session went back to listening: gated speech has finished playing."""
        self._hold = False

    def line(self, text: str, kind: str = "reply") -> str:
        try:
            provider = self._provider()
            style = None
            kind = self.kind_of(text, kind)
            if kind not in emotion.STYLED_KINDS:
                # OpenAI tone is a SHARED option applied at synthesis time: once a flat line
                # is queued, keep everything flat until it has played (fail toward flat).
                self._hold = True
            elif self._enabled and not self._hold:
                named, intensity, concern = self._mood_now()
                style = emotion.style_for(named, intensity, concern=concern, kind=kind)
            if provider == "openai" and self._tts is not None:
                self._tts.update_options(instructions=emotion.instructions_for(style))
            return emotion.decorate(text, style, provider)
        except Exception:
            log.warning("styling failed — speaking flat", exc_info=True)
            return emotion.decorate(text, None, "cartesia")
