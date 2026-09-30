"""friday · brain/nodes/memory_writer.py

Post-turn fact extraction into long-term memory. Fire-and-forget: the node
schedules a background task and returns immediately, so the spoken reply is
never delayed. Extraction failure is a logged warning, never a crash.
"""

import asyncio
import logging
import re

from adapters import memory as memory_adapter
from adapters.llm import think as llm_think
from brain import pending_question
from brain.state import FridayState, last_user

log = logging.getLogger(__name__)

# Extraction gate: only pay the LLM call when the utterance could plausibly carry
# a lasting fact. Permissive on purpose — a wasted cheap call beats a lost memory,
# so this only skips clearly fact-free turns (questions, commands, small talk).
_FACT_HINT = re.compile(
    r"\d|remember|note|forget|call me|name is|birthday|anniversary|prefer|favou?rite"
    r"|i am|i'm|i like|i love|i hate|i use|i work|i live|decided|always|never|from now on",
    re.IGNORECASE,
)

_PROMPT = """\
{asked}Sir said: "{utterance}"

List lasting personal facts worth remembering from this (preferences, people,
numbers, codes, dates, decisions). One per line, each a standalone statement
starting with "Sir". Ignore small talk and questions. If none, reply NONE."""

_tasks: set[asyncio.Task] = set()


async def memory_writer_node(
    state: FridayState, *, think=llm_think, remember=memory_adapter.remember
) -> dict:
    utterance = last_user(state.messages)
    asked = pending_question.take()  # answering a check-in? always worth remembering
    if utterance and (asked or _FACT_HINT.search(utterance)):
        task = asyncio.create_task(
            _extract_and_store(utterance, think=think, remember=remember, asked=asked))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return {}


async def _extract_and_store(utterance: str, *, think, remember, asked: str = "") -> None:
    context = f'Friday asked: "{asked}"\n' if asked else ""
    try:
        raw = await think(_PROMPT.format(asked=context, utterance=utterance), fast=True)
        for line in raw.splitlines():
            fact = line.strip("-•* \t")
            if fact and fact.upper() != "NONE":
                await remember(fact)
    except Exception:
        log.warning("memory extraction failed", exc_info=True)


async def drain() -> None:
    """Await outstanding extractions (used by tests and shutdown)."""
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
