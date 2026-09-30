"""friday · voice/emotion.py

Mood -> voice, with a SAFETY GATE. Pure functions, no I/O: the voice agent asks
style_for() what a spoken line may sound like, then decorate() prepares the
text for the active TTS engine and instructions_for() gives OpenAI TTS its tone.

Gate (tests/unit/test_emotion.py, written first): only ordinary replies,
greetings and check-ins are styled. Kill/stand-down, cuts, confirmations, PIN
requests, refusals and apologies stay flat and tag-free — and so does
everything while sir is stressed (concern >= 0.7). Fish Audio S1 renders an
inline tag like "(worried)"; OpenAI gpt-4o-mini-tts takes tone instructions;
Cartesia never receives a tag.
"""

import re
from dataclasses import dataclass

STYLED_KINDS = frozenset({"reply", "greeting", "checkin"})
STRESS_CONCERN = 0.7
NEUTRAL_INSTRUCTIONS = ("Speak as a composed British assistant: clear, calm, even and "
                        "unhurried. No added emotion.")
_TAG = re.compile(r"^\s*\([a-z ]{2,24}\)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class Style:
    tag: str  # Fish Audio S1 inline emotion marker
    instructions: str  # OpenAI TTS tone


_STYLES = {
    "proud": Style("(proud)", "Quietly proud and warm, composed; a faint smile in the voice."),
    "delighted": Style("(delighted)", "Genuinely pleased and bright, still dignified."),
    "worried": Style("(worried)", "Gently concerned and caring; softer, a touch slower."),
    "protective": Style("(serious)", "Calm, firm and protective; steady and reassuring."),
    "sheepish": Style("(embarrassed)", "Slightly sheepish and apologetic, but composed."),
    "irritated": Style("(sighing)", "Crisp and a little clipped; polite, never rude."),
    "weary": Style("(soft tone)", "Soft and low-key, late-night quiet; gentle warmth."),
    "content": Style("(relaxed)", "Relaxed and warm, easy-going, softly amused."),
}


def style_for(named: str, intensity: float, *, concern: float, kind: str) -> Style | None:
    """The style a line may carry, or None (flat). Unknown kinds count as unsafe."""
    if kind not in STYLED_KINDS or concern >= STRESS_CONCERN or intensity <= 0:
        return None
    return _STYLES.get(named)


def decorate(text: str, style: Style | None, provider: str) -> str:
    """Text ready for the TTS engine: Fish gets the tag on the first chunk; every
    other engine gets any stray leading tag stripped (never read aloud)."""
    if provider == "fishaudio":
        return f"{style.tag} {text}" if style else text
    return _TAG.sub("", text, count=1)


def instructions_for(style: Style | None) -> str:
    return style.instructions if style else NEUTRAL_INSTRUCTIONS
