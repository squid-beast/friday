"""friday · tests/unit/test_local_intents.py

Kill/capture phrase matcher (TDD — written before client/local_intents.py).
Every kill phrase + near-misses that must NOT trigger.

Direction rules: intents that REDUCE capability (stand down, camera off, mute)
match by containment — firing too eagerly is the safe failure. Intents that
RESTORE capability (resume/unmute) and bare one-word kills ("dismissed") match
only as the standalone utterance — re-activation must be deliberate.
"""

import pytest

from client.local_intents import Intent, match

# --- kill/capture phrases fire, with punctuation/case/embedding noise ---


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("stand down", Intent.STAND_DOWN),
        ("Friday, stand down.", Intent.STAND_DOWN),
        ("STAND DOWN", Intent.STAND_DOWN),
        ("please stand down now", Intent.STAND_DOWN),
        ("go to sleep", Intent.STAND_DOWN),
        ("that will be all", Intent.STAND_DOWN),
        ("that will be all for tonight, thank you", Intent.STAND_DOWN),
        ("Dismissed.", Intent.STAND_DOWN),  # standalone command form
        ("camera off", Intent.CAMERA_OFF),
        ("turn off the camera", Intent.CAMERA_OFF),
        ("stop looking", Intent.CAMERA_OFF),
        ("stop looking at me", Intent.CAMERA_OFF),
        ("stop watching my screen", Intent.SCREEN_OFF),
        ("screen off", Intent.SCREEN_OFF),
        ("stop screen recording", Intent.SCREEN_OFF),
        ("mute yourself", Intent.MUTE),
        ("be quiet", Intent.MUTE),
        ("Resume.", Intent.RESUME),  # standalone only
        ("as you were", Intent.RESUME),
        ("unmute", Intent.RESUME),
    ],
)
def test_phrases_fire(text: str, intent: Intent) -> None:
    assert match(text) is intent


# --- near-misses that must NOT trigger ---


@pytest.mark.parametrize(
    "text",
    [
        "standing ovation",
        "I understand downloading takes time",  # 'stand down' hidden inside words
        "stand by for the update",
        "the camera is off already",  # statement, not command
        "my screen is off",
        "shut down the computer",
        "what a beautiful sleepy morning",
        "he was dismissed from the meeting",  # bare kills are standalone-only
        "resume the workflow",  # RESUME is standalone-only: no accidental re-activation
        "the resume is on my desk",
        "",
        "   ",
        "hello there",
    ],
)
def test_near_misses_do_not_trigger(text: str) -> None:
    assert match(text) is None


# Safe-direction false positive, documented on purpose: killing too eagerly
# is the acceptable failure mode for capability-REDUCING intents.
def test_safe_direction_false_positive_is_deliberate() -> None:
    assert match("I should go to sleep soon") is Intent.STAND_DOWN


# --- priority: a kill phrase beats every other intent in the same utterance ---


def test_stand_down_wins_over_other_intents() -> None:
    assert match("camera off and then stand down") is Intent.STAND_DOWN
    assert match("stand down and mute yourself") is Intent.STAND_DOWN


def test_match_is_pure_text_no_network_modules() -> None:
    """Fresh interpreter: importing the matcher must pull in zero network stacks."""
    import subprocess
    import sys

    code = (
        "import sys, client.local_intents\n"
        "banned = ('httpx', 'anthropic', 'livekit', 'deepgram', 'cartesia', 'websockets')\n"
        "hit = [m for m in sys.modules if m.split('.')[0] in banned]\n"
        "assert not hit, hit\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=30)
