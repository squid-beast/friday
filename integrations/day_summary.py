"""friday · integrations/day_summary.py

"Send me a summary" — tool `send_summary` (risk confirm). Friday builds the day
digest LOCALLY (calendar, today's plan, pending reminders, job search, what she
did today) and POSTs it to the Friday-owned n8n workflow "Friday — Send me a
summary" (/webhook/friday-summary, header auth X-Friday-Secret), which delivers
it to sir's Telegram via his bot. No business workflow is involved. Every source
degrades independently. The Telegram recipient is set once in the n8n workflow
(never sent from here).
"""

import time


async def _calendar() -> str:
    from adapters.calendar import events_today, format_event

    events = await events_today()
    return "; ".join(format_event(e) for e in events[:6]) or "nothing on the calendar"


def _plan() -> str:
    from adapters import vault_plan

    todo = vault_plan.items()
    if not todo:
        return "no plan written"
    return "; ".join(("✓ " if done else "☐ ") + text for done, text in todo)


def _reminders() -> str:
    from integrations import reminders

    pending = [r["text"] for r in reminders.pending()]
    return "; ".join(pending[:6]) or "none"


def _activity() -> str:
    from audit.log import today

    events = today()
    tools = sum(1 for e in events if e.kind == "tool")
    wakes = sum(1 for e in events if e.kind == "wake")
    return f"{wakes} wakes, {tools} actions run"


async def build() -> str:
    from integrations.jobs_voice import status as jobs_status

    sections = [("Calendar", _calendar), ("Plan", _plan), ("Reminders", _reminders),
                ("Jobs", lambda: jobs_status("", "")), ("Friday today", _activity)]
    lines = [f"Friday — day summary, {time.strftime('%a %d %b %H:%M')}"]
    for title, source in sections:
        try:
            value = source()
            value = await value if hasattr(value, "__await__") else value
        except Exception as exc:
            value = f"unavailable ({type(exc).__name__})"
        lines.append(f"{title}: {value}")
    return "\n".join(lines)


async def send(webhook_path: str, utterance: str) -> str:
    from adapters.n8n import call

    summary = await build()
    # no chat id in the payload: the recipient is fixed INSIDE the Friday workflow, so a
    # leaked webhook secret can't turn his bot into a relay to arbitrary chats
    await call(webhook_path, {"utterance": utterance, "summary": summary})
    return "the day summary is on its way to your Telegram"
