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
    assert cmd[0] == "osascript" and cmd[-1] == evil
    assert all(evil not in part for part in cmd[:-1])  # script body never contains the text


def test_main_notifies_queues_for_wake_and_audits() -> None:
    posted = []

    async def compose():
        return "Rest well tonight, sir."

    assert pc.main([], compose_fn=compose, notify_fn=posted.append) == 0
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


async def test_summary_needs_a_chat_id_then_posts_to_the_friday_workflow(monkeypatch) -> None:
    sent = {}

    async def call(path, payload):
        sent.update(path=path, payload=payload)
        return "ok"

    async def build():
        return "the digest"

    monkeypatch.setattr("adapters.n8n.call", call)
    monkeypatch.setattr(day_summary, "build", build)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    get_settings.cache_clear()
    assert "TELEGRAM_CHAT_ID" in await day_summary.send("/webhook/friday-summary", "send it")
    assert sent == {}
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    get_settings.cache_clear()
    assert "Telegram" in await day_summary.send("/webhook/friday-summary", "send it")
    assert sent["path"] == "/webhook/friday-summary"
    assert sent["payload"] == {"utterance": "send it", "summary": "the digest",
                               "chat_id": "12345"}
