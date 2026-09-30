"""friday · tests/unit/test_session.py

voice/session.py wiring + the agent's stt tee: with the per-turn lock armed,
preemptive generation is off; an UNVERIFIED wake (lock armed, no wake verifier)
gets a neutral greeting and nothing personal — no brief, nudge, check-in or app
launch — while a private wake runs the whole routine; the stt tee feeds the lock
only when armed and passes every frame through untouched.
"""

from types import SimpleNamespace

import pytest

from voice import session
from voice.owner_lock import OwnerLock


def _lock(armed: bool) -> OwnerLock:
    return OwnerLock(armed=armed, score=lambda pcm: 0.9, threshold=0.5)


def test_preemptive_generation_is_off_only_when_armed() -> None:
    assert session.session_options(_lock(False)) == {}
    assert session.session_options(_lock(True)) == {
        "turn_handling": {"preemptive_generation": {"enabled": False}}}


@pytest.mark.parametrize(("armed", "verifier", "private"), [
    (False, "", True), (True, "", False), (True, "owner.joblib", True)])
def test_wake_is_private(armed: bool, verifier: str, private: bool) -> None:
    settings = SimpleNamespace(wake_verifier_path=verifier)
    assert session.wake_is_private(_lock(armed), settings) is private


class _Pending:
    def __init__(self, queued: str = "") -> None:
        self.queued, self.marked = queued, []

    def take_for_wake(self) -> str:
        q, self.queued = self.queued, ""
        return q

    def mark(self, q: str) -> None:
        self.marked.append(q)


async def _run(private: bool, pending: _Pending) -> tuple[list, list]:
    said, launched = [], []

    async def say(text, kind):
        said.append((text, kind))

    async def brief():
        return "Morning, sir. Dentist at ten."

    async def checkin():
        return "How did you sleep, sir?"

    await session.wake_routine(say, private=private, brief=brief, checkin=checkin,
                               launch=lambda **kw: launched.append(kw), pending=pending)
    return said, launched


async def test_unverified_wake_speaks_nothing_personal() -> None:
    pending = _Pending(queued="Did you eat, sir?")
    said, launched = await _run(False, pending)
    assert said == [("At your service, sir.", "greeting")]
    assert launched == [] and pending.queued == "Did you eat, sir?" and pending.marked == []


async def test_private_wake_runs_the_whole_routine() -> None:
    said, launched = await _run(True, _Pending())
    assert said == [("Morning, sir. Dentist at ten.", "greeting"),
                    ("How did you sleep, sir?", "checkin")]
    assert launched == [{"on_wake": True}]


async def test_private_wake_follows_up_a_queued_nudge_and_marks_it() -> None:
    pending = _Pending(queued="Did you eat, sir?")
    said, _ = await _run(True, pending)
    assert said[-1] == ("Earlier I wondered — Did you eat, sir?", "checkin")
    assert pending.marked == ["Earlier I wondered — Did you eat, sir?"]


@pytest.mark.parametrize("armed", [True, False])
async def test_stt_tee_feeds_the_lock_only_when_armed(monkeypatch, armed: bool) -> None:
    from livekit import agents

    from voice.agent import FridayAgent

    frames = [SimpleNamespace(data=b"\x01\x00" * 160, sample_rate=16_000, num_channels=1)
              for _ in range(3)]
    seen = []

    async def default_stt(agent, audio, settings):
        async for frame in audio:
            seen.append(frame)
            yield "event"

    monkeypatch.setattr(agents.Agent.default, "stt_node", default_stt)
    agent = FridayAgent(object(), "t", sense=lambda: None, lock=_lock(armed),
                        audit=lambda *a: None)

    async def audio():
        for f in frames:
            yield f

    events = [e async for e in agent.stt_node(audio(), None)]
    assert events == ["event"] * 3 and seen == frames  # every frame passes through
    assert len(agent.lock.take()) == (480 if armed else 0)
