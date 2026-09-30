"""jarvis-life-os · tests/unit/test_ops_node.py

ops_select / ops_execute with fakes: registry edge cases, audit queries,
execution failure apologies. The confirm-gate invariants live in
test_confirm_gate.py.
"""

from audit.log import Event
from brain.nodes.ops import (
    NO_MATCH,
    NO_TOOLS,
    ops_execute_node,
    ops_select_node,
)
from brain.state import JarvisState
from config.tools import Tool
from tests.fakes import BrokenLLM, FakeLLM

TOOL = Tool(
    name="content_pipeline",
    description="runs the content pipeline",
    adapter="adapters.n8n:call",
    webhook_path="/webhook/content",
    risk="safe",
)


def _state(utterance: str, pending: str = "") -> JarvisState:
    return JarvisState(
        messages=[{"role": "user", "content": utterance}], pending_tool=pending
    )


class Recorder:
    def __init__(self) -> None:
        self.audited: list[tuple[str, str, bool]] = []
        self.confirms: list[str] = []
        self.executed: list[str] = []

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.audited.append((tool, result, confirmed))

    def confirm(self, question: str) -> bool:
        self.confirms.append(question)
        return True

    async def execute(self, tool: Tool, utterance: str) -> str:
        self.executed.append(tool.name)
        return "ok"


# --- ops_select ---


async def test_no_registered_tools() -> None:
    out = await ops_select_node(
        _state("run the thing"), think=FakeLLM([]).think, tools=list, audit_read=list
    )
    assert out["reply"] == NO_TOOLS and out["pending_tool"] == ""


async def test_select_match_sets_pending_only() -> None:
    out = await ops_select_node(
        _state("run my content pipeline"),
        think=FakeLLM(["content_pipeline"]).think,
        tools=lambda: [TOOL],
        audit_read=list,
    )
    assert out == {"pending_tool": "content_pipeline"}  # no reply yet — gate comes next


async def test_select_none_answer_is_no_match() -> None:
    out = await ops_select_node(
        _state("order a pizza"),
        think=FakeLLM(["NONE"]).think,
        tools=lambda: [TOOL],
        audit_read=list,
    )
    assert out["reply"] == NO_MATCH and out["pending_tool"] == ""


async def test_select_llm_down_is_no_match_not_a_crash() -> None:
    out = await ops_select_node(
        _state("run it"), think=BrokenLLM().think, tools=lambda: [TOOL], audit_read=list
    )
    assert out["reply"] == NO_MATCH


async def test_audit_query_reads_log_not_workflows() -> None:
    events = [Event(ts=1.0, kind="wake", detail="wake_phrase")]
    llm = FakeLLM(["You woke me once and ran nothing, sir."])
    out = await ops_select_node(
        _state("what did you do today?"), think=llm.think, tools=list, audit_read=lambda: events
    )
    assert out["reply"] == "You woke me once and ran nothing, sir."
    assert "wake" in llm.calls[0]["prompt"]


async def test_audit_query_empty_log_needs_no_llm() -> None:
    llm = FakeLLM([])
    out = await ops_select_node(
        _state("what did you do today?"), think=llm.think, tools=list, audit_read=list
    )
    assert out["reply"] == "Nothing in the log today, sir."
    assert llm.calls == []


# --- ops_execute ---


async def test_safe_tool_never_asks_for_confirmation() -> None:
    rec = Recorder()
    out = await ops_execute_node(
        _state("run it", pending="content_pipeline"),
        think=FakeLLM(["Done, sir."]).think,
        tools=lambda: [TOOL],
        execute=rec.execute,
        confirm=rec.confirm,
        audit=rec.audit,
    )
    assert rec.executed == ["content_pipeline"] and rec.confirms == []
    assert out["reply"] == "Done, sir." and out["pending_tool"] == ""


async def test_stale_pending_tool_refuses() -> None:
    rec = Recorder()
    out = await ops_execute_node(
        _state("run it", pending="deleted_tool"),
        think=FakeLLM([]).think,
        tools=lambda: [TOOL],
        execute=rec.execute,
        confirm=rec.confirm,
        audit=rec.audit,
    )
    assert out["reply"] == NO_MATCH and rec.executed == []


async def test_execution_failure_apologizes_and_audits() -> None:
    rec = Recorder()

    async def boom(tool: Tool, utterance: str) -> str:
        raise ConnectionError("n8n down")

    out = await ops_execute_node(
        _state("run it", pending="content_pipeline"),
        think=FakeLLM([]).think,
        tools=lambda: [TOOL],
        execute=boom,
        confirm=rec.confirm,
        audit=rec.audit,
    )
    assert "couldn't run" in out["reply"]
    assert rec.audited == [("content_pipeline", "failed: unreachable/error", True)]


async def test_summary_llm_down_still_reports_done() -> None:
    rec = Recorder()
    out = await ops_execute_node(
        _state("run it", pending="content_pipeline"),
        think=BrokenLLM().think,
        tools=lambda: [TOOL],
        execute=rec.execute,
        confirm=rec.confirm,
        audit=rec.audit,
    )
    assert out["reply"] == "Done, sir. content_pipeline has run."  # the work DID happen
    assert rec.audited[0][2] is True
