"""jarvis-life-os · adapters/calendar.py

macOS Calendar via EventKit. Reads whatever Calendar.app holds — add the
Google account there and Google events come along free (DECISIONS.md). First
use triggers the macOS Calendar permission prompt; denial raises
PermissionError with the fix. Event creation is registered in tools.yaml as
risk=confirm, so nothing lands on the calendar without a spoken yes.
EventKit imports are lazy — the kill path never pays for the framework.
"""

import asyncio
import json
import re
import threading
import time
from datetime import datetime

from pydantic import BaseModel

from adapters.llm import think as llm_think

_ACCESS_TIMEOUT_S = 30
_DAY_S = 86_400
_store = None
_lock = threading.Lock()


class CalEvent(BaseModel):
    title: str
    start_ts: float
    end_ts: float
    all_day: bool = False
    calendar: str = ""


def _get_store():
    global _store
    from EventKit import EKEventStore

    with _lock:
        if _store is None:
            store = EKEventStore.alloc().init()
            done, result = threading.Event(), {"granted": False}

            def completion(granted: bool, _error) -> None:
                result["granted"] = bool(granted)
                done.set()

            store.requestFullAccessToEventsWithCompletion_(completion)
            if not done.wait(_ACCESS_TIMEOUT_S) or not result["granted"]:
                raise PermissionError(
                    "Calendar access not granted (System Settings -> Privacy -> Calendars)"
                )
            _store = store
    return _store


def _events_between(start_ts: float, end_ts: float) -> list[CalEvent]:
    from Foundation import NSDate

    store = _get_store()
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        NSDate.dateWithTimeIntervalSince1970_(start_ts),
        NSDate.dateWithTimeIntervalSince1970_(end_ts),
        None,
    )
    found = store.eventsMatchingPredicate_(predicate) or []
    events = [
        CalEvent(
            title=str(e.title() or ""),
            start_ts=e.startDate().timeIntervalSince1970(),
            end_ts=e.endDate().timeIntervalSince1970(),
            all_day=bool(e.isAllDay()),
            calendar=str(e.calendar().title()) if e.calendar() else "",
        )
        for e in found
    ]
    return sorted(events, key=lambda ev: ev.start_ts)


async def events_today() -> list[CalEvent]:
    now = time.localtime()
    midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
    return await asyncio.to_thread(_events_between, midnight, midnight + _DAY_S)


# NOTE: macOS Reminders (EKEntityTypeReminder) is deliberately NOT read here.
# requestFullAccessToReminders from a non-bundled Python process throws an
# UNCATCHABLE ObjC NSException (no Info.plist usage-description) that aborts the
# whole server — Python try/except can't guard it. The HUD's reminder sources
# are calendar events + spoken "remind me to ..." + recent vault notes instead.


def format_event(event: CalEvent) -> str:
    if event.all_day:
        return f"{event.title} (all day)"
    return f"{time.strftime('%H:%M', time.localtime(event.start_ts))} {event.title}"


# --- tools.yaml entry points: async fn(arg, utterance) -> spoken-ish str ---


async def today_summary(_arg: str, _utterance: str) -> str:
    events = await events_today()
    if not events:
        return "nothing on the calendar today"
    return "today's calendar: " + "; ".join(format_event(e) for e in events[:8])


_EXTRACT_PROMPT = """\
It is {now} ({weekday}). Extract the calendar event from sir's request as JSON:
{{"title": "...", "start": "YYYY-MM-DD HH:MM", "duration_min": 60}}
Request: "{utterance}"
JSON only. If the request has no clear date+time, use "start": ""."""


async def create_from_speech(_arg: str, utterance: str, *, think=llm_think) -> str:
    raw = await think(
        _EXTRACT_PROMPT.format(
            now=time.strftime("%Y-%m-%d %H:%M"),
            weekday=time.strftime("%A"),
            utterance=utterance,
        ),
        fast=True,
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"no event JSON in model reply: {raw[:80]!r}")
    spec = json.loads(match.group())
    if not str(spec.get("start", "")).strip():
        raise ValueError("no clear date+time in the request")
    # naive local time on purpose: "3pm" means sir's wall clock, not UTC
    start = datetime.strptime(str(spec["start"]), "%Y-%m-%d %H:%M")
    duration_min = int(spec.get("duration_min") or 60)
    title = str(spec.get("title") or "").strip() or "Appointment"
    await asyncio.to_thread(_create, title, start.timestamp(), duration_min * 60)
    spoken_time = start.strftime("%A at %H:%M")
    return f"{title} is on the calendar for {spoken_time}"


def _create(title: str, start_ts: float, duration_s: float) -> None:
    from EventKit import EKEvent, EKSpanThisEvent
    from Foundation import NSDate

    store = _get_store()
    event = EKEvent.eventWithEventStore_(store)
    event.setTitle_(title)
    event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(start_ts))
    event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(start_ts + duration_s))
    event.setCalendar_(store.defaultCalendarForNewEvents())
    ok, error = store.saveEvent_span_error_(event, EKSpanThisEvent, None)
    if not ok:
        raise ValueError(f"calendar refused the event: {error}")
