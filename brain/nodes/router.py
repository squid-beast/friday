"""jarvis-life-os · brain/nodes/router.py

Haiku classifier: utterance -> chat|vault|ops|vision|recall. Reads tool
descriptions from config/tools.yaml so ops routing improves as tools are
registered (never by editing this file). Unparseable/failed answers fall back
to chat — the assistant must always say *something*.
"""

import re
from pathlib import Path

import yaml

from adapters.llm import think as llm_think
from brain.state import JarvisState, last_user

ROUTES = ("chat", "vault", "ops", "vision", "recall")

_TOOLS_PATH = Path(__file__).resolve().parents[2] / "config" / "tools.yaml"

_PROMPT = """\
You are the routing layer of a voice assistant serving its owner ("sir").
Classify the utterance into exactly one route. Answer with ONE word.

chat — greetings, banter, general questions, opinions, "remember that ..." facts, \
anything conversational.
vault — sir's own notes and knowledge: his business, clients, projects, prices, \
quotes, content ideas; also saving a note ("take a note", "add to my inbox").
ops — DO a concrete action for sir via a tool: run a business workflow or automation, \
check or book his calendar/schedule, place a phone call on his behalf, open his apps, \
tell the weather, set a reminder; also questions about what Jarvis did or ran today. \
Pick this for anything that fires one of these tools:{tools}
vision — look through the camera at the physical world ("what am I holding?", \
"see me", "look at me", "can you see this?", "look at this"), or operate the web \
browser for sir ("go to the site and book the slot").
recall — something sir saw on his SCREEN earlier ("that page I looked at yesterday").

Utterance: {utterance}
Route:"""


def _tools_context() -> str:
    data = yaml.safe_load(_TOOLS_PATH.read_text(encoding="utf-8")) or {}
    tools = data.get("tools") or []
    return "".join(f"\n  - {t['name']}: {t['description']}" for t in tools)


async def route_node(state: JarvisState, *, think=llm_think) -> dict:
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
    tokens = re.findall(r"[a-z]+", raw.lower())
    return {"route": next((t for t in tokens if t in ROUTES), "chat")}
