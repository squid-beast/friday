"""friday · voice/session.py

The LiveKit job entrypoint: build the session (VAD -> STT -> brain -> TTS), then
the wake routine — mood refresh from real signals, greeting, optional app
launch, and the caring check-in (or the follow-up to a proactive nudge). With
the owner-voice lock armed, preemptive generation is off so every turn is scored
on its COMPLETE audio. Started by `python -m voice.agent console|dev`.
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
from voice.agent import FridayAgent, silence_watchdog
from voice.owner_lock import OwnerLock
from voice.styling import Styler


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    brain = await get_brain()
    lock = OwnerLock.from_settings()
    extra = {}
    if lock.armed:  # score each COMPLETE turn: no brain run on a half-heard preflight
        extra["turn_handling"] = {"preemptive_generation": {"enabled": False}}
    session = agents.AgentSession(
        vad=get_vad(),
        stt=get_stt(),
        llm=get_llm(),  # unused by llm_node; keeps pipeline internals happy
        tts=get_tts(),
        **extra,
    )
    styler = Styler(tts=session.tts)
    agent = FridayAgent(brain, thread_id=ctx.room.name or "local", styler=styler, lock=lock)
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
