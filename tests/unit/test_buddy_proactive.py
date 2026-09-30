"""friday · tests/unit/test_buddy_proactive.py

Phase 4 companion layer: the proactive nudge (launchd com.friday.checkin) posts
ONE caring line as a notification, queues it for the next wake and audits it —
silent when disabled or mid-session; the notification text rides in argv (never
interpolated into AppleScript); the day summary degrades per source and goes to
the Friday-owned n8n workflow only when a Telegram chat id is configured.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from brain import pending_question
from config.settings import get_settings
from integrations import day_summary
from scripts import proactive_checkin as pc


@pytest.fixture(autouse=True)
def _state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PENDING_QUESTION_FILE", str(tmp_path / "control" / "pending.json"))
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("STAND_DOWN_FILE", str(tmp_path / "control" / "stand_down"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(("hour", "part"), [(8, "morning"), (13, "midday"), (19, "evening")])
def test_part_of_day(hour: int, part: str) -> None:
    assert pc.part_of_day(hour) == part


async def test_compose_is_grounded_in_memory_and_calendar() -> None:
    seen = {}

    async def think(prompt, **kw):
        seen.update(prompt=prompt, **kw)
        return " Did you eat, sir? "

    async def recall(q, k):
        return ["sir skipped lunch yesterday"]

    async def events():
        return []

    assert await pc.compose(think=think, recall=recall, events=events, hour=13) == (
        "Did you eat, sir?")
    assert "whether he has eaten" in seen["prompt"] and "skipped lunch" in seen["prompt"]
    assert seen["fast"] is True and seen["max_tokens"] == 60


def test_notify_passes_text_as_argv_never_into_the_script() -> None:
    calls = []
    evil = 'hi" & do shell script "rm -rf ~'
    pc.notify(evil, run=lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    cmd = calls[0]
    assert cmd[0] == "osascript" and cmd[-2:] == ["--", evil]
    assert all(evil not in part for part in cmd[:-1])  # script body never contains the text


def test_main_notifies_queues_for_wake_and_audits() -> None:
    posted = []

    async def compose():
        return "Rest well tonight, sir."

    def deliver(text):
        posted.append(text)
        return True

    assert pc.main([], compose_fn=compose, notify_fn=deliver) == 0
    assert posted == ["Rest well tonight, sir."]
    assert pending_question.take_for_wake() == "Rest well tonight, sir."
    from audit.log import today

    assert any(e.kind == "proactive_checkin" for e in today())


def test_main_is_silent_when_disabled_or_mid_session(monkeypatch) -> None:
    posted = []

    async def compose():
        return "hello sir"

    monkeypatch.setenv("PROACTIVE_CHECKINS", "false")
    get_settings.cache_clear()
    pc.main([], compose_fn=compose, notify_fn=posted.append)
    monkeypatch.setenv("PROACTIVE_CHECKINS", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("client.control.read_state", lambda: "active")
    pc.main([], compose_fn=compose, notify_fn=posted.append)
    assert posted == []


def test_wake_queue_expires_after_twelve_hours() -> None:
    pending_question.queue_for_wake("How was the gym, sir?", now=1_000.0)
    assert pending_question.take_for_wake(now=1_000.0 + 13 * 3600) == ""


async def test_summary_degrades_per_source(monkeypatch) -> None:
    def boom():
        raise RuntimeError("down")

    async def jobs(_a, _u):
        return "latest batch: 3 roles"

    monkeypatch.setattr(day_summary, "_plan", boom)
    monkeypatch.setattr("integrations.jobs_voice.status", jobs)
    text = await day_summary.build()
    assert "Plan: unavailable (RuntimeError)" in text and "Jobs: latest batch: 3 roles" in text


async def test_summary_posts_to_the_friday_workflow_without_a_recipient(monkeypatch) -> None:
    sent = {}

    async def call(path, payload):
        sent.update(path=path, payload=payload)
        return "ok"

    async def build():
        return "the digest"

    monkeypatch.setattr("adapters.n8n.call", call)
    monkeypatch.setattr(day_summary, "build", build)
    assert "Telegram" in await day_summary.send("/webhook/friday-summary", "send it")
    assert sent["path"] == "/webhook/friday-summary"
    # the chat id is fixed inside the workflow: a leaked secret can't redirect the bot
    assert sent["payload"] == {"utterance": "send it", "summary": "the digest"}



def test_a_line_starting_with_a_dash_is_never_an_osascript_option() -> None:
    calls = []
    pc.notify("-e property p : 1", run=lambda c, **k: calls.append(c) or SimpleNamespace(
        returncode=0))
    assert calls[0][-2:] == ["--", "-e property p : 1"]


def test_undelivered_nudge_is_neither_audited_nor_queued() -> None:
    async def compose():
        return "hello sir"

    pc.main([], compose_fn=compose, notify_fn=lambda text: False)
    assert pending_question.take_for_wake() == ""
    from audit.log import today

    assert not any(e.kind == "proactive_checkin" for e in today())


async def test_next_event_skips_ones_already_over() -> None:
    import time

    seen = {}

    async def think(prompt, **kw):
        seen["prompt"] = prompt
        return "ok sir"

    async def recall(q, k):
        return []

    from adapters.calendar import CalEvent

    now = time.time()
    past = CalEvent(title="standup", start_ts=now - 3600, end_ts=now - 3000)
    soon = CalEvent(title="dentist", start_ts=now + 3600, end_ts=now + 5400)

    async def events():
        return [past, soon]

    await pc.compose(think=think, recall=recall, events=events, hour=13)
    assert "dentist" in seen["prompt"] and "standup" not in seen["prompt"]
