"""friday · tests/unit/test_vision_browser.py

Graph-level browser confirm gate: same interrupt invariants as ops — pause,
resume-yes runs exactly the confirmed task, anything else never browses.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from brain.graph import build_graph
from brain.nodes.memory_writer import drain
from brain.nodes.ops import ABORTED
from tests.fakes import FakeLLM, FakeMemory, FakeVault

THREAD = {"configurable": {"thread_id": "vision-t"}}


class Recorder:
    def __init__(self) -> None:
        self.audited: list[tuple[str, str, bool]] = []
        self.browsed: list[str] = []

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.audited.append((tool, result, confirmed))

    async def browse(self, task: str) -> str:
        self.browsed.append(task)
        return "Booked the 9am slot."


def _graph(llm: FakeLLM, rec: Recorder):
    async def look(q: str) -> str:
        return "nothing of note"

    return build_graph(
        InMemorySaver(),
        think=llm.think,
        search=FakeVault().search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
        remember=FakeMemory().remember,
        tools=list,
        audit=rec.audit,
        audit_read=list,
        look=look,
        browse=rec.browse,
    )


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_browser_task_pauses_for_confirmation() -> None:
    llm = FakeLLM(["vision", "browser: book the 9am slot"])
    rec = Recorder()
    result = await _graph(llm, rec).ainvoke(_turn("book the 9am slot online"), THREAD)
    assert rec.browsed == []
    (intr,) = result["__interrupt__"]
    assert "driving the web" in intr.value["question"]


async def test_browser_resume_yes_runs_task() -> None:
    llm = FakeLLM(["vision", "browser: book the 9am slot", "Booked, sir. Nine sharp.", "NONE"])
    rec = Recorder()
    graph = _graph(llm, rec)
    await graph.ainvoke(_turn("book the 9am slot online"), THREAD)
    result = await graph.ainvoke(Command(resume="go ahead"), THREAD)
    await drain()
    assert rec.browsed == ["book the 9am slot"]
    assert result["reply"] == "Booked, sir. Nine sharp."
    assert ("browser_task", "Booked the 9am slot.", True) in rec.audited


async def test_browser_resume_no_never_runs() -> None:
    llm = FakeLLM(["vision", "browser: order the espresso machine", "NONE"])
    rec = Recorder()
    graph = _graph(llm, rec)
    await graph.ainvoke(_turn("order it online"), THREAD)
    result = await graph.ainvoke(Command(resume="no, hold off"), THREAD)
    await drain()
    assert rec.browsed == []
    assert result["reply"] == ABORTED
    assert ("browser_task", "aborted: no spoken yes", False) in rec.audited
