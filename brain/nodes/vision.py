"""friday · brain/nodes/vision.py

The eyes, three ways:
- recall_node: screenpipe search -> grounded persona answer (route "recall").
- vision_select_node: fast-classify camera-look vs browser-task, persist the
  choice in state.pending_action (interrupt replay safety, same pattern as ops).
- vision_execute_node: camera = single frame + moondream + persona line;
  browser = confirm gate FIRST, then browser-use with the max-steps cap.
Every sight and browser task lands in the audit log.
"""

import logging

from adapters import browser as browser_adapter
from adapters import camera as camera_adapter
from adapters import screenpipe as screenpipe_adapter
from adapters.llm import think as llm_think
from audit.log import log_tool
from brain.confirm import ask_confirmation
from brain.nodes.chat import persona
from brain.nodes.ops import ABORTED
from brain.state import FridayState, assistant_reply, last_user

log = logging.getLogger(__name__)

RECALL_OFF = "Screen watching is off, sir."
RECALL_APOLOGY = "I can't reach the screen archive, sir."
RECALL_EMPTY = "Nothing in the screen archive for that, sir."
CAMERA_CUT = "The camera is disabled, sir."
SIGHT_APOLOGY = "My eyes aren't available right now, sir."
BROWSER_APOLOGY = "The browser task failed, sir."

_RECALL_PROMPT = """\
Answer sir's question using ONLY these OCR snippets from his own screen
(newest data wins; mention when he saw it if helpful). If they don't contain
the answer, say so plainly. Speak as Friday.

Question: {question}

Screen snippets:
{context}"""

_CLASSIFY_PROMPT = """\
Sir said: "{utterance}"
Is he asking Friday to LOOK through the camera at something physical, or to
OPERATE the web browser? Reply with exactly "camera", or "browser: <the task
restated as one clear instruction>"."""

_SIGHT_PROMPT = """\
Sir asked: "{question}"
The camera sees: {sight}
Answer him in ONE spoken sentence, in character."""

_BROWSER_DONE_PROMPT = """\
The browser task finished and reported:
{result}
Tell sir the outcome in at most two spoken sentences, in character."""


async def recall_node(
    state: FridayState, *, think=llm_think, screen_search=screenpipe_adapter.search
) -> dict:
    utterance = last_user(state.messages)
    try:
        hits = await screen_search(utterance)
    except PermissionError:
        return assistant_reply(RECALL_OFF)
    except Exception:
        log.warning("screenpipe search failed", exc_info=True)
        return assistant_reply(RECALL_APOLOGY)
    if not hits:
        return assistant_reply(RECALL_EMPTY)
    context = "\n".join(
        f"[{h.timestamp} · {h.app} · {h.window}] {h.text}" for h in hits
    )
    try:
        reply = (
            await think(
                _RECALL_PROMPT.format(question=utterance, context=context), system=persona()
            )
        ).strip()
    except Exception:
        log.warning("recall synthesis failed", exc_info=True)
        reply = "I found matches on your screen, sir, but my reasoning engine is unreachable."
    return assistant_reply(reply)


async def vision_select_node(state: FridayState, *, think=llm_think) -> dict:
    utterance = last_user(state.messages)
    try:
        raw = (await think(_CLASSIFY_PROMPT.format(utterance=utterance), fast=True)).strip()
    except Exception:
        log.warning("vision classify failed", exc_info=True)
        return {"pending_action": f"camera:{utterance}"}
    if raw.lower().startswith("browser"):
        task = raw.partition(":")[2].strip() or utterance
        return {"pending_action": f"browser:{task}"}
    return {"pending_action": f"camera:{utterance}"}


async def vision_execute_node(
    state: FridayState,
    *,
    think=llm_think,
    look=camera_adapter.look,
    browse=browser_adapter.run_task,
    confirm=ask_confirmation,
    audit=log_tool,
) -> dict:
    kind, _, payload = state.pending_action.partition(":")
    if kind == "browser":
        return await _run_browser(payload, think, browse, confirm, audit)
    return await _run_camera(payload, think, look, audit)


async def _run_camera(question: str, think, look, audit) -> dict:
    try:
        sight = await look(question)
    except PermissionError:
        return {**assistant_reply(CAMERA_CUT), "pending_action": ""}
    except Exception:
        log.warning("camera look failed", exc_info=True)
        return {**assistant_reply(SIGHT_APOLOGY), "pending_action": ""}
    audit("camera_look", question[:80], sight, confirmed=True)
    try:
        reply = (
            await think(_SIGHT_PROMPT.format(question=question, sight=sight), system=persona())
        ).strip()
    except Exception:
        reply = f"{sight}, sir."
    return {**assistant_reply(reply), "pending_action": ""}


async def _run_browser(task: str, think, browse, confirm, audit) -> dict:
    # Replay-safe: nothing above the gate but string handling.
    if not confirm(f"That will have me driving the web — {task[:80]}. Shall I proceed, sir?"):
        audit("browser_task", task[:80], "aborted: no spoken yes", confirmed=False)
        return {**assistant_reply(ABORTED), "pending_action": ""}
    try:
        result = await browse(task)
    except Exception:
        log.warning("browser task failed", exc_info=True)
        audit("browser_task", task[:80], "failed", confirmed=True)
        return {**assistant_reply(BROWSER_APOLOGY), "pending_action": ""}
    audit("browser_task", task[:80], result, confirmed=True)
    try:
        reply = (
            await think(_BROWSER_DONE_PROMPT.format(result=result), system=persona())
        ).strip()
    except Exception:
        reply = "The browser task is done, sir."
    return {**assistant_reply(reply), "pending_action": ""}
