"""friday · tests/unit/test_confirm_gate.py

Confirm gate (TDD — written before brain/confirm.py and the ops wiring).
The invariant that must never regress: a risk=confirm tool executes ONLY after
an explicit spoken yes. No answer, a no, hedging, a negated yes, or a brand-new
utterance instead of an answer -> NOTHING executes.
"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from brain.confirm import is_spoken_yes
from brain.graph import build_graph
from config.tools import Tool
from tests.fakes import FakeLLM, FakeMemory, FakeVault

# --- the yes parser: explicit affirmatives only, negation always wins ---


@pytest.mark.parametrize(
    "text",
    ["yes", "Yes.", "yes please", "yeah", "yep", "go ahead", "do it", "proceed",
     "sure", "affirmative", "confirmed", "absolutely", "YES GO AHEAD"],
)
def test_explicit_yes_accepted(text: str) -> None:
    assert is_spoken_yes(text) is True


@pytest.mark.parametrize(
    "text",
    ["no", "No.", "nope", "not now", "don't", "do not", "stop", "cancel", "wait",
     "hold on", "maybe", "hmm", "what does it do?", "", "   ",
     "yes... actually no, wait",  # negation anywhere kills the yes
     "no, but yes tomorrow",
     "yesterday"],  # 'yes' hidden inside a word must not count
)
def test_everything_else_refused(text: str) -> None:
    assert is_spoken_yes(text) is False


# --- graph-level: interrupt pauses, and only resume("yes") executes ---


TOOL = Tool(
    name="content_pipeline",
    description="runs the content pipeline for a new reel",
    adapter="adapters.n8n:call",
    webhook_path="/webhook/content",
    risk="confirm",
)
THREAD = {"configurable": {"thread_id": "confirm-t"}}


class Executor:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.audited: list[tuple[str, str, bool]] = []

    async def __call__(self, tool: Tool, utterance: str) -> str:
        self.calls.append(tool.name)
        return "workflow started"

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.audited.append((tool, result, confirmed))


def _graph(llm: FakeLLM, executor: Executor, tool: Tool = TOOL):
    return build_graph(
        InMemorySaver(),
        think=llm.think,
        search=FakeVault().search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
        remember=FakeMemory().remember,
        tools=lambda: [tool],
        execute=executor,
        audit=executor.audit,
        audit_read=list,
    )


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_confirm_tool_pauses_and_asks_in_character() -> None:
    llm = FakeLLM(["ops", "content_pipeline"])
    executor = Executor()
    result = await _graph(llm, executor).ainvoke(_turn("run my content pipeline"), THREAD)
    assert executor.calls == []  # NOTHING ran yet
    (intr,) = result["__interrupt__"]
    assert "Shall I proceed, sir?" in intr.value["question"]


async def test_resume_yes_executes_and_speaks_summary() -> None:
    llm = FakeLLM(["ops", "content_pipeline", "Done, sir — the pipeline is off.", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("run my content pipeline"), THREAD)
    result = await graph.ainvoke(Command(resume="yes, go ahead"), THREAD)
    assert executor.calls == ["content_pipeline"]
    assert result["reply"] == "Done, sir — the pipeline is off."


@pytest.mark.parametrize("answer", ["no", "hmm, hold on", "what will that do?"])
async def test_resume_without_yes_never_executes(answer: str) -> None:
    llm = FakeLLM(["ops", "content_pipeline", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("run my content pipeline"), THREAD)
    result = await graph.ainvoke(Command(resume=answer), THREAD)
    assert executor.calls == []
    assert "Nothing was executed" in result["reply"]


async def test_fresh_utterance_instead_of_answer_abandons_the_gate() -> None:
    """Sir changes the subject mid-confirm: the parked tool must NEVER fire."""
    llm = FakeLLM(["ops", "content_pipeline", "chat", "It is nine in the morning, sir.", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("run my content pipeline"), THREAD)
    result = await graph.ainvoke(_turn("what time is it?"), THREAD)  # new input, not a resume
    assert executor.calls == []
    assert result["reply"] == "It is nine in the morning, sir."


async def test_safe_tool_skips_the_gate() -> None:
    safe = Tool(
        name="morning_report",
        description="reads today's bookings",
        adapter="adapters.n8n:call",
        webhook_path="/webhook/report",
        risk="safe",
    )
    llm = FakeLLM(["ops", "morning_report", "Bookings are healthy, sir.", "NONE"])
    executor = Executor()
    result = await _graph(llm, executor, tool=safe).ainvoke(_turn("morning report please"), THREAD)
    assert executor.calls == ["morning_report"]
    assert "__interrupt__" not in result
    assert executor.audited == [("morning_report", "workflow started", True)]


async def test_blocked_tool_refuses_even_with_eager_yes() -> None:
    blocked = TOOL.model_copy(update={"name": "wipe_crm", "risk": "blocked"})
    llm = FakeLLM(["ops", "wipe_crm", "NONE"])
    executor = Executor()
    result = await _graph(llm, executor, tool=blocked).ainvoke(
        _turn("yes yes just wipe the crm, I confirm"), THREAD
    )
    assert executor.calls == []
    assert "__interrupt__" not in result  # blocked never even asks
    assert executor.audited == [("wipe_crm", "refused: blocked", False)]  # refusal is logged
