"""friday · brain/mood_sense.py

Feeds brain/mood.py from the real world. refresh_at_wake() runs once per wake
(voice agent, before the greeting): audit events since the last look, plus —
at most once per day — remembered facts about sleep/deadlines/wins, today's
calendar load, the hour, and how long sir was away. turn_update() runs each
turn and only folds in new audit events (cheap: one sqlite read). Every source
degrades independently; a failure leaves the mood where it was.
"""

import logging
import time

from brain import mood

log = logging.getLogger(__name__)
_DAY = 86_400


def _audit_since(ts: float):
    from audit.log import events_since

    return events_since(ts)


async def _facts() -> list[str]:
    from adapters.memory import recall

    # only what he said in the last 2 days: a months-old "slept badly" must not fire daily
    return await recall("how sir is doing: sleep, deadlines, wins, stress", k=5,
                        max_age_s=2 * _DAY)


async def _events_today() -> int:
    from adapters.calendar import events_today

    return len(await events_today())


async def refresh_at_wake(*, now: float | None = None, audit=_audit_since, facts=_facts,
                          calendar=_events_today) -> mood.MoodState:
    now = time.time() if now is None else now
    raw = mood.load_raw()
    hours_away = (now - raw.updated) / 3600 if raw.updated else 0.0
    state = mood._decayed(raw, now)
    try:
        mood.observe(state, audit(state.cursor or now - _DAY))
    except Exception:
        log.warning("mood: audit read failed", exc_info=True)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    if state.context_day != today:
        remembered: list[str] = []
        n_events = 0
        try:
            remembered = await facts()
        except Exception:
            log.warning("mood: memory recall failed", exc_info=True)
        try:
            n_events = await calendar()
        except Exception:
            log.warning("mood: calendar read failed", exc_info=True)
        hour = time.localtime(now).tm_hour
        for event in mood.events_from_context(remembered, n_events, hour, hours_away):
            mood.apply(state, event)
        state.context_day = today
    mood.save(state)
    return state


def turn_update(*, now: float | None = None, audit=_audit_since) -> mood.MoodState:
    now = time.time() if now is None else now
    state = mood.load(now)
    try:
        mood.observe(state, audit(state.cursor or now - _DAY))
    except Exception:
        log.warning("mood: audit read failed", exc_info=True)
    mood.save(state)
    return state


def current_line() -> str:
    """The disposition line for the system prompt ("" if the mood can't be read)."""
    try:
        return mood.disposition(mood.load())
    except Exception:
        return ""
