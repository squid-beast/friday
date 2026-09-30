"""friday · tests/unit/test_pending_question.py

A question Friday asked (wake check-in, proactive nudge) is remembered for a
short while so sir's ANSWER is always stored — even "pretty rough, slept four
hours" that the per-turn fact gate would otherwise skip. Taken once, expires.
"""

from pathlib import Path

import pytest

from brain import pending_question
from brain.nodes.memory_writer import drain, memory_writer_node
from brain.state import FridayState
from config.settings import get_settings
from tests.fakes import FakeLLM, FakeMemory


@pytest.fixture(autouse=True)
def _file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PENDING_QUESTION_FILE", str(tmp_path / "pending.json"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_mark_then_take_once() -> None:
    pending_question.mark("How did you sleep, sir?")
    assert pending_question.take() == "How did you sleep, sir?"
    assert pending_question.take() == ""  # consumed


def test_stale_question_expires() -> None:
    pending_question.mark("How did you sleep, sir?", now=1_000.0)
    assert pending_question.take(now=1_000.0 + 3600) == ""


async def test_answer_to_a_checkin_is_always_extracted() -> None:
    pending_question.mark("How did you sleep, sir?")
    llm = FakeLLM(["Sir slept badly — about four hours"])
    mem = FakeMemory()
    state = FridayState(messages=[{"role": "user", "content": "pretty rough, honestly"}])
    await memory_writer_node(state, think=llm.think, remember=mem.remember)
    await drain()
    assert mem.stored == ["Sir slept badly — about four hours"]
    assert 'Friday asked: "How did you sleep, sir?"' in llm.calls[0]["prompt"]


async def test_small_talk_without_a_question_is_still_skipped() -> None:
    llm = FakeLLM([])  # any call would fail loudly
    state = FridayState(messages=[{"role": "user", "content": "pretty rough, honestly"}])
    await memory_writer_node(state, think=llm.think, remember=FakeMemory().remember)
    await drain()
