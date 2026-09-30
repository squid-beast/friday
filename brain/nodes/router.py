"""friday · brain/nodes/router.py

Haiku classifier: utterance -> chat|vault|ops|vision|recall. Reads tool
descriptions from config/tools.yaml so ops routing improves as tools are
registered (never by editing this file). Unparseable/failed answers fall back
to chat — the assistant must always say *something*.
"""

import re
from pathlib import Path

import yaml

from adapters.llm import think as llm_think
from brain.state import FridayState, last_user

# "recall" (screen memory) stays a route so it can be ANSWERED honestly: the graph
# disarmed it with screenpipe (2026-09-29), so it lands on `unarmed`.
ROUTES = ("chat", "vault", "ops", "vision", "recall")

_TOOLS_PATH = Path(__file__).resolve().parents[2] / "config" / "tools.yaml"

_PROMPT = """\
You are the routing layer of a voice assistant serving its owner ("sir").
Classify the utterance into exactly one route. Answer with ONE word.

chat — greetings, banter, general knowledge, the time or date, opinions and advice, \
and personal facts sir tells you to remember ("remember that ...", "remember I ...") \
— remembering is chat, NOT vault.
vault — what is written IN sir's own notes and knowledge base: his business, clients, \
projects, prices, quotes, content ideas; also saving a note to his inbox \
("take a note", "add to my inbox") — a note stays vault even when it mentions a day or \
a follow-up; only "remind me ..." is a reminder.
ops — DO a concrete action for sir with a tool: read or book his calendar/schedule, \
tell the weather, set a reminder, play or control music, open his apps or the \
Obsidian notes app, report his job search, read Friday's own metrics; also questions \
about what Friday did or ran today. Short commands count: "skip this song", \
"pause the music", "book a meeting tomorrow at 3pm", "open my apps". \
Pick this for anything that fires one of these tools:{tools}
vision — look through the camera at the physical world ("what am I holding?", \
"see me", "look at me", "can you see this?", "look at this"), or operate or search \
the web in the browser for sir ("go to the site and book the slot", "search the web \
for reviews of X and read me the verdict").
recall — something sir saw on his SCREEN earlier ("that page I looked at yesterday", "what \
was on my screen"); this sense is switched off right now.

Utterance: {utterance}
Route:"""


def _tools() -> list[dict]:
    return (yaml.safe_load(_TOOLS_PATH.read_text(encoding="utf-8")) or {}).get("tools") or []


def _tools_context() -> str:
    return "".join(f"\n  - {t['name']}: {t['description']}" for t in _tools())


async def route_node(state: FridayState, *, think=llm_think) -> dict:
    utterance = last_user(state.messages)
    if not utterance:
        return {"route": "chat"}
    try:
        raw = await think(
            _PROMPT.format(tools=_tools_context(), utterance=utterance),
            fast=True,
            max_tokens=16,  # the answer is one word; anything longer is waste
        )
    except Exception:
        return {"route": "chat"}
    tools = {t["name"] for t in _tools()}  # an echoed tool name IS an ops answer
    for token in re.findall(r"[a-z_]+", raw.lower()):
        if token in ROUTES:
            return {"route": token}
        if token in tools:
            return {"route": "ops"}
    return {"route": "chat"}
