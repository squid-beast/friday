"""friday · tests/unit/test_pin_gate.py

Spoken-PIN gate for risk=pin tools (TDD — written before the implementation).
Invariants: no PIN in the answer = no execution, an eager "yes" is NOT a PIN,
an unset PIN locks the tool shut, and the digits NEVER reach the audit log.
"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from brain.confirm import is_spoken_pin, spoken_digits
from brain.graph import build_graph
from config.settings import get_settings
from config.tools import Tool
from tests.fakes import FakeLLM, FakeMemory, FakeVault

# --- digit normalization + matching ---


@pytest.mark.parametrize(
    ("text", "digits"),
    [
        ("4242", "4242"),
        ("four two four two", "4242"),
        ("my code is four two four two, go", "4242"),
        ("oh seven one nine", "0719"),
        ("it's 42 42", "4242"),
        ("no digits here", ""),
    ],
)
def test_spoken_digits(text: str, digits: str) -> None:
    assert spoken_digits(text) == digits


@pytest.mark.parametrize(
    "text", ["4242", "four two four two", "the code is 4242, proceed"]
)
def test_correct_pin_accepted(text: str) -> None:
    assert is_spoken_pin(text, "4242") is True


@pytest.mark.parametrize(
    "text",
    [
        "4243", "424", "", "yes", "yes go ahead", "proceed", "four two four", "0000",
        "4242 wait no, 4243",  # exact digit-string equality, not containment
        "no, 4242",  # negation vetoes even a correct code
    ],
)
def test_everything_else_rejected(text: str) -> None:
    assert is_spoken_pin(text, "4242") is False


def test_unset_pin_never_matches() -> None:
    assert is_spoken_pin("4242", "") is False
    assert is_spoken_pin("", "") is False


# --- graph-level: the gate itself ---


PIN_TOOL = Tool(
    name="wire_refund",
    description="wires a refund to a client",
    adapter="adapters.n8n:call",
    webhook_path="/webhook/refund",
    risk="pin",
)
THREAD = {"configurable": {"thread_id": "pin-t"}}


class Executor:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.audited: list[tuple[str, str, bool]] = []

    async def __call__(self, tool: Tool, utterance: str) -> str:
        self.calls.append(tool.name)
        return "refund wired"

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.audited.append((tool, result, confirmed))


@pytest.fixture
def pin_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FRIDAY_PIN", "4242")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _graph(llm: FakeLLM, executor: Executor):
    return build_graph(
        InMemorySaver(),
        think=llm.think,
        search=FakeVault().search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
        remember=FakeMemory().remember,
        tools=lambda: [PIN_TOOL],
        execute=executor,
        audit=executor.audit,
        audit_read=list,
    )


def _turn(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


async def test_pin_tool_asks_for_the_code(pin_env) -> None:
    llm = FakeLLM(["ops", "wire_refund"])
    executor = Executor()
    result = await _graph(llm, executor).ainvoke(_turn("wire the refund"), THREAD)
    assert executor.calls == []
    (intr,) = result["__interrupt__"]
    assert "PIN" in intr.value["question"]


async def test_correct_spoken_pin_executes(pin_env) -> None:
    llm = FakeLLM(["ops", "wire_refund", "The refund is on its way, sir.", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("wire the refund"), THREAD)
    result = await graph.ainvoke(Command(resume="four two four two"), THREAD)
    assert executor.calls == ["wire_refund"]
    assert result["reply"] == "The refund is on its way, sir."


@pytest.mark.parametrize("answer", ["yes, go ahead", "4243", "424", "absolutely, proceed"])
async def test_no_pin_no_execution_even_with_eager_yes(pin_env, answer: str) -> None:
    llm = FakeLLM(["ops", "wire_refund", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("wire the refund"), THREAD)
    result = await graph.ainvoke(Command(resume=answer), THREAD)
    assert executor.calls == []
    assert "Nothing was executed" in result["reply"]


async def test_unset_pin_locks_the_tool_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRIDAY_PIN", "")
    get_settings.cache_clear()
    try:
        llm = FakeLLM(["ops", "wire_refund", "NONE"])
        executor = Executor()
        result = await _graph(llm, executor).ainvoke(_turn("wire the refund"), THREAD)
        assert executor.calls == []
        assert "__interrupt__" not in result  # never even asks
        assert "No PIN" in result["reply"]
    finally:
        get_settings.cache_clear()


async def test_digits_never_reach_the_audit_log(pin_env) -> None:
    llm = FakeLLM(["ops", "wire_refund", "NONE"])
    executor = Executor()
    graph = _graph(llm, executor)
    await graph.ainvoke(_turn("wire the refund"), THREAD)
    await graph.ainvoke(Command(resume="4242 wait no, 4243"), THREAD)  # refused
    assert executor.calls == []
    flat = " ".join(f"{t} {r}" for t, r, _ in executor.audited)
    assert "4242" not in flat and "4243" not in flat  # the log is not a PIN dump
