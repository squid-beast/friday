"""friday · tests/unit/test_emotion.py — SAFETY GATE (written before the code)

Emotion may color ordinary replies, greetings and check-ins. It must NEVER
color a kill/stand-down, a camera/screen cut, a confirmation question, a PIN
request, a refusal or an apology — and never when sir is stressed (concern
high): those lines stay flat and tag-free. Fish renders inline tags, OpenAI
takes tone instructions, Cartesia never sees a tag.
"""

import pytest

from voice import emotion

GATED = ("kill", "cut", "confirm", "pin", "refusal", "apology")


@pytest.mark.parametrize("kind", GATED)
def test_safety_lines_are_never_styled(kind: str) -> None:
    assert emotion.style_for("delighted", 0.9, concern=0.1, kind=kind) is None


@pytest.mark.parametrize("kind", ("reply", "greeting", "checkin"))
def test_ordinary_lines_carry_the_mood(kind: str) -> None:
    style = emotion.style_for("proud", 0.6, concern=0.2, kind=kind)
    assert style is not None and style.tag.startswith("(") and style.instructions


def test_stress_suppresses_emotion_everywhere() -> None:
    assert emotion.style_for("delighted", 0.9, concern=0.75, kind="reply") is None


def test_unknown_kind_is_treated_as_unsafe() -> None:
    assert emotion.style_for("content", 0.5, concern=0.1, kind="mystery") is None


def test_fish_gets_one_tag_on_the_first_chunk_only() -> None:
    style = emotion.style_for("worried", 0.7, concern=0.5, kind="reply")
    assert emotion.decorate("You skipped sleep, sir.", style, "fishaudio") == (
        f"{style.tag} You skipped sleep, sir.")
    assert emotion.decorate("Standing down, sir.", None, "fishaudio") == "Standing down, sir."


@pytest.mark.parametrize("provider", ("cartesia", "openai"))
def test_other_providers_never_receive_tags(provider: str) -> None:
    style = emotion.style_for("delighted", 0.8, concern=0.1, kind="reply")
    assert emotion.decorate("Well done, sir.", style, provider) == "Well done, sir."
    # and a stray tag the model emitted is stripped before a tagless engine reads it
    assert emotion.decorate("(happy) Well done, sir.", None, provider) == "Well done, sir."


def test_openai_tone_is_neutral_for_gated_lines() -> None:
    assert emotion.instructions_for(None) == emotion.NEUTRAL_INSTRUCTIONS
    warm = emotion.style_for("content", 0.5, concern=0.1, kind="greeting")
    assert emotion.instructions_for(warm) != emotion.NEUTRAL_INSTRUCTIONS
