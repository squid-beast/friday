"""friday · tests/unit/test_ask_bridge.py

The phone bridge: kill phrases never reach the graph, gate questions carry a
pending flag the next text answers, threads stay continuous.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from config.settings import get_settings
from integrations.ask import BrainBridge


@pytest.fixture
def control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STAND_DOWN_FILE", str(tmp_path / "stand_down"))
    monkeypatch.setenv("CAMERA_OFF_FILE", str(tmp_path / "camera_off"))
    monkeypatch.setenv("SCREEN_OFF_FILE", str(tmp_path / "screen_off"))
    get_settings.cache_clear()
    yield tmp_path / "stand_down"
    get_settings.cache_clear()


class FakeGraph:
    def __init__(self, results: list[dict]) -> None:
        self.results = list(results)
        self.payloads: list = []

    async def ainvoke(self, payload, config: dict) -> dict:
        self.payloads.append(payload)
        return self.results.pop(0)


def _bridge(graph: FakeGraph) -> BrainBridge:
    async def factory():
        return graph

    return BrainBridge(brain_factory=factory)


def test_normal_turn(control: Path) -> None:
    graph = FakeGraph([{"reply": "Indeed, sir.", "messages": []}])
    out = _bridge(graph).ask("what did I quote Receivly?")
    assert out == {"reply": "Indeed, sir.", "pending": False}
    assert graph.payloads[0]["messages"][0]["content"] == "what did I quote Receivly?"


def test_gate_question_pends_then_next_text_resumes(control: Path) -> None:
    graph = FakeGraph(
        [
            {"reply": "stale", "__interrupt__": [
                SimpleNamespace(value={"question": "Shall I proceed, sir?"})
            ]},
            {"reply": "Done, sir.", "messages": []},
        ]
    )
    bridge = _bridge(graph)
    first = bridge.ask("run my content pipeline")
    assert first == {"reply": "Shall I proceed, sir?", "pending": True}
    second = bridge.ask("yes, go ahead")
    assert second == {"reply": "Done, sir.", "pending": False}
    resume = graph.payloads[1]
    assert isinstance(resume, Command) and resume.resume == "yes, go ahead"


def test_stand_down_from_phone_touches_control_never_graph(control: Path) -> None:
    graph = FakeGraph([])
    out = _bridge(graph).ask("stand down")
    assert out["reply"] == "Standing down, sir."
    assert control.exists()  # the daemon at home acts on this
    assert graph.payloads == []


def test_stand_down_clears_a_pending_gate(control: Path) -> None:
    graph = FakeGraph(
        [{"reply": "stale", "__interrupt__": [
            SimpleNamespace(value={"question": "Shall I proceed, sir?"})
        ]}]
    )
    bridge = _bridge(graph)
    bridge.ask("run my content pipeline")
    bridge.ask("stand down")
    assert bridge._pending_confirm is False  # the parked gate is dead


def test_camera_cut_from_phone(control: Path) -> None:
    graph = FakeGraph([])
    out = _bridge(graph).ask("camera off")
    assert out["reply"] == "Camera disabled, sir."
    assert Path(get_settings().camera_off_file).exists()
    assert graph.payloads == []


def test_empty_text(control: Path) -> None:
    assert _bridge(FakeGraph([])).ask("   ") == {"reply": "Sir?", "pending": False}


def test_brain_built_once_thread_continuous(control: Path) -> None:
    graph = FakeGraph(
        [{"reply": "One.", "messages": []}, {"reply": "Two.", "messages": []}]
    )
    calls = []

    async def factory():
        calls.append(1)
        return graph

    bridge = BrainBridge(brain_factory=factory)
    bridge.ask("first")
    bridge.ask("second")
    assert calls == [1]  # one brain, one checkpointed phone thread
