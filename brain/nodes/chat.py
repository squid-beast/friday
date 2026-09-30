"""friday · brain/nodes/chat.py

Direct Sonnet answer with the Friday persona (config/persona.md — which carries
the 3-sentence spoken cap). Also home of persona() for the other nodes.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langgraph.config import get_config, get_stream_writer

from adapters.llm import think as llm_think
from adapters.llm import think_stream as llm_think_stream
from brain.state import FridayState, Message, assistant_reply

log = logging.getLogger(__name__)


def _wants_token_stream() -> bool:
    """True only when the voice agent asked for token streaming (astream custom).
    ainvoke/text and direct unit-test calls fall through to the blocking path."""
    try:
        return bool(get_config().get("configurable", {}).get("stream_tokens"))
    except RuntimeError:
        return False

_PERSONA_PATH = Path(__file__).resolve().parents[2] / "config" / "persona.md"
_HISTORY_MESSAGES = 12
LLM_APOLOGY = "Apologies, sir — my reasoning engine is unreachable."


@lru_cache
def persona() -> str:
    return _PERSONA_PATH.read_text(encoding="utf-8")


def transcript(messages: list[Message], limit: int = _HISTORY_MESSAGES) -> str:
    lines = [
        f"{'Sir' if m['role'] == 'user' else 'Friday'}: {m['content']}"
        for m in messages[-limit:]
    ]
    return "\n".join(lines)


async def chat_node(state: FridayState, *, think=llm_think, stream=llm_think_stream) -> dict:
    prompt = (
        "Continue this spoken conversation. Reply with Friday's next line only.\n\n"
        f"{transcript(state.messages)}\nFriday:"
    )
    if _wants_token_stream():
        try:
            writer = get_stream_writer()
            parts: list[str] = []
            async for delta in stream(prompt, system=persona()):
                writer(delta)  # -> the voice pipeline speaks this token now
                parts.append(delta)
            return assistant_reply("".join(parts).strip())
        except Exception:
            log.warning("chat stream failed", exc_info=True)
            return assistant_reply(LLM_APOLOGY)
    try:
        reply = (await think(prompt, system=persona())).strip()
    except Exception:
        log.warning("chat LLM call failed", exc_info=True)
        reply = LLM_APOLOGY
    return assistant_reply(reply)
