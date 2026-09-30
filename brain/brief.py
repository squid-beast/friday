"""friday · brain/brief.py

Spoken morning brief, once per day on the first wake. The once-marker is a
"brief" event in the audit log — restart-safe, no extra state file. Grounded
only in what Friday actually has: the date and remembered facts.
"""

import logging
import time

from adapters import memory as memory_adapter
from adapters.calendar import events_today, format_event
from adapters.llm import think as llm_think
from audit.log import log_event, today
from brain.nodes.chat import persona

log = logging.getLogger(__name__)

FALLBACK = "Good morning, sir. Systems are up."

_PROMPT = """\
It is {now}. Compose sir's spoken morning brief: greet him, mention the date
naturally, lead with the first calendar item if there is one, and weave in
anything useful from the remembered items.
Today's calendar:
{calendar}
Remembered items:
{facts}
At most three spoken sentences, in character."""


async def morning_brief(
    *,
    think=llm_think,
    recall=memory_adapter.recall,
    events=events_today,
    audit_read=today,
    audit_write=log_event,
) -> str | None:
    """The brief text, or None if today's brief was already spoken."""
    try:
        if any(event.kind == "brief" for event in audit_read()):
            return None
    except Exception:
        log.warning("brief marker check failed", exc_info=True)
        return None
    try:
        facts = await recall("plans, reminders and priorities for today", k=3)
    except Exception:
        facts = []
    try:
        todays = await events()
    except Exception:
        todays = []
    now = time.strftime("%A, %B %d, %H:%M")
    fact_lines = "\n".join(f"- {fact}" for fact in facts) or "- nothing on file"
    calendar_lines = "\n".join(f"- {format_event(e)}" for e in todays[:5]) or "- clear"
    try:
        text = (
            await think(
                _PROMPT.format(now=now, facts=fact_lines, calendar=calendar_lines),
                system=persona(),
            )
        ).strip()
    except Exception:
        log.warning("brief synthesis failed", exc_info=True)
        text = FALLBACK
    try:
        audit_write("brief", now)
    except Exception:
        log.warning("brief marker write failed", exc_info=True)
    return text
