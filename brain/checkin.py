"""friday · brain/checkin.py

The caring check-in: on every wake, after the greeting, Friday asks ONE warm
question — rotating through sir's health, skills, whereabouts and what he's done
— grounded in what he last said so it lands like family, not a form. The question
is marked (brain/pending_question.py) so his answer is always remembered.
"""

import logging

from adapters import memory as memory_adapter
from adapters.llm import think as llm_think
from audit.log import today
from brain.nodes.chat import persona

log = logging.getLogger(__name__)

# Rotated by the number of wakes so far today — a different concern each time.
TOPICS = {
    "health": "how he is feeling — his health, energy, sleep",
    "skills": "what he is learning or building lately, and how it's going",
    "location": "where he is or where his day is taking him",
    "activity": "what he has gotten done, or what he's about to take on",
}
_ORDER = list(TOPICS)

_PROMPT = """\
In ONE short, warm sentence — like caring family, not an interviewer — ask sir about \
{focus}.{context} Keep it in character and end with "sir"."""


def next_topic(audit_read=today) -> str:
    """The daemon logs "wake" BEFORE this runs, so the Nth wake sees N rows."""
    try:
        n = sum(1 for e in audit_read() if e.kind == "wake")
    except Exception:
        n = 0
    return _ORDER[max(n - 1, 0) % len(_ORDER)]


async def checkin_line(
    *, think=llm_think, recall=memory_adapter.recall, audit_read=today
) -> str:
    """A single caring question, or "" if it can't be composed (greeting still works)."""
    topic = next_topic(audit_read)
    try:
        facts = await recall(f"sir's {topic}", k=1)
    except Exception:
        facts = []
    context = f' You recall: "{facts[0]}" — follow up on it naturally.' if facts else ""
    try:
        return (
            await think(
                _PROMPT.format(focus=TOPICS[topic], context=context),
                system=persona(),
                fast=True,  # a one-line warm question — the cheap/fast model is plenty
                max_tokens=60,
            )
        ).strip()
    except Exception:
        log.warning("check-in synthesis failed", exc_info=True)
        return ""
