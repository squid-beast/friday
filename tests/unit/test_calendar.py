"""friday · tests/unit/test_calendar.py

adapters/calendar.py with EventKit fully mocked — tests must NEVER trigger the
macOS permission prompt. The objc glue itself is exercised live.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

import adapters.calendar as cal
from adapters.calendar import CalEvent
from tests.fakes import BrokenLLM, FakeLLM

NINE = time.mktime(time.strptime("2026-08-11 09:00", "%Y-%m-%d %H:%M"))
STANDUP = CalEvent(title="Standup", start_ts=NINE, end_ts=NINE + 1800, calendar="Work")
LAUNCH = CalEvent(title="Launch day", start_ts=NINE, end_ts=NINE + 86_400, all_day=True)


# --- today_summary tool ---


async def test_today_summary_lists_times_and_titles() -> None:
    with patch.object(cal, "_events_between", return_value=[STANDUP, LAUNCH]):
        text = await cal.today_summary("", "what's on today?")
    assert "09:00 Standup" in text
    assert "Launch day (all day)" in text


async def test_today_summary_empty_calendar() -> None:
    with patch.object(cal, "_events_between", return_value=[]):
        assert "nothing on the calendar" in await cal.today_summary("", "")


async def test_permission_denied_propagates() -> None:
    with (
        patch.object(cal, "_events_between", side_effect=PermissionError("not granted")),
        pytest.raises(PermissionError),
    ):
        await cal.events_today()


# --- create_from_speech tool ---


async def test_create_parses_speech_and_saves() -> None:
    llm = FakeLLM(['{"title": "Dentist", "start": "2026-08-11 15:00", "duration_min": 45}'])
    with patch.object(cal, "_create") as create:
        line = await cal.create_from_speech(
            "", "book the dentist tomorrow at 3pm for 45 minutes", think=llm.think
        )
    title, start_ts, duration_s = create.call_args.args
    assert title == "Dentist"
    assert time.strftime("%H:%M", time.localtime(start_ts)) == "15:00"
    assert duration_s == 45 * 60
    assert "Dentist is on the calendar" in line
    assert llm.calls[0]["fast"] is True  # extraction is a cheap-model job


async def test_create_tolerates_prose_around_json() -> None:
    llm = FakeLLM(
        ['Sure: {"title": "Gym", "start": "2026-08-12 07:00", "duration_min": 60} there.'])
    with patch.object(cal, "_create") as create:
        await cal.create_from_speech("", "gym wednesday 7am", think=llm.think)
    assert create.call_args.args[0] == "Gym"


async def test_create_refuses_without_clear_time() -> None:
    llm = FakeLLM(['{"title": "Coffee", "start": "", "duration_min": 60}'])
    with (
        patch.object(cal, "_create") as create,
        pytest.raises(ValueError, match="no clear date"),
    ):
        await cal.create_from_speech("", "coffee sometime", think=llm.think)
    create.assert_not_called()  # never guess a time onto sir's calendar


async def test_create_llm_garbage_raises_never_saves() -> None:
    llm = FakeLLM(["cannot help with that"])
    with (
        patch.object(cal, "_create") as create,
        pytest.raises(ValueError, match="no event JSON"),
    ):
        await cal.create_from_speech("", "book something", think=llm.think)
    create.assert_not_called()


async def test_create_llm_down_propagates_to_ops_apology() -> None:
    with (
        patch.object(cal, "_create", new=AsyncMock()) as create,
        pytest.raises(ConnectionError),
    ):
        await cal.create_from_speech("", "book it", think=BrokenLLM().think)
    create.assert_not_called()
