"""voice/agent.py — persona loading, brain-backed llm_node, Phase 3 kill path:
local intents short-circuit BEFORE the graph, watchdog ends silent sessions."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from config.settings import get_settings
from voice.agent import JarvisAgent, build_instructions


def test_instructions_load_persona() -> None:
    text = build_instructions()
    assert "friday" in text.lower()  # the persona file rode along
    assert '"sir"' in text


def test_instructions_contain_three_sentence_cap() -> None:
    # The cap is the contract; the wording belongs to Lohith's persona file.
    assert re.search(r"(three spoken sentences|<=?\s*3 sentences)",
                     build_instructions().lower())


class FakeBrain:
    """A non-streaming route (vault/ops-style): the whole reply arrives in updates."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    async def astream(self, state, config, *, stream_mode=None):
        self.calls.append((state, config))
        yield "updates", {"chat": {"reply": "Indeed, sir.", "route": "chat", "messages": []}}


def _ctx(*items: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(items=list(items))


async def test_llm_node_speaks_the_graph_reply() -> None:
    brain = FakeBrain()
    agent = JarvisAgent(brain, thread_id="console")
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
    agent = JarvisAgent(brain, thread_id="console")
    ctx = _ctx(
        SimpleNamespace(role="user", text_content="old question"),
        SimpleNamespace(role="assistant", text_content="answered"),
        SimpleNamespace(role="user", text_content="new question"),
    )
    _ = [c async for c in agent.llm_node(ctx, [], None)]
    assert brain.calls[0][0]["messages"][0]["content"] == "new question"


async def test_llm_node_without_user_message_stays_silent() -> None:
    brain = FakeBrain()
    agent = JarvisAgent(brain, thread_id="console")
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
    agent = JarvisAgent(StreamingBrain(), thread_id="console")
    ctx = _ctx(SimpleNamespace(role="user", text_content="hello"))
    chunks = [c async for c in agent.llm_node(ctx, [], None)]
    assert chunks == ["In", "deed, ", "sir."]  # spoken token-by-token, not one blob at the end


# --- Phase 3: local intents run BEFORE the graph ---


@pytest.fixture
def control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "stand_down"
    monkeypatch.setenv("STAND_DOWN_FILE", str(path))
    monkeypatch.setenv("CAMERA_OFF_FILE", str(tmp_path / "camera_off"))
    monkeypatch.setenv("SCREEN_OFF_FILE", str(tmp_path / "screen_off"))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def _user(text: str) -> SimpleNamespace:
    return SimpleNamespace(role="user", text_content=text)


async def _speak(agent: JarvisAgent, text: str) -> list[str]:
    return [c async for c in agent.llm_node(_ctx(_user(text)), [], None)]


async def test_stand_down_short_circuits_graph_and_signals_daemon(control: Path) -> None:
    brain = FakeBrain()
    agent = JarvisAgent(brain, thread_id="console")
    assert await _speak(agent, "Friday, stand down.") == ["Standing down, sir."]
    assert brain.calls == []  # kill phrases never reach the LLM
    assert control.exists()


async def test_camera_off_cuts_offline_no_graph(control: Path) -> None:
    brain = FakeBrain()
    agent = JarvisAgent(brain, thread_id="console")
    assert await _speak(agent, "camera off") == ["Camera disabled, sir."]
    assert brain.calls == []
    assert not control.exists()  # capture cuts do not end the session
    assert get_settings().camera_off_file and Path(get_settings().camera_off_file).exists()


async def test_resume_clears_camera_cut(control: Path) -> None:
    agent = JarvisAgent(FakeBrain(), thread_id="console")
    await _speak(agent, "camera off")
    assert await _speak(agent, "resume") == ["At your service, sir."]
    assert not Path(get_settings().camera_off_file).exists()


async def test_mute_then_silent_then_resume(control: Path) -> None:
    brain = FakeBrain()
    agent = JarvisAgent(brain, thread_id="console")
    assert await _speak(agent, "mute yourself") == []
    assert await _speak(agent, "what did I quote Receivly?") == []  # muted: no graph, no speech
    assert brain.calls == []
    assert await _speak(agent, "resume") == ["At your service, sir."]
    assert await _speak(agent, "what did I quote Receivly?") == ["Indeed, sir."]
    assert len(brain.calls) == 1


async def test_normal_turn_updates_activity(control: Path) -> None:
    agent = JarvisAgent(FakeBrain(), thread_id="console")
    agent.last_activity = 0.0
    await _speak(agent, "hello")
    assert agent.last_activity > 0.0


# --- Phase 4: confirm-gate interrupt round trip ---


class InterruptingBrain:
    """First real turn interrupts with a question; a Command(resume=...) completes."""

    def __init__(self) -> None:
        self.payloads: list = []

    async def astream(self, payload, config, *, stream_mode=None):
        self.payloads.append(payload)
        from langgraph.types import Command

        if isinstance(payload, Command):
            yield "updates", {"ops_execute": {
                "reply": "Done, sir. content_pipeline has run.", "messages": []}}
        else:
            yield "updates", {"__interrupt__": (
                SimpleNamespace(
                    value={"question": "That will run content_pipeline. Shall I proceed, sir?"}),
            )}


async def test_interrupt_speaks_question_then_resumes_with_answer(control: Path) -> None:
    from langgraph.types import Command

    brain = InterruptingBrain()
    agent = JarvisAgent(brain, thread_id="console")
    assert await _speak(agent, "run my content pipeline") == [
        "That will run content_pipeline. Shall I proceed, sir?"
    ]
    assert agent.pending_confirm is True
    assert await _speak(agent, "yes, go ahead") == ["Done, sir. content_pipeline has run."]
    assert agent.pending_confirm is False
    resume = brain.payloads[1]
    assert isinstance(resume, Command) and resume.resume == "yes, go ahead"


async def test_stand_down_wins_over_pending_confirm(control: Path) -> None:
    brain = InterruptingBrain()
    agent = JarvisAgent(brain, thread_id="console")
    await _speak(agent, "run my content pipeline")  # gate parked
    assert await _speak(agent, "stand down") == ["Standing down, sir."]
    assert len(brain.payloads) == 1  # the kill never touched the graph
    assert control.exists()


# silence-watchdog tests live in test_watchdog.py
