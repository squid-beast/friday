"""jarvis-life-os · tests/unit/test_brief.py

Morning brief: once per day via the audit marker, grounded in remembered
facts, degrades to a canned line — never blocks the greeting.
"""

import time

from adapters.calendar import CalEvent
from audit.log import Event
from brain.brief import FALLBACK, morning_brief
from tests.fakes import BrokenLLM, FakeLLM, FakeMemory

BRIEF_EVENT = Event(ts=1.0, kind="brief", detail="Sunday")
NINE = time.mktime(time.strptime("2026-08-11 09:00", "%Y-%m-%d %H:%M"))


async def _no_events():
    return []


class Marker:
    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    def write(self, kind: str, detail: str = "") -> None:
        self.written.append((kind, detail))


async def test_first_wake_speaks_brief_with_facts_and_marks_done() -> None:
    llm = FakeLLM(["Good morning, sir. Demo day — locker code 4242, gym at seven."])
    marker = Marker()
    text = await morning_brief(
        think=llm.think,
        events=_no_events,
        recall=FakeMemory(["Sir's gym session is at 7", "Sir's locker code is 4242"]).recall,
        audit_read=list,
        audit_write=marker.write,
    )
    assert text.startswith("Good morning")
    assert "gym session is at 7" in llm.calls[0]["prompt"]
    assert marker.written and marker.written[0][0] == "brief"


async def test_second_wake_same_day_is_silent() -> None:
    llm = FakeLLM([])
    marker = Marker()
    text = await morning_brief(
        think=llm.think,
        events=_no_events,
        recall=FakeMemory().recall,
        audit_read=lambda: [BRIEF_EVENT],
        audit_write=marker.write,
    )
    assert text is None
    assert llm.calls == [] and marker.written == []


async def test_llm_down_still_greets_and_marks() -> None:
    marker = Marker()
    text = await morning_brief(
        think=BrokenLLM().think,
        events=_no_events,
        recall=FakeMemory().recall,
        audit_read=list,
        audit_write=marker.write,
    )
    assert text == FALLBACK
    assert marker.written  # no retry storm tomorrow morning


async def test_memory_down_briefs_anyway() -> None:
    async def broken_recall(q: str, k: int = 3):
        raise ConnectionError("chroma gone")

    llm = FakeLLM(["Good morning, sir. A quiet slate today."])
    text = await morning_brief(
        think=llm.think, events=_no_events, recall=broken_recall,
        audit_read=list, audit_write=Marker().write
    )
    assert text.startswith("Good morning")
    assert "nothing on file" in llm.calls[0]["prompt"]


async def test_brief_leads_with_first_calendar_event() -> None:
    """Phase D2 acceptance: the brief mentions today's first event."""

    async def one_event():
        return [CalEvent(title="Standup with Receivly", start_ts=NINE, end_ts=NINE + 1800)]

    llm = FakeLLM(["Good morning, sir — Receivly standup at nine, then a clear runway."])
    text = await morning_brief(
        think=llm.think,
        events=one_event,
        recall=FakeMemory().recall,
        audit_read=list,
        audit_write=Marker().write,
    )
    assert "nine" in text.lower()
    assert "09:00 Standup with Receivly" in llm.calls[0]["prompt"]


async def test_calendar_down_briefs_anyway() -> None:
    async def broken_events():
        raise PermissionError("calendar access not granted")

    llm = FakeLLM(["Good morning, sir."])
    text = await morning_brief(
        think=llm.think,
        events=broken_events,
        recall=FakeMemory().recall,
        audit_read=list,
        audit_write=Marker().write,
    )
    assert text.startswith("Good morning")
    assert "- clear" in llm.calls[0]["prompt"]


async def test_broken_audit_read_skips_brief_not_crashes() -> None:
    def broken_read():
        raise OSError("audit db corrupted")

    text = await morning_brief(
        think=FakeLLM([]).think,
        events=_no_events,
        recall=FakeMemory().recall,
        audit_read=broken_read,
        audit_write=Marker().write,
    )
    assert text is None  # plain greeting instead — never a crash before hello
