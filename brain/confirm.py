"""friday · brain/confirm.py

The spoken gates for risky tools, via LangGraph interrupt(). Strict by design:
- confirm (risk=confirm): explicit affirmative only; negation ANYWHERE wins.
- PIN (risk=pin): the extracted digit string must EQUAL the PIN — containment
  would let "4242 wait no 4243" through — and negation vetoes even a correct
  code. The digits are compared here and never logged anywhere.
Everything ambiguous is a no.
"""

import re

from langgraph.types import interrupt

from config.settings import get_settings

_AFFIRM = (
    "yes", "yeah", "yep", "go ahead", "do it", "proceed",
    "sure", "affirmative", "confirmed", "absolutely", "please do",
)
_NEGATE = (
    "no", "nope", "not", "don t", "do not", "stop", "cancel",
    "wait", "hold", "never mind", "nevermind",
)
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _has_negation(normalized: str) -> bool:
    padded = f" {normalized} "
    return any(f" {phrase} " in padded for phrase in _NEGATE)


def is_spoken_yes(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized or _has_negation(normalized):
        return False
    padded = f" {normalized} "
    return any(f" {phrase} " in padded for phrase in _AFFIRM)


def spoken_digits(text: str) -> str:
    """All digits in the utterance, word-digits included: 'four two 42' -> '4242'."""
    out = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _DIGIT_WORDS:
            out.append(_DIGIT_WORDS[word])
        elif word.isdigit():
            out.append(word)
    return "".join(out)


def is_spoken_pin(text: str, pin: str) -> bool:
    if not pin or _has_negation(_normalize(text)):
        return False
    return spoken_digits(text) == pin


def ask_confirmation(question: str) -> bool:
    """Pause the graph, speak the question, resume on sir's next utterance."""
    answer = interrupt({"question": question})
    return is_spoken_yes(str(answer))


def ask_pin(question: str) -> bool:
    """Same pause, but only the exact spoken PIN opens the gate."""
    answer = interrupt({"question": question})
    return is_spoken_pin(str(answer), get_settings().friday_pin)
