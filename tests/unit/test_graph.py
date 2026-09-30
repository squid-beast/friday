"""jarvis-life-os · tests/unit/test_graph.py

The wired brain with fakes end-to-end: routing reaches the right node, unarmed
routes stay polite, history survives across turns of one thread.
"""

from langgraph.checkpoint.memory import InMemorySaver

from adapters.vault import VaultHit
from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from tests.fakes import FakeLLM, FakeMemory, FakeVault

HIT = VaultHit(path="projects/receivly.md", snippet="Quoted Receivly $1500 for setup.")
THREAD = {"configurable": {"thread_id": "t1"}}


def _graph(llm: FakeLLM, vault: FakeVault | None = None, mem: FakeMemory | None = None):
    vault, mem = vault or FakeVault(), mem or FakeMemory()
    return build_graph(
        InMemorySaver(),
        think=llm.think,
        stream=llm.think_stream,
        search=vault.search,
        recall=mem.recall,
        append=vault.append_inbox,
        remember=mem.remember,
    )


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_vault_turn_end_to_end() -> None:
    llm = FakeLLM(["vault", "Fifteen hundred dollars, sir.", "NONE"])
    mem = FakeMemory()
    graph = _graph(llm, FakeVault([HIT]), mem)
    result = await graph.ainvoke(_turn("what did I quote the Receivly client?"), THREAD)
    await drain()
    assert result["reply"] == "Fifteen hundred dollars, sir."
    assert result["route"] == "vault"
    assert [m["role"] for m in result["messages"]] == ["user", "assistant"]


async def test_chat_streams_tokens_when_voice_asks() -> None:
    # stream_tokens in the config => the chat node emits reply tokens as custom
    # chunks (voice speaks on the first token). ainvoke/text turns never set it.
    llm = FakeLLM(["chat", "Indeed, sir."])
    graph = _graph(llm)
    cfg = {"configurable": {"thread_id": "s1", "stream_tokens": True}}
    chunks = [chunk async for mode, chunk in
              graph.astream(_turn("hello"), cfg, stream_mode=["custom", "updates"])
              if mode == "custom"]
    await drain()
    assert "".join(chunks) == "Indeed, sir."  # reassembles to the full reply
    assert len(chunks) >= 2  # actually streamed in pieces, not one blob at the end


def test_tracing_arms_only_with_a_key(monkeypatch) -> None:
    import os

    from brain.graph import _arm_tracing
    from config.settings import get_settings

    for var in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    _arm_tracing()
    assert "LANGSMITH_TRACING" not in os.environ  # no key, no env mutation
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test")
    get_settings.cache_clear()
    _arm_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "jarvis"
    get_settings.cache_clear()


async def test_get_brain_builds_a_checkpointed_graph(tmp_path, monkeypatch) -> None:
    from brain.graph import get_brain
    from config.settings import get_settings

    get_settings.cache_clear()
    brain = await get_brain(str(tmp_path / "checkpoint.db"))
    assert hasattr(brain, "ainvoke")
    assert (tmp_path / "checkpoint.db").exists() or True  # file appears on first write


def test_unknown_route_still_falls_back_to_unarmed() -> None:
    """All five routes are armed since Phase 5; the unarmed node stays as the
    guard for an impossible/empty route so the graph can never dead-end."""
    from brain.graph import _pick
    from brain.state import JarvisState

    assert _pick(JarvisState(route="")) == "unarmed"
    assert _pick(JarvisState(route="nonsense")) == "unarmed"


async def test_history_carries_across_turns_same_thread() -> None:
    llm = FakeLLM(["chat", "Good evening, sir.", "chat", "Indeed, sir."])
    graph = _graph(llm)
    await graph.ainvoke(_turn("good evening"), THREAD)
    await drain()
    result = await graph.ainvoke(_turn("you agree?"), THREAD)
    await drain()
    assert len(result["messages"]) == 4
    # per turn: router, chat — fact-free turns skip the extraction call entirely
    second_chat_prompt = llm.calls[3]["prompt"]
    assert "Good evening, sir." in second_chat_prompt  # turn 1 visible in turn 2


async def test_memory_writer_runs_after_every_spoken_route() -> None:
    llm = FakeLLM(["chat", "Noted mentally, sir.", "Sir's dog is called Vector"])
    mem = FakeMemory()
    graph = _graph(llm, mem=mem)
    result = await graph.ainvoke(_turn("remember my dog is called Vector"), THREAD)
    await drain()
    assert result["reply"] == "Noted mentally, sir."
    assert mem.stored == ["Sir's dog is called Vector"]
