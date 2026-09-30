"""jarvis-life-os · brain/nodes/ops.py

Ops in two nodes, because interrupt() REPLAYS its node on resume:
- ops_select: Haiku picks the workflow (or answers "what did you do today")
  and persists the choice in state.pending_tool.
- ops_execute: deterministic lookup -> risk gate (interrupt for confirm) ->
  execute via the adapter path -> audit -> spoken summary. Everything before
  the gate is a plain dict lookup, so the replay can never switch tools.

Never imports vendor SDKs (CONVENTIONS.md) — adapters resolve by
"module:function" path at execution time.
"""

import importlib
import logging
import re

from adapters.llm import think as llm_think
from audit.log import log_tool, today
from brain.confirm import ask_confirmation, ask_pin
from brain.nodes.chat import persona
from brain.state import JarvisState, assistant_reply, last_user
from config.settings import get_settings
from config.tools import Tool, load_tools

log = logging.getLogger(__name__)

NO_TOOLS = "I have no workflows registered yet, sir."
NO_MATCH = "I don't have a workflow for that, sir."
BLOCKED_LINE = "That workflow is blocked, sir. I won't be running it."
ABORTED = "Very well, sir. Nothing was executed."
NO_PIN_SET = "No PIN is configured, sir. That workflow stays locked."
PIN_REFUSED = "That's not the code, sir. Nothing was executed."
_AUDIT_RE = re.compile(
    r"\bwhat (did you do|have you done)\b|\bdid you (run|do) anything\b", re.IGNORECASE
)

_SELECT_PROMPT = """\
Sir asked: "{utterance}"
Pick the ONE workflow that matches, from:
{catalog}
Reply with exactly the workflow name, or NONE."""

_SUMMARY_PROMPT = """\
The tool "{name}" just ran and returned:
{result}
Relay the outcome to sir in at most three spoken sentences, in character."""


async def _default_execute(tool: Tool, utterance: str) -> str:
    """Tool-adapter contract (Phase D2): async fn(arg, utterance) -> spoken-ish str.
    arg = the tool's webhook_path (may be ""); utterance = what sir actually said,
    so adapters like calendar can parse titles/times from it."""
    module_name, _, func_name = tool.adapter.partition(":")
    fn = getattr(importlib.import_module(module_name), func_name)
    return await fn(tool.webhook_path, utterance)


async def _audit_report(think, audit_read) -> dict:
    events = audit_read()
    if not events:
        return assistant_reply("Nothing in the log today, sir.")
    lines = "; ".join(f"{e.kind}: {e.detail[:80]}" for e in events[-20:])
    try:
        reply = (
            await think(
                f"Today's activity log: {lines}\n"
                "Report it to sir in at most two spoken sentences, in character.",
                system=persona(),
            )
        ).strip()
    except Exception:
        log.warning("audit summary failed", exc_info=True)
        reply = f"I logged {len(events)} events today, sir."
    return assistant_reply(reply)


async def ops_select_node(
    state: JarvisState, *, think=llm_think, tools=load_tools, audit_read=today
) -> dict:
    utterance = last_user(state.messages)
    if _AUDIT_RE.search(utterance):
        return {**await _audit_report(think, audit_read), "pending_tool": ""}
    registry = tools()
    if not registry:
        return {**assistant_reply(NO_TOOLS), "pending_tool": ""}
    catalog = "\n".join(f"- {t.name}: {t.description}" for t in registry)
    try:
        raw = await think(
            _SELECT_PROMPT.format(utterance=utterance, catalog=catalog), fast=True
        )
    except Exception:
        log.warning("tool selection failed", exc_info=True)
        return {**assistant_reply(NO_MATCH), "pending_tool": ""}
    tokens = set(re.findall(r"[a-z0-9_]+", raw.lower()))
    tool = next((t for t in registry if t.name.lower() in tokens), None)
    if tool is None:
        return {**assistant_reply(NO_MATCH), "pending_tool": ""}
    return {"pending_tool": tool.name}


async def ops_execute_node(
    state: JarvisState,
    *,
    think=llm_think,
    tools=load_tools,
    execute=_default_execute,
    confirm=ask_confirmation,
    pin_check=ask_pin,
    audit=log_tool,
) -> dict:
    # Replay-safe zone: nothing above the gates but deterministic lookups.
    tool = next((t for t in tools() if t.name == state.pending_tool), None)
    if tool is None:  # registry edited mid-flight; refuse rather than guess
        return {**assistant_reply(NO_MATCH), "pending_tool": ""}
    if tool.risk == "blocked":
        audit(tool.name, tool.webhook_path, "refused: blocked", confirmed=False)
        return {**assistant_reply(BLOCKED_LINE), "pending_tool": ""}
    if tool.risk == "pin":
        if not get_settings().jarvis_pin:
            audit(tool.name, tool.webhook_path, "refused: no pin configured", confirmed=False)
            return {**assistant_reply(NO_PIN_SET), "pending_tool": ""}
        if not pin_check(f"{tool.name} is PIN-protected, sir. Your code, please."):
            # never log what was actually said — the audit is not a PIN dump
            audit(tool.name, tool.webhook_path, "aborted: pin refused", confirmed=False)
            return {**assistant_reply(PIN_REFUSED), "pending_tool": ""}
    if tool.risk == "confirm" and not confirm(
        f"That will run {tool.name}. Shall I proceed, sir?"
    ):
        audit(tool.name, tool.webhook_path, "aborted: no spoken yes", confirmed=False)
        return {**assistant_reply(ABORTED), "pending_tool": ""}
    try:
        result = await execute(tool, last_user(state.messages))
    except Exception:
        log.warning("tool %s failed", tool.name, exc_info=True)
        audit(tool.name, tool.webhook_path, "failed: unreachable/error", confirmed=True)
        return {**assistant_reply(f"I couldn't run {tool.name}, sir."), "pending_tool": ""}
    audit(tool.name, tool.webhook_path, result, confirmed=True)
    try:
        reply = (
            await think(_SUMMARY_PROMPT.format(name=tool.name, result=result), system=persona())
        ).strip()
    except Exception:
        reply = f"Done, sir. {tool.name} has run."
    return {**assistant_reply(reply), "pending_tool": ""}
