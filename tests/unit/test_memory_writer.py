"""friday · tests/unit/test_memory_writer.py

memory_writer node with fakes: fire-and-forget fact extraction, the cheap
fact-hint gate in front of the LLM call, failures that never raise.
"""

from brain.nodes.memory_writer import drain, memory_writer_node
from brain.state import FridayState
from tests.fakes import BrokenLLM, FakeLLM, FakeMemory


def _state(utterance: str) -> FridayState:
    return FridayState(messages=[{"role": "user", "content": utterance}])


# --- memory_writer ---


async def test_extracts_and_stores_facts() -> None:
    llm = FakeLLM(["Sir's gym locker code is 4242\nSir prefers morning workouts"])
    mem = FakeMemory()
    assert await memory_writer_node(
        _state("remember my gym locker code is 4242, I go mornings"),
        think=llm.think,
        remember=mem.remember,
    ) == {}
    await drain()
    assert mem.stored == ["Sir's gym locker code is 4242", "Sir prefers morning workouts"]


async def test_none_stores_nothing() -> None:
    mem = FakeMemory()
    # "i like" passes the gate; the model still judges it small talk -> NONE
    await memory_writer_node(_state("i like a bit of banter in the morning"),
                             think=FakeLLM(["NONE"]).think, remember=mem.remember)
    await drain()
    assert mem.stored == []


async def test_extraction_failure_never_raises() -> None:
    mem = FakeMemory()
    await memory_writer_node(_state("remember this"), think=BrokenLLM().think,
                             remember=mem.remember)
    await drain()
    assert mem.stored == []


async def test_no_utterance_schedules_nothing() -> None:
    llm = FakeLLM([])
    assert await memory_writer_node(FridayState(), think=llm.think,
                                    remember=FakeMemory().remember) == {}
    await drain()
    assert llm.calls == []


async def test_fact_free_turn_skips_extraction() -> None:
    llm = FakeLLM([])
    mem = FakeMemory()
    await memory_writer_node(
        _state("what's the weather looking today, friday"), think=llm.think, remember=mem.remember
    )
    await drain()
    assert llm.calls == []  # no fact hint -> no LLM call at all
    assert mem.stored == []


async def test_fact_hint_without_remember_still_extracts() -> None:
    llm = FakeLLM(["Sir takes his coffee black"])
    mem = FakeMemory()
    await memory_writer_node(_state("i like my coffee black"), think=llm.think,
                             remember=mem.remember)
    await drain()
    assert mem.stored == ["Sir takes his coffee black"]


async def test_digits_pass_the_extraction_gate() -> None:
    llm = FakeLLM(["Sir's door code is 4242"])
    mem = FakeMemory()
    await memory_writer_node(_state("the door code is 4242"), think=llm.think,
                             remember=mem.remember)
    await drain()
    assert mem.stored == ["Sir's door code is 4242"]
