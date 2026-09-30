"""friday · scripts/proactive_checkin.py

The proactive nudge (launchd com.friday.checkin at 09:00 / 13:00 / 19:00).
Friday composes ONE caring line grounded in memory, today's calendar and her
mood — morning: rest + the day ahead; midday: food + energy; evening: wins +
winding down — posts it as a macOS notification, and queues it so the NEXT
wake follows up out loud (and remembers the answer). Silent when disabled,
while a voice session is already active, or on any failure.

Run by hand: uv run python -m scripts.proactive_checkin
"""

import asyncio
import logging
import subprocess
import sys
import time

from brain import pending_question
from config.settings import get_settings

log = logging.getLogger(__name__)

_FOCUS = {
    "morning": "how he slept and what today holds",
    "midday": "whether he has eaten and how his energy is holding up",
    "evening": "what he got done today and whether he is winding down",
}
_PROMPT = """\
Unprompted, send sir ONE short, warm line — like caring family, not an assistant — \
about {focus}.{context} It will appear as a notification. No more than 20 words; \
end with "sir"."""


def part_of_day(hour: int) -> str:
    return "morning" if hour < 12 else "midday" if hour < 17 else "evening"


async def compose(*, think=None, recall=None, events=None, hour: int | None = None) -> str:
    from adapters.calendar import events_today, format_event
    from adapters.llm import think as llm_think
    from adapters.memory import recall as memory_recall
    from brain.nodes.chat import persona

    think, recall, events = think or llm_think, recall or memory_recall, events or events_today
    focus = _FOCUS[part_of_day(time.localtime().tm_hour if hour is None else hour)]
    context = ""
    try:
        facts = await recall(f"sir: {focus}", k=2)
        if facts:
            context += f' You recall: "{facts[0]}".'
    except Exception:
        log.warning("recall failed", exc_info=True)
    try:
        upcoming = await events()
        if upcoming:
            context += f" Next on his calendar: {format_event(upcoming[0])}."
    except Exception:
        log.warning("calendar read failed", exc_info=True)
    return (await think(_PROMPT.format(focus=focus, context=context), system=persona(),
                        fast=True, max_tokens=60)).strip()


def notify(text: str, run=subprocess.run) -> bool:
    """macOS notification. The text rides in argv — never interpolated into script."""
    script = ["-e", "on run argv", "-e",
              'display notification (item 1 of argv) with title "Friday"', "-e", "end run"]
    return run(["osascript", *script, text], check=False, capture_output=True).returncode == 0


def main(argv: list[str] | None = None, *, compose_fn=compose, notify_fn=notify) -> int:
    from audit.log import log_event
    from client import control

    if not get_settings().proactive_checkins:
        return 0
    if control.read_state() == "active":
        return 0  # already talking — no need to nudge
    try:
        line = asyncio.run(compose_fn())
    except Exception:
        log.warning("proactive check-in failed", exc_info=True)
        return 0
    if not line:
        return 0
    notify_fn(line)
    pending_question.queue_for_wake(line)
    log_event("proactive_checkin", line[:120])
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
