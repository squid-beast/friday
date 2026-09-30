"""friday · tests/unit/test_agent_intents.py

voice/agent.py Phase 3 kill path: local intents short-circuit BEFORE the graph
(stand down, camera/screen cuts, mute/resume) and win over a pending confirm.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from config.settings import get_settings
from tests.fakes import FakeBrain
from voice.agent import FridayAgent


def _ctx(*items: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(items=list(items))


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


async def _speak(agent: FridayAgent, text: str) -> list[str]:
    return [c async for c in agent.llm_node(_ctx(_user(text)), [], None)]


async def test_stand_down_short_circuits_graph_and_signals_daemon(control: Path) -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    assert await _speak(agent, "Friday, stand down.") == ["Standing down, sir."]
    assert brain.calls == []  # kill phrases never reach the LLM
    assert control.exists()


async def test_camera_off_cuts_offline_no_graph(control: Path) -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    assert await _speak(agent, "camera off") == ["Camera disabled, sir."]
    assert brain.calls == []
    assert not control.exists()  # capture cuts do not end the session
    assert get_settings().camera_off_file and Path(get_settings().camera_off_file).exists()


async def test_resume_clears_camera_cut(control: Path) -> None:
    agent = FridayAgent(FakeBrain(), thread_id="console")
    await _speak(agent, "camera off")
    assert await _speak(agent, "resume") == ["At your service, sir."]
    assert not Path(get_settings().camera_off_file).exists()


async def test_mute_then_silent_then_resume(control: Path) -> None:
    brain = FakeBrain()
    agent = FridayAgent(brain, thread_id="console")
    assert await _speak(agent, "mute yourself") == []
    assert await _speak(agent, "what did I quote Receivly?") == []  # muted: no graph, no speech
    assert brain.calls == []
    assert await _speak(agent, "resume") == ["At your service, sir."]
    assert await _speak(agent, "what did I quote Receivly?") == ["Indeed, sir."]
    assert len(brain.calls) == 1


async def test_normal_turn_updates_activity(control: Path) -> None:
    agent = FridayAgent(FakeBrain(), thread_id="console")
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
    agent = FridayAgent(brain, thread_id="console")
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
    agent = FridayAgent(brain, thread_id="console")
    await _speak(agent, "run my content pipeline")  # gate parked
    assert await _speak(agent, "stand down") == ["Standing down, sir."]
    assert len(brain.payloads) == 1  # the kill never touched the graph
    assert control.exists()


# silence-watchdog tests live in test_watchdog.py
