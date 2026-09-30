"""friday · tests/scenario/test_registry_risks.py

L4: the LIVE config/tools.yaml registry behaves per its declared risk — the
real loader, the real graph, only the backends faked. If someone edits a risk
level in YAML, this is the test that notices.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from config.tools import Tool, load_tools
from tests.fakes import FakeLLM, FakeMemory, FakeVault

THREAD = {"configurable": {"thread_id": "registry"}}


def test_live_registry_declares_the_d2_tools() -> None:
    tools = {t.name: t for t in load_tools()}
    assert tools["calendar_today"].risk == "safe"
    assert tools["calendar_event"].risk == "confirm"  # booking always asks
    assert tools["metrics_report"].risk == "safe"


class Executor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, tool: Tool, utterance: str) -> str:
        self.calls.append(tool.name)
        return "done"

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        return None


def _graph(llm: FakeLLM, executor: Executor):
    return build_graph(
        InMemorySaver(),
        think=llm.think,
        search=FakeVault().search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
        remember=FakeMemory().remember,
        tools=load_tools,  # <- the REAL registry
        execute=executor,
        audit=executor.audit,
        audit_read=list,
    )


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_booking_through_the_live_registry_is_confirm_gated() -> None:
    llm = FakeLLM(["ops", "calendar_event", "Booked, sir.", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    result = await graph.ainvoke(_turn("book the dentist tomorrow at 3pm"), THREAD)
    assert executor.calls == []  # parked at "Shall I proceed, sir?"
    assert "Shall I proceed" in result["__interrupt__"][0].value["question"]
    result = await graph.ainvoke(Command(resume="yes"), THREAD)
    await drain()
    assert executor.calls == ["calendar_event"]
    assert result["reply"] == "Booked, sir."


async def test_metrics_through_the_live_registry_runs_without_a_gate() -> None:
    llm = FakeLLM(["ops", "metrics_report", "Reels are up forty percent, sir.", "NONE"])
    executor = Executor()
    result = await _graph(llm, executor).ainvoke(_turn("how did the reels do?"), THREAD)
    await drain()
    assert executor.calls == ["metrics_report"]
    assert "__interrupt__" not in result
