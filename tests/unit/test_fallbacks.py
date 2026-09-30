"""jarvis-life-os · tests/unit/test_fallbacks.py

Coverage audit (Phase 7): every degraded path still speaks. These are the
think-failure and backend-failure branches the happy-path suites skip.
"""

from pathlib import Path

import pytest

from adapters.screenpipe import ScreenHit
from adapters.vault import VaultHit
from brain.brief import morning_brief
from brain.nodes.ops import _default_execute, ops_select_node
from brain.nodes.vault import vault_node
from brain.nodes.vision import (
    BROWSER_APOLOGY,
    recall_node,
    vision_execute_node,
)
from brain.state import JarvisState
from config.tools import Tool
from tests.fakes import BrokenLLM, FakeLLM, FakeMemory, FakeVault


def _state(utterance: str, **kw) -> JarvisState:
    return JarvisState(messages=[{"role": "user", "content": utterance}], **kw)


class Audit:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool]] = []

    def __call__(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.rows.append((tool, result, confirmed))


# --- synthesis LLM down, data layer up: speak SOMETHING grounded ---


async def test_vault_synthesis_down_still_speaks() -> None:
    hit = VaultHit(path="a.md", snippet="Quoted $1500")
    out = await vault_node(
        _state("Receivly quote?"),
        think=BrokenLLM().think,
        search=FakeVault([hit]).search,
        recall=FakeMemory().recall,
        append=FakeVault().append_inbox,
    )
    assert "unreachable" in out["reply"]  # apology, never silence


async def test_recall_synthesis_down_still_speaks() -> None:
    hit = ScreenHit(text="Stripe pricing", app="Safari", window="w", timestamp="t")

    async def search(q: str, **kw):
        return [hit]

    out = await recall_node(_state("that page?"), think=BrokenLLM().think, screen_search=search)
    assert "unreachable" in out["reply"]


async def test_camera_persona_down_falls_back_to_raw_sight() -> None:
    async def look(q: str) -> str:
        return "A soldering iron"

    out = await vision_execute_node(
        _state("q", pending_action="camera:what is this?"),
        think=BrokenLLM().think,
        look=look,
        browse=None,
        confirm=lambda q: True,
        audit=Audit(),
    )
    assert out["reply"] == "A soldering iron, sir."  # moondream's words beat silence


async def test_browser_failure_apologizes_and_audits() -> None:
    async def broken_browse(task: str) -> str:
        raise RuntimeError("chrome crashed")

    audit = Audit()
    out = await vision_execute_node(
        _state("q", pending_action="browser:book it"),
        think=FakeLLM([]).think,
        look=None,
        browse=broken_browse,
        confirm=lambda q: True,
        audit=audit,
    )
    assert out["reply"] == BROWSER_APOLOGY
    assert ("browser_task", "failed", True) in audit.rows


async def test_browser_summary_down_still_reports_done() -> None:
    async def browse(task: str) -> str:
        return "Booked."

    out = await vision_execute_node(
        _state("q", pending_action="browser:book it"),
        think=BrokenLLM().think,
        look=None,
        browse=browse,
        confirm=lambda q: True,
        audit=Audit(),
    )
    assert out["reply"] == "The browser task is done, sir."


async def test_audit_report_summary_down_still_counts() -> None:
    from audit.log import Event

    events = [Event(ts=1.0, kind="wake", detail="x")] * 3
    out = await ops_select_node(
        _state("what did you do today?"),
        think=BrokenLLM().think,
        tools=list,
        audit_read=lambda: events,
    )
    assert "3 events" in out["reply"]


async def test_brief_marker_write_failure_still_greets() -> None:
    async def no_events():
        return []

    def broken_write(kind: str, detail: str = "") -> None:
        raise OSError("disk full")

    llm = FakeLLM(["Good morning, sir."])
    text = await morning_brief(
        think=llm.think,
        events=no_events,
        recall=FakeMemory().recall,
        audit_read=list,
        audit_write=broken_write,
    )
    assert text == "Good morning, sir."  # two briefs tomorrow beats zero greetings today


# --- the real importlib executor resolves module:function and passes both args ---


async def test_default_execute_resolves_adapter_path() -> None:
    tool = Tool(
        name="sample", description="d", adapter="tests.fakes:sample_tool",
        webhook_path="/x", risk="safe",
    )
    assert await _default_execute(tool, "hello there") == "/x|hello there"


async def test_default_execute_bad_path_raises() -> None:
    tool = Tool(name="bad", description="d", adapter="tests.fakes:no_such_fn", risk="safe")
    with pytest.raises(AttributeError):
        await _default_execute(tool, "x")


# --- vault root misconfiguration fails loudly, not silently empty ---


def test_vault_root_not_a_directory_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from adapters.vault import read_note
    from config.settings import get_settings

    monkeypatch.setenv("VAULT_PATH", str(tmp_path / "nope"))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="not a directory"):
            read_note("anything.md")
    finally:
        get_settings.cache_clear()
