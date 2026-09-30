"""voice/agent.py silence watchdog — fires only after real silence."""

import asyncio
import time

from tests.unit.test_agent import FakeBrain
from voice.agent import FridayAgent, silence_watchdog


async def test_watchdog_fires_after_silence() -> None:
    agent = FridayAgent(FakeBrain(), thread_id="console")
    agent.last_activity = time.monotonic() - 999
    fired: list[int] = []
    await silence_watchdog(agent, timeout_s=0.01, poll_s=0.01, on_timeout=lambda: fired.append(1))
    assert fired == [1]


async def test_watchdog_quiet_while_sir_is_talking() -> None:
    agent = FridayAgent(FakeBrain(), thread_id="console")
    fired: list[int] = []
    task = asyncio.create_task(
        silence_watchdog(agent, timeout_s=10.0, poll_s=0.01, on_timeout=lambda: fired.append(1))
    )
    await asyncio.sleep(0.05)
    agent.last_activity = time.monotonic()  # activity keeps it quiet
    await asyncio.sleep(0.05)
    assert fired == []
    task.cancel()
