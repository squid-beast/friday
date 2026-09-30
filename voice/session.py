"""friday · voice/session.py

The LiveKit job entrypoint: build the session (VAD -> STT -> brain -> TTS), then
the wake routine — mood refresh from real signals, greeting, optional app
launch, and the caring check-in (or the follow-up to a proactive nudge). With
the owner-voice lock armed, preemptive generation is off so every turn is scored
on its COMPLETE audio, and an UNVERIFIED wake (no wake verifier) gets a neutral
greeting only — nothing personal is spoken before the lock has heard sir.
Started by `python -m voice.agent console|dev`.
"""

import asyncio
import contextlib

from livekit import agents

from adapters.apps import launch_apps
from adapters.llm import get_llm
from adapters.stt import get_stt, get_vad
from adapters.tts import get_tts
from brain import mood_sense, pending_question
from brain.brief import morning_brief
from brain.checkin import checkin_line
from brain.graph import get_brain
from config.settings import get_settings
from voice.agent import FridayAgent, silence_watchdog
from voice.owner_lock import OwnerLock
from voice.styling import Styler


def session_options(lock: OwnerLock) -> dict:
    """With the turn lock armed, score each COMPLETE turn: no brain run on a preflight."""
    return {"turn_handling": {"preemptive_generation": {"enabled": False}}} if lock.armed else {}


def wake_is_private(lock: OwnerLock, settings) -> bool:
    """May the wake routine speak PERSONAL things (brief, check-in, nudge, apps)?
    Only if nobody is gated (lock off) or the wake itself was voice-verified."""
    return not lock.armed or bool(settings.wake_verifier_path)


async def wake_routine(say, *, private: bool, brief=morning_brief, checkin=checkin_line,
                       launch=launch_apps, pending=pending_question) -> None:
    """Greeting first (fast to first word); personal content only when private."""
    greeting = (await brief() if private else None) or "At your service, sir."
    await say(greeting, "greeting")
    if not private:
        return  # unverified wake + armed lock: no brief, no nudge, no apps — the lock decides
    await asyncio.to_thread(launch, on_wake=True)  # only if WAKE_APPS_ENABLED
    followup = pending.take_for_wake()  # a proactive nudge sent while away?
    line = f"Earlier I wondered — {followup}" if followup else await checkin()
    if line:
        pending.mark(line)  # so his answer is always remembered
        await say(line, "checkin")


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    brain = await get_brain()
    lock = OwnerLock.from_settings()
    session = agents.AgentSession(
        vad=get_vad(),
        stt=get_stt(),
        llm=get_llm(),  # unused by llm_node; keeps pipeline internals happy
        tts=get_tts(),
        **session_options(lock),
    )
    styler = Styler(tts=session.tts)
    session.on("agent_state_changed",  # a gated line finished playing -> tone may return
               lambda ev: styler.release() if ev.new_state == "listening" else None)
    agent = FridayAgent(brain, thread_id=ctx.room.name or "local", styler=styler, lock=lock)
    await session.start(agent=agent, room=ctx.room)
    agent.watchdog = asyncio.create_task(silence_watchdog(agent))  # ref kept against GC
    with contextlib.suppress(Exception):  # real signals -> mood before the first word
        await mood_sense.refresh_at_wake()

    async def say(text: str, kind: str) -> None:
        await session.say(styler.line(text, kind))

    await wake_routine(say, private=wake_is_private(lock, get_settings()))
