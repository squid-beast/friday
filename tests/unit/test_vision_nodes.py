"""friday · tests/unit/test_vision_nodes.py

recall / vision_select / vision_execute with fakes, plus the graph-level
browser confirm gate (same interrupt invariants as ops).
"""


from adapters.screenpipe import ScreenHit
from brain.nodes.vision import (
    CAMERA_CUT,
    RECALL_APOLOGY,
    RECALL_EMPTY,
    RECALL_OFF,
    recall_node,
    vision_execute_node,
    vision_select_node,
)
from brain.state import FridayState
from tests.fakes import BrokenLLM, FakeLLM

HIT = ScreenHit(
    text="github.com/langchain-ai/langgraph — Build resilient agents",
    app="Safari",
    window="GitHub",
    timestamp="2026-08-09T15:04:00Z",
)


def _state(utterance: str, pending: str = "") -> FridayState:
    return FridayState(
        messages=[{"role": "user", "content": utterance}], pending_action=pending
    )


# --- recall ---


async def test_recall_grounds_answer_in_screen_hits() -> None:
    llm = FakeLLM(["The langgraph repo on GitHub, sir — yesterday afternoon."])

    async def screen_search(q: str, **kw):
        return [HIT]

    out = await recall_node(_state("that repo I looked at yesterday?"),
                            think=llm.think, screen_search=screen_search)
    assert out["reply"].startswith("The langgraph repo")
    prompt = llm.calls[0]["prompt"]
    assert "langgraph" in prompt and "2026-08-09" in prompt and "ONLY" in prompt


async def test_recall_respects_the_screen_cut() -> None:
    async def cut_search(q: str, **kw):
        raise PermissionError("cut")

    out = await recall_node(_state("what was on my screen?"),
                            think=FakeLLM([]).think, screen_search=cut_search)
    assert out["reply"] == RECALL_OFF


async def test_recall_service_down_apologizes() -> None:
    async def dead_search(q: str, **kw):
        raise ConnectionError("screenpipe not running")

    out = await recall_node(_state("that page?"), think=FakeLLM([]).think,
                            screen_search=dead_search)
    assert out["reply"] == RECALL_APOLOGY


async def test_recall_no_hits_says_so_without_llm() -> None:
    llm = FakeLLM([])

    async def empty_search(q: str, **kw):
        return []

    out = await recall_node(_state("flurbles?"), think=llm.think, screen_search=empty_search)
    assert out["reply"] == RECALL_EMPTY and llm.calls == []


# --- vision_select ---


async def test_select_camera() -> None:
    out = await vision_select_node(_state("what am I holding?"),
                                   think=FakeLLM(["camera"]).think)
    assert out == {"pending_action": "camera:what am I holding?"}


async def test_select_browser_restates_task() -> None:
    out = await vision_select_node(
        _state("can you book the 9am slot on the site"),
        think=FakeLLM(["browser: book the 9am slot on the BookYourSlot site"]).think,
    )
    assert out == {"pending_action": "browser:book the 9am slot on the BookYourSlot site"}


async def test_select_llm_down_defaults_to_camera() -> None:
    out = await vision_select_node(_state("look at this"), think=BrokenLLM().think)
    assert out["pending_action"] == "camera:look at this"


# --- vision_execute: camera ---


class Recorder:
    def __init__(self) -> None:
        self.audited: list[tuple[str, str, bool]] = []
        self.browsed: list[str] = []

    def audit(self, tool: str, args: str, result: str, *, confirmed: bool) -> None:
        self.audited.append((tool, result, confirmed))

    async def browse(self, task: str) -> str:
        self.browsed.append(task)
        return "Booked the 9am slot."


async def test_camera_look_persona_and_audit() -> None:
    rec = Recorder()

    async def look(q: str) -> str:
        return "A red multimeter"

    out = await vision_execute_node(
        _state("q", pending="camera:what am I holding?"),
        think=FakeLLM(["A red multimeter, sir — treat it gently."]).think,
        look=look, browse=rec.browse, confirm=lambda q: True, audit=rec.audit,
    )
    assert out["reply"].startswith("A red multimeter")
    assert out["pending_action"] == ""
    assert rec.audited == [("camera_look", "A red multimeter", True)]


async def test_camera_cut_line() -> None:
    async def cut_look(q: str) -> str:
        raise PermissionError("cut")

    out = await vision_execute_node(
        _state("q", pending="camera:what is this?"),
        think=FakeLLM([]).think, look=cut_look,
        browse=Recorder().browse, confirm=lambda q: True, audit=Recorder().audit,
    )
    assert out["reply"] == CAMERA_CUT


async def test_camera_stack_missing_apologizes() -> None:
    async def broken_look(q: str) -> str:
        raise ValueError("imagesnap not installed")

    out = await vision_execute_node(
        _state("q", pending="camera:look"),
        think=FakeLLM([]).think, look=broken_look,
        browse=Recorder().browse, confirm=lambda q: True, audit=Recorder().audit,
    )
    assert "aren't available" in out["reply"]


# graph-level browser confirm tests live in test_vision_browser.py
