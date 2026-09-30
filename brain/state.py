"""jarvis-life-os · brain/state.py

JarvisState — the one state object flowing through the graph (PLAN §1.6).
Phase 4 adds tool_calls/pending_confirmation when the ops node arrives.
"""

import operator
from typing import Annotated

from pydantic import BaseModel, Field

Message = dict[str, str]  # {"role": "user" | "assistant", "content": "..."}


class JarvisState(BaseModel):
    messages: Annotated[list[Message], operator.add] = Field(default_factory=list)
    route: str = ""  # chat|vault|ops|vision|recall — set by the router each turn
    reply: str = ""  # what the voice layer speaks this turn
    # Phase 4: tool chosen by ops_select, consumed by ops_execute. Persisted in the
    # checkpoint so the confirm-gate replay is deterministic — the resume must gate
    # EXACTLY the tool sir was asked about, never a re-selection.
    pending_tool: str = ""
    # Phase 5: same pattern for the eyes — "camera:<question>" | "browser:<task>",
    # written by vision_select, consumed replay-safely by vision_execute.
    pending_action: str = ""


def assistant_reply(text: str) -> dict:
    """Node return helper: speak `text` and append it to history."""
    return {"reply": text, "messages": [{"role": "assistant", "content": text}]}


def last_user(messages: list[Message]) -> str:
    return next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
