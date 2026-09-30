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
import contextlib
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
from brain import mood_sense, pending_question
from brain.brief import morning_brief
from brain.checkin import checkin_line
from brain.graph import get_brain
from client.local_intents import Intent, cut, match
from config.settings import get_settings
from voice.styling import Styler

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

    def __init__(self, brain: Any, thread_id: str, *, styler: Styler | None = None,
                 sense=mood_sense.turn_update) -> None:
        super().__init__(instructions=build_instructions())
        self._brain = brain
        self.styler = styler or Styler()  # mood -> voice, safety-gated (voice/emotion.py)
        self._sense = sense  # folds this session's audit events into the mood each turn
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
        say = self.styler.line
        if intent is Intent.STAND_DOWN:
            yield say("Standing down, sir.", "kill")  # flat, tag-free: never styled
            touch_stand_down()
            return
        if intent in (Intent.CAMERA_OFF, Intent.SCREEN_OFF):
            yield say(cut(intent), "cut")  # offline: flag + pkill, no graph, no network
            return
        if intent is Intent.MUTE:
            self.muted = True
            return
        if intent is Intent.RESUME:
            self.muted = False
            yield say(cut(intent), "cut")  # clears capture flags; "At your service, sir."
            return
        if self.muted:
            return  # listening silently — no speech, no tokens (and no gate resume)
        if self.pending_confirm:
            self.pending_confirm = False
            payload: Any = Command(resume=utterance)  # the answer to "Shall I proceed, sir?"
        else:
            payload = {"messages": [{"role": "user", "content": utterance}]}
        with contextlib.suppress(Exception):  # mood is color, never a blocker
            await asyncio.to_thread(self._sense)
        config = {"configurable": {**self._config["configurable"], "stream_tokens": True}}
        streamed = False
        final_reply: str | None = None
        interrupt_q: str | None = None
        async for mode, chunk in self._brain.astream(
            payload, config, stream_mode=["custom", "updates"]
        ):
            if mode == "custom" and isinstance(chunk, str):
                yield chunk if streamed else say(chunk, "reply")  # style the FIRST token only
                streamed = True  # a reply token — spoken as it arrives, not at the end
            elif mode == "updates":
                if "__interrupt__" in chunk:  # confirm gate parked a question
                    interrupt_q = chunk["__interrupt__"][0].value["question"]
                else:  # a non-streaming node (vault/ops/vision) set the whole reply
                    for out in chunk.values():
                        if isinstance(out, dict) and out.get("reply"):
                            final_reply = out["reply"]
        if interrupt_q is not None:
            self.pending_confirm = True
            yield say(interrupt_q, "pin" if "PIN" in interrupt_q else "confirm")
        elif not streamed and final_reply is not None:
            yield say(final_reply, "reply")  # canned refusals/apologies are gated by text


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    brain = await get_brain()
    session = agents.AgentSession(
        vad=get_vad(),
        stt=get_stt(),
        llm=get_llm(),  # unused by llm_node; keeps pipeline internals happy
        tts=get_tts(),
    )
    styler = Styler(tts=session.tts)
    agent = FridayAgent(brain, thread_id=ctx.room.name or "local", styler=styler)
    await session.start(agent=agent, room=ctx.room)
    agent.watchdog = asyncio.create_task(silence_watchdog(agent))  # ref kept against GC
    with contextlib.suppress(Exception):  # real signals -> mood before the first word
        await mood_sense.refresh_at_wake()
    brief = await morning_brief()  # non-None only on the first wake of the day
    greeting = brief or "At your service, sir."
    await session.say(styler.line(greeting, "greeting"))  # greet FIRST — fast to first word
    await asyncio.to_thread(launch_apps, on_wake=True)  # only if WAKE_APPS_ENABLED
    followup = pending_question.take_for_wake()  # a proactive nudge sent while away?
    checkin = f"Earlier I wondered — {followup}" if followup else await checkin_line()
    if checkin:
        pending_question.mark(checkin)  # so his answer is always remembered
        await session.say(styler.line(checkin, "checkin"))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
