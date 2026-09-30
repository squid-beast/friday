"""friday · tests/unit/test_styling.py

voice/styling.Styler + the agent + adapters/tts: with Fish active and a
delighted mood, ordinary replies carry ONE tag on the first chunk while the
stand-down, confirm/PIN questions and canned refusals/apologies stay flat;
OpenAI TTS gets tone instructions (neutral for gated lines); Cartesia never
sees a tag; the TTS factory honours TTS_PROVIDER and fails loudly on keys.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from brain.nodes.ops import PIN_REFUSED
from config.settings import get_settings
from voice.agent import FridayAgent
from voice.emotion import NEUTRAL_INSTRUCTIONS
from voice.styling import Styler


def _styler(provider: str, tts=None, mood=("delighted", 0.8, 0.1)) -> Styler:
    return Styler(tts, provider=lambda: provider, mood_now=lambda: mood, enabled=True)


def test_fish_reply_is_tagged_but_safety_lines_are_flat() -> None:
    s = _styler("fishaudio")
    assert s.line("Well done, sir.", "reply") == "(delighted) Well done, sir."
    assert s.line("Standing down, sir.", "kill") == "Standing down, sir."
    assert s.line("That will run x. Shall I proceed, sir?", "confirm").startswith("That")
    assert s.line(PIN_REFUSED, "reply") == PIN_REFUSED  # canned refusal gated by its text


def test_openai_gets_tone_then_neutral_for_gated_lines() -> None:
    tts = MagicMock()
    s = _styler("openai", tts)
    assert s.line("Well done, sir.", "greeting") == "Well done, sir."  # no tag in the text
    warm = tts.update_options.call_args.kwargs["instructions"]
    assert warm != NEUTRAL_INSTRUCTIONS
    s.line("Standing down, sir.", "kill")
    assert tts.update_options.call_args.kwargs["instructions"] == NEUTRAL_INSTRUCTIONS


def test_stress_and_disabled_emotion_speak_flat() -> None:
    assert _styler("fishaudio", mood=("worried", 0.9, 0.9)).line("Hm.", "reply") == "Hm."
    off = Styler(None, provider=lambda: "fishaudio", mood_now=lambda: ("proud", 1, 0),
                 enabled=False)
    assert off.line("Done, sir.", "reply") == "Done, sir."


def test_a_broken_mood_never_breaks_speech() -> None:
    def boom():
        raise RuntimeError("mood file corrupt")

    s = Styler(None, provider=lambda: "fishaudio", mood_now=boom, enabled=True)
    assert s.line("(happy) Hello, sir.", "reply") == "Hello, sir."  # flat + stray tag stripped


class _Brain:
    def __init__(self, *chunks) -> None:
        self._chunks = chunks

    async def astream(self, payload, config, *, stream_mode=None):
        for chunk in self._chunks:
            yield chunk


def _ctx(text: str) -> SimpleNamespace:
    return SimpleNamespace(items=[SimpleNamespace(role="user", text_content=text)])


async def _say(agent: FridayAgent, text: str) -> list[str]:
    return [c async for c in agent.llm_node(_ctx(text), [], None)]


async def test_agent_tags_only_the_first_streamed_token() -> None:
    brain = _Brain(("custom", "Well"), ("custom", " done, sir."), ("updates", {}))
    agent = FridayAgent(brain, "t", styler=_styler("fishaudio"), sense=lambda: None)
    assert await _say(agent, "how did it go?") == ["(delighted) Well", " done, sir."]


async def test_agent_confirm_question_and_stand_down_stay_flat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STAND_DOWN_FILE", str(tmp_path / "stand_down"))
    get_settings.cache_clear()
    question = SimpleNamespace(value={"question": "That will run x. Shall I proceed, sir?"})
    agent = FridayAgent(_Brain(("updates", {"__interrupt__": (question,)})), "t",
                        styler=_styler("fishaudio"), sense=lambda: None)
    assert await _say(agent, "run x") == ["That will run x. Shall I proceed, sir?"]
    assert await _say(agent, "stand down") == ["Standing down, sir."]
    get_settings.cache_clear()


@pytest.mark.parametrize(("provider", "env", "message"), [
    ("openai", {}, "OPENAI_API_KEY not set"),
    ("fishaudio", {}, "FISH_API_KEY not set"),
    ("fishaudio", {"FISH_API_KEY": "f"}, "FISH_VOICE_ID not set"),
    ("elevenlabs", {}, "unknown TTS_PROVIDER"),
])
def test_tts_factory_fails_loudly(monkeypatch, provider, env, message) -> None:
    from adapters.tts import get_tts

    monkeypatch.setenv("TTS_PROVIDER", provider)
    for k in ("OPENAI_API_KEY", "FISH_API_KEY", "FISH_VOICE_ID"):
        monkeypatch.setenv(k, env.get(k, ""))
    get_settings.cache_clear()
    with pytest.raises(ValueError, match=message):
        get_tts()
    get_settings.cache_clear()


def test_tts_factory_builds_openai_and_fish(monkeypatch) -> None:
    from livekit.plugins import fishaudio
    from livekit.plugins import openai as openai_plugin

    from adapters.tts import get_tts

    monkeypatch.setattr(openai_plugin, "TTS", MagicMock(name="oai"))
    monkeypatch.setattr(fishaudio, "TTS", MagicMock(name="fish"))
    monkeypatch.setenv("TTS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-t")
    get_settings.cache_clear()
    get_tts()
    kw = openai_plugin.TTS.call_args.kwargs
    assert kw["model"] == "gpt-4o-mini-tts" and kw["instructions"] == NEUTRAL_INSTRUCTIONS
    monkeypatch.setenv("TTS_PROVIDER", "fishaudio")
    monkeypatch.setenv("FISH_API_KEY", "f-k")
    monkeypatch.setenv("FISH_VOICE_ID", "voice-1")
    get_settings.cache_clear()
    get_tts()
    assert fishaudio.TTS.call_args.kwargs == {"api_key": "f-k", "model": "s1",
                                              "voice_id": "voice-1"}
    get_settings.cache_clear()


def test_dynamic_tool_failure_apology_is_flat() -> None:
    from brain.nodes.ops import TOOL_FAILED

    line = TOOL_FAILED.format("send_summary")
    assert _styler("fishaudio", mood=("proud", 0.9, 0.1)).line(line, "reply") == line


def test_openai_tone_stays_neutral_until_gated_speech_has_played() -> None:
    tts = MagicMock()
    s = _styler("openai", tts)
    s.line("That will run x. Shall I proceed, sir?", "confirm")  # still synthesizing...
    s.line("How did you sleep, sir?", "checkin")  # ...prepared meanwhile
    assert tts.update_options.call_args.kwargs["instructions"] == NEUTRAL_INSTRUCTIONS
    s.release()  # back to listening
    s.line("How did you sleep, sir?", "checkin")
    assert tts.update_options.call_args.kwargs["instructions"] != NEUTRAL_INSTRUCTIONS
