"""friday · tests/unit/test_mood.py

brain/mood.py + brain/mood_sense.py: the trigger table is deterministic (event
in, dimension delta out, no LLM); feelings decay toward baseline; a kill is
neutral instantly without costing warmth; real events (audit rows, remembered
facts, calendar, clock, absence) move the mood; context applies once a day;
the persona carries ONE disposition line.
"""

import json
import time
from pathlib import Path

import pytest

from audit.log import Event
from brain import mood, mood_sense
from config.settings import get_settings


@pytest.fixture(autouse=True)
def mood_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MOOD_PATH", str(tmp_path / "mood.json"))
    get_settings.cache_clear()
    yield tmp_path / "mood.json"
    get_settings.cache_clear()


def _tool(ts: float, result: str) -> Event:
    return Event(ts=ts, kind="tool", detail=json.dumps({"tool": "x", "result": result}))


def test_triggers_are_deterministic_and_clamped() -> None:
    state = mood.apply(mood.MoodState(), "tool_success")
    assert state.dims["confidence"] == pytest.approx(0.58)
    assert state.dims["valence"] == pytest.approx(0.56)
    for _ in range(20):
        mood.apply(state, "tool_failure")
    assert state.dims["confidence"] == 0.0  # clamped, never negative


def test_kill_is_neutral_instantly_but_keeps_warmth() -> None:
    state = mood.MoodState(dims={"valence": 0.9, "arousal": 0.8, "warmth": 0.8,
                                 "confidence": 0.2, "concern": 0.9})
    mood.apply(state, "kill")
    assert state.dims == {"valence": 0.5, "arousal": 0.5, "warmth": 0.8,
                          "confidence": 0.5, "concern": 0.5}


def test_feelings_decay_toward_baseline_and_persist(mood_file: Path) -> None:
    state = mood.MoodState(dims={**dict.fromkeys(mood.DIMS, 0.5), "concern": 0.9},
                           updated=1_000.0)
    mood.save(state)
    later = mood.load(now=1_000.0 + 6 * 3600)  # one half-life
    assert later.dims["concern"] == pytest.approx(0.7)
    assert mood.load(now=1_000.0 + 48 * 3600).dims["concern"] == pytest.approx(0.5, abs=0.01)


@pytest.mark.parametrize(("dims", "hour", "expected"), [
    ({"concern": 0.8}, 12, "worried"),
    ({"concern": 0.8, "warmth": 0.7}, 12, "protective"),
    ({"arousal": 0.4}, 2, "weary"),
    ({"confidence": 0.7, "valence": 0.6}, 12, "proud"),
    ({"valence": 0.75}, 12, "delighted"),
    ({"confidence": 0.3}, 12, "sheepish"),
    ({"warmth": 0.3}, 12, "irritated"),
    ({}, 12, "content"),
])
def test_named_moods(dims: dict, hour: int, expected: str) -> None:
    state = mood.MoodState(dims={**dict.fromkeys(mood.DIMS, 0.5), **dims})
    assert mood.named_mood(state, hour)[0] == expected


def test_disposition_is_one_word_choice_line() -> None:
    line = mood.disposition(mood.MoodState(), hour=12)
    assert line.startswith("Current disposition: mildly content.")
    assert "never the 3-sentence cap, confirmations, or safety" in line


def test_audit_rows_move_the_mood_once() -> None:
    state = mood.MoodState()
    events = [_tool(10, "ok: done"), _tool(11, "failed: 500"),
              Event(ts=12, kind="stand_down", detail="spoken")]
    mood.observe(state, events)
    assert state.cursor == 12 and state.dims["confidence"] == 0.5  # kill reset last
    before = dict(state.dims)
    mood.observe(state, events)  # same rows again: nothing new
    assert state.dims == before


def test_context_signals_from_real_life() -> None:
    got = mood.events_from_context(
        ["Sir slept badly last night", "The grant deadline is due friday", "Sir shipped v2"],
        n_events_today=6, hour=1, hours_away=72)
    assert set(got) == {"poor_sleep", "deadline_soon", "win", "busy_day", "late_night",
                        "return_after_absence"}


async def test_wake_refresh_applies_context_once_per_day(mood_file: Path) -> None:
    now = time.mktime((2026, 9, 30, 9, 0, 0, 0, 0, -1))
    calls = {"facts": 0}

    async def facts():
        calls["facts"] += 1
        return ["sir slept badly"]

    async def calendar():
        return 2

    first = await mood_sense.refresh_at_wake(now=now, audit=lambda ts: [], facts=facts,
                                             calendar=calendar)
    assert first.dims["concern"] > 0.5 and first.context_day == "2026-09-30"
    second = await mood_sense.refresh_at_wake(now=now + 60, audit=lambda ts: [],
                                              facts=facts, calendar=calendar)
    assert calls["facts"] == 1  # the second wake today doesn't re-apply (no ratchet)
    assert second.dims["concern"] <= first.dims["concern"]


async def test_wake_refresh_survives_every_source_failing(mood_file: Path) -> None:
    async def boom():
        raise RuntimeError("down")

    def audit_boom(ts):
        raise RuntimeError("db locked")

    state = await mood_sense.refresh_at_wake(audit=audit_boom, facts=boom, calendar=boom)
    assert mood_file.exists() and set(state.dims) == set(mood.DIMS)


def test_turn_update_folds_new_audit_rows(mood_file: Path) -> None:
    state = mood_sense.turn_update(audit=lambda ts: [_tool(time.time(), "ok")])
    assert state.dims["confidence"] > 0.5


def test_persona_carries_the_disposition_line() -> None:
    from brain.nodes.chat import persona

    text = persona()
    assert "You are Friday" in text and text.rstrip().splitlines()[-1].startswith(
        "Current disposition:")
