"""friday · voice/agent.py

LiveKit Agents worker: VAD -> STT -> brain graph -> TTS with barge-in.
Since Phase 2 the reply comes from the LangGraph brain; since Phase 3 every
transcript hits client/local_intents FIRST (PLAN §1.5: local overrides beat
cloud) — kill phrases never reach the graph, and a silence watchdog touches
the stand-down control file so the daemon ends idle sessions.

Run:  uv run python -m voice.agent console   # local mic/speakers, no server
      uv run python -m voice.agent dev       # against the dockerized LiveKit
"""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from langgraph.types import Command
from livekit import agents

from adapters.apps import launch_apps
from adapters.llm import get_llm
from adapters.stt import get_stt, get_vad
from adapters.tts import get_tts
from brain.brief import morning_brief
from brain.checkin import checkin_line
from brain.graph import get_brain
from client.local_intents import Intent, cut, match
from config.settings import get_settings

_PERSONA_PATH = Path(__file__).resolve().parent.parent / "config" / "persona.md"
UNARMED_LINE = "That system isn't armed yet, sir."


def touch_stand_down() -> None:
    """Signal the daemon to end this session (spoken kill or silence timeout)."""
    control = Path(get_settings().stand_down_file)
    control.parent.mkdir(parents=True, exist_ok=True)
    control.touch()


async def silence_watchdog(
    agent: "FridayAgent",
    *,
    timeout_s: float | None = None,
    poll_s: float = 5.0,
    on_timeout=touch_stand_down,
) -> None:
    timeout_s = get_settings().session_silence_timeout_s if timeout_s is None else timeout_s
    while True:
        await asyncio.sleep(poll_s)
        if time.monotonic() - agent.last_activity > timeout_s:
            on_timeout()
            return


def build_instructions() -> str:
    """The system prompt is config, not code — edit config/persona.md."""
    return _PERSONA_PATH.read_text(encoding="utf-8")


def _last_user_text(chat_ctx: Any) -> str:
    for item in reversed(chat_ctx.items):
        if getattr(item, "role", "") == "user" and item.text_content:
            return item.text_content
    return ""


class FridayAgent(agents.Agent):
    """Voice pipeline agent whose 'LLM' is the whole brain graph."""

    def __init__(self, brain: Any, thread_id: str) -> None:
        super().__init__(instructions=build_instructions())
        self._brain = brain
        self._config = {"configurable": {"thread_id": thread_id}}
        self.muted = False
        self.last_activity = time.monotonic()
        self.pending_confirm = False  # a confirm-gate question is parked in the graph

    async def llm_node(  # replaces the default LLM step of the pipeline
        self, chat_ctx: Any, tools: Any, model_settings: Any
    ) -> AsyncIterator[str]:
        utterance = _last_user_text(chat_ctx)
        if not utterance:
            return
        self.last_activity = time.monotonic()
        intent = match(utterance)  # offline check BEFORE any graph/LLM dispatch
        if intent is Intent.STAND_DOWN:
            yield "Standing down, sir."
            touch_stand_down()
            return
        if intent in (Intent.CAMERA_OFF, Intent.SCREEN_OFF):
            yield cut(intent)  # offline: flag + pkill, no graph, no network
            return
        if intent is Intent.MUTE:
            self.muted = True
            return
        if intent is Intent.RESUME:
            self.muted = False
            yield cut(intent)  # clears capture flags; speaks "At your service, sir."
            return
        if self.muted:
            return  # listening silently — no speech, no tokens (and no gate resume)
        if self.pending_confirm:
            self.pending_confirm = False
            payload: Any = Command(resume=utterance)  # the answer to "Shall I proceed, sir?"
        else:
            payload = {"messages": [{"role": "user", "content": utterance}]}
        config = {"configurable": {**self._config["configurable"], "stream_tokens": True}}
        streamed = False
        final_reply: str | None = None
        interrupt_q: str | None = None
        async for mode, chunk in self._brain.astream(
            payload, config, stream_mode=["custom", "updates"]
        ):
            if mode == "custom" and isinstance(chunk, str):
                streamed = True
                yield chunk  # a reply token — spoken as it arrives, not at the end
            elif mode == "updates":
                if "__interrupt__" in chunk:  # confirm gate parked a question
                    interrupt_q = chunk["__interrupt__"][0].value["question"]
                else:  # a non-streaming node (vault/ops/vision) set the whole reply
                    for out in chunk.values():
                        if isinstance(out, dict) and out.get("reply"):
                            final_reply = out["reply"]
        if interrupt_q is not None:
            self.pending_confirm = True
            yield interrupt_q
        elif not streamed and final_reply is not None:
            yield final_reply


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    brain = await get_brain()
    session = agents.AgentSession(
        vad=get_vad(),
        stt=get_stt(),
        llm=get_llm(),  # unused by llm_node; keeps pipeline internals happy
        tts=get_tts(),
    )
    agent = FridayAgent(brain, thread_id=ctx.room.name or "local")
    await session.start(agent=agent, room=ctx.room)
    agent.watchdog = asyncio.create_task(silence_watchdog(agent))  # ref kept against GC
    brief = await morning_brief()  # non-None only on the first wake of the day
    await session.say(brief or "At your service, sir.")  # greet FIRST — fast to first word
    await asyncio.to_thread(launch_apps)  # EVERY wake: open sir's apps + tabs + the cockpit
    checkin = await checkin_line()  # then the warm, caring question (its own utterance)
    if checkin:
        await session.say(checkin)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
