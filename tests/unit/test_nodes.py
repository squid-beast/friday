"""jarvis-life-os · tests/unit/test_nodes.py

chat, vault, and memory_writer nodes with fakes: reply shape, grounding
context, apology fallbacks, note-taking, fire-and-forget extraction.
"""

from adapters.vault import VaultHit
from brain.nodes.chat import LLM_APOLOGY, chat_node
from brain.nodes.memory_writer import drain, memory_writer_node
from brain.nodes.vault import NOTED, NOTHING_FOUND, VAULT_APOLOGY, vault_node
from brain.state import JarvisState
from tests.fakes import BrokenLLM, FakeLLM, FakeMemory, FakeVault

HIT = VaultHit(path="projects/receivly.md", snippet="Quoted Receivly $1500 for setup.")


def _state(utterance: str) -> JarvisState:
    return JarvisState(messages=[{"role": "user", "content": utterance}])


# --- chat ---


async def test_chat_replies_in_persona_with_history() -> None:
    llm = FakeLLM(["Good evening, sir."])
    state = JarvisState(
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "At your service, sir."},
            {"role": "user", "content": "good evening"},
        ]
    )
    out = await chat_node(state, think=llm.think)
    assert out["reply"] == "Good evening, sir."
    assert out["messages"] == [{"role": "assistant", "content": "Good evening, sir."}]
    assert "friday" in llm.calls[0]["system"].lower()  # persona rides along
    assert "At your service, sir." in llm.calls[0]["prompt"]  # history rides along


async def test_chat_llm_down_still_speaks() -> None:
    out = await chat_node(_state("hello"), think=BrokenLLM().think)
    assert out["reply"] == LLM_APOLOGY


# --- vault: question path ---


async def test_vault_answer_grounded_in_hits_and_facts() -> None:
    llm = FakeLLM(["Fifteen hundred dollars, sir."])
    out = await vault_node(
        _state("what did I quote the Receivly client?"),
        think=llm.think,
        search=FakeVault([HIT]).search,
        recall=FakeMemory(["Sir's locker code is 4242"]).recall,
        append=FakeVault().append_inbox,
    )
    assert out["reply"] == "Fifteen hundred dollars, sir."
    prompt = llm.calls[0]["prompt"]
    assert "Quoted Receivly $1500" in prompt and "locker code is 4242" in prompt
    assert "ONLY the context" in prompt  # grounding instruction


async def test_vault_nothing_found_is_deterministic_no_llm() -> None:
    llm = FakeLLM([])
    out = await vault_node(
        _state("what about flurbles?"),
        think=llm.think,
        search=FakeVault().search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
    )
    assert out["reply"] == NOTHING_FOUND
    assert llm.calls == []


async def test_vault_both_stores_down_apologizes() -> None:
    async def boom(*a, **k):
        raise ConnectionError("down")

    out = await vault_node(
        _state("my notes?"),
        think=FakeLLM([]).think,
        search=boom,
        recall=boom,
        append=FakeVault().append_inbox,
    )
    assert out["reply"] == VAULT_APOLOGY


async def test_vault_one_store_down_still_answers() -> None:
    async def boom(*a, **k):
        raise ConnectionError("down")

    llm = FakeLLM(["From your notes: $1500, sir."])
    out = await vault_node(
        _state("Receivly quote?"), think=llm.think,
        search=FakeVault([HIT]).search, recall=boom, append=FakeVault().append_inbox,
    )
    assert out["reply"] == "From your notes: $1500, sir."


# --- vault: note-taking path ---


async def test_take_a_note_appends_to_inbox_no_llm() -> None:
    llm, vault = FakeLLM([]), FakeVault()
    out = await vault_node(
        _state("Take a note: follow up with the dentist lead on Friday"),
        think=llm.think, search=vault.search,
        recall=FakeMemory().recall, append=vault.append_inbox,
    )
    assert out["reply"] == NOTED
    assert vault.appended == ["follow up with the dentist lead on Friday"]
    assert llm.calls == []


async def test_empty_note_asks_instead_of_appending() -> None:
    vault = FakeVault()
    out = await vault_node(
        _state("take a note"),
        think=FakeLLM([]).think, search=vault.search,
        recall=FakeMemory().recall, append=vault.append_inbox,
    )
    assert "What shall I note" in out["reply"]
    assert vault.appended == []


async def test_note_append_failure_apologizes() -> None:
    def boom(text: str) -> str:
        raise OSError("vault gone")

    out = await vault_node(
        _state("note down buy more RAM"),
        think=FakeLLM([]).think, search=FakeVault().search,
        recall=FakeMemory().recall, append=boom,
    )
    assert out["reply"] == VAULT_APOLOGY


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
    assert await memory_writer_node(JarvisState(), think=llm.think,
                                    remember=FakeMemory().remember) == {}
    await drain()
    assert llm.calls == []


async def test_fact_free_turn_skips_extraction() -> None:
    llm = FakeLLM([])
    mem = FakeMemory()
    await memory_writer_node(
        _state("what's the weather looking today, jarvis"), think=llm.think, remember=mem.remember
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
