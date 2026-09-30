"""voice/agent.py — persona loading, brain-backed llm_node, Phase 3 kill path:
local intents short-circuit BEFORE the graph, watchdog ends silent sessions."""

import re
from types import SimpleNamespace

from tests.fakes import FakeBrain
from voice.agent import FridayAgent, build_instructions


def test_instructions_load_persona() -> None:
    text = build_instructions()
    assert "friday" in text.lower()  # the persona file rode along
    assert '"sir"' in text


def test_instructions_contain_three_sentence_cap() -> None:
    # The cap is the contract; the wording belongs to Lohith's persona file.
    assert re.search(r"(three spoken sentences|<=?\s*3 sentences)",
                     build_instructions().lower())


def _ctx(*items: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(items=list(items))


async def test_llm_node_speaks_the_graph_reply() -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    ctx = _ctx(
        SimpleNamespace(role="assistant", text_content="At your service, sir."),
        SimpleNamespace(role="user", text_content="what did I quote Receivly?"),
    )
    chunks = [c async for c in agent.llm_node(ctx, [], None)]
    assert chunks == ["Indeed, sir."]
    state, config = brain.calls[0]
    assert state["messages"] == [{"role": "user", "content": "what did I quote Receivly?"}]
    assert config["configurable"]["thread_id"] == "console"


async def test_llm_node_uses_latest_user_message() -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    ctx = _ctx(
        SimpleNamespace(role="user", text_content="old question"),
        SimpleNamespace(role="assistant", text_content="answered"),
        SimpleNamespace(role="user", text_content="new question"),
    )
    _ = [c async for c in agent.llm_node(ctx, [], None)]
    assert brain.calls[0][0]["messages"][0]["content"] == "new question"


async def test_llm_node_without_user_message_stays_silent() -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    assert [c async for c in agent.llm_node(_ctx(), [], None)] == []
    assert brain.calls == []


class StreamingBrain:
    """A streaming route (chat): reply tokens arrive as custom chunks."""

    async def astream(self, payload, config, *, stream_mode=None):
        assert config["configurable"]["stream_tokens"] is True  # voice asked for tokens
        for tok in ["In", "deed, ", "sir."]:
            yield "custom", tok
        yield "updates", {"chat": {"reply": "Indeed, sir."}}


async def test_llm_node_streams_reply_tokens_as_they_arrive() -> None:
    agent = FridayAgent(StreamingBrain(), thread_id="console")
    ctx = _ctx(SimpleNamespace(role="user", text_content="hello"))
    chunks = [c async for c in agent.llm_node(ctx, [], None)]
    assert chunks == ["In", "deed, ", "sir."]  # spoken token-by-token, not one blob at the end
