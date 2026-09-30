"""friday · tests/unit/test_owner_lock.py — SAFETY (written before the code)

Per-turn owner-voice lock (Phase 5): when armed, every spoken turn's own audio
is scored against sir's enrolled voiceprint BEFORE the brain runs.
- a stranger mid-session is refused (nothing reaches the brain), sir passes;
- model/voiceprint unavailable while armed -> fail CLOSED (refuse);
- too little voice to judge -> ask again, don't guess;
- capability-REDUCING intents (stand down, camera/screen off, mute) work from
  ANY voice — safety beats identity; capability-RESTORING "resume" is owner-only;
- disarmed = exactly today's behaviour (no scoring at all).
"""

from types import SimpleNamespace

import numpy as np
import pytest

from config.settings import get_settings
from voice.agent import FridayAgent
from voice.owner_lock import REFUSALS, OwnerLock

SR = 16_000


def _voice(seconds: float = 1.5) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)


def _lock(score, *, armed: bool = True, threshold: float = 0.5) -> OwnerLock:
    return OwnerLock(armed=armed, score=score, threshold=threshold)


def test_owner_passes_and_stranger_is_refused() -> None:
    assert _lock(lambda pcm: 0.82).verdict(_voice()) == "owner"
    assert _lock(lambda pcm: 0.12).verdict(_voice()) == "stranger"


def test_unavailable_verifier_fails_closed() -> None:
    assert _lock(lambda pcm: None).verdict(_voice()) == "unavailable"

    def boom(pcm):
        raise RuntimeError("onnx failed")

    assert _lock(boom).verdict(_voice()) == "unavailable"


def test_too_little_voice_asks_again() -> None:
    assert _lock(lambda pcm: 0.99).verdict(_voice(0.3)) == "too_short"
    assert _lock(lambda pcm: 0.99).verdict(np.zeros(SR * 2, np.float32)) == "too_short"


def test_disarmed_never_scores() -> None:
    def must_not_run(pcm):
        raise AssertionError("scored while disarmed")

    assert _lock(must_not_run, armed=False).verdict(_voice()) == "unlocked"


def test_buffer_resamples_to_16k_and_is_taken_once() -> None:
    lock = _lock(lambda pcm: 0.9)
    frame = (np.ones(2400, np.int16) * 1000).tobytes()  # 100ms at 24kHz (console mode)
    for _ in range(10):
        lock.feed(frame, sample_rate=24_000, channels=1)
    pcm = lock.take()
    assert pcm.dtype == np.float32 and abs(len(pcm) - SR) < 20  # 1s at 16kHz
    assert len(lock.take()) == 0  # consumed per turn


# --- the gate inside the voice agent ---------------------------------------------------


class _Brain:
    def __init__(self) -> None:
        self.calls = 0

    async def astream(self, payload, config, *, stream_mode=None):
        self.calls += 1
        yield "updates", {"chat": {"reply": "Indeed, sir."}}


def _ctx(text: str) -> SimpleNamespace:
    return SimpleNamespace(items=[SimpleNamespace(role="user", text_content=text)])


@pytest.fixture
def control(tmp_path, monkeypatch):
    for var, name in (("STAND_DOWN_FILE", "stand_down"), ("CAMERA_OFF_FILE", "camera_off"),
                      ("SCREEN_OFF_FILE", "screen_off")):
        monkeypatch.setenv(var, str(tmp_path / name))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _agent(score) -> tuple[FridayAgent, _Brain]:
    brain = _Brain()
    lock = _lock(score)
    agent = FridayAgent(brain, "t", sense=lambda: None, lock=lock, audit=lambda *a: None)
    return agent, brain


async def _say(agent: FridayAgent, text: str) -> list[str]:
    agent.lock.feed((np.sin(np.arange(24_000) / 7) * 9000).astype(np.int16).tobytes(),
                    sample_rate=24_000, channels=1)  # 1s of "speech" for this turn
    return [c async for c in agent.llm_node(_ctx(text), [], None)]


async def test_stranger_mid_session_never_reaches_the_brain(control) -> None:
    agent, brain = _agent(lambda pcm: 0.1)
    assert await _say(agent, "send me a summary") == [REFUSALS["stranger"]]
    assert brain.calls == 0


async def test_owner_turn_reaches_the_brain(control) -> None:
    agent, brain = _agent(lambda pcm: 0.9)
    assert await _say(agent, "how's my day") == ["Indeed, sir."]
    assert brain.calls == 1


async def test_any_voice_can_stand_down_or_cut_but_not_resume(control) -> None:
    agent, brain = _agent(lambda pcm: 0.1)  # a stranger
    assert await _say(agent, "stand down") == ["Standing down, sir."]
    assert (control / "stand_down").exists()
    assert await _say(agent, "camera off") == ["Camera disabled, sir."]
    assert await _say(agent, "resume") == [REFUSALS["stranger"]]  # restoring = owner-only
    assert (control / "camera_off").exists() and brain.calls == 0


async def test_each_turn_is_scored_on_its_own_audio_only(control) -> None:
    """A reducing intent's audio must not leak into the NEXT turn's score."""
    heard: list[int] = []

    def score(pcm):
        heard.append(len(pcm))
        return 0.1  # a stranger

    agent, brain = _agent(score)
    agent.lock.feed((np.sin(np.arange(48_000) / 7) * 9000).astype(np.int16).tobytes(),
                    sample_rate=24_000, channels=1)  # sir: 2s "camera off"
    assert [c async for c in agent.llm_node(_ctx("camera off"), [], None)] == [
        "Camera disabled, sir."]
    assert await _say(agent, "send me a summary") == [REFUSALS["stranger"]]
    assert heard and heard[-1] < 17_000  # ~1s of the stranger only, not 3s mixed
    assert brain.calls == 0


async def test_short_confirm_is_asked_again_and_gate_stays_parked(control) -> None:
    agent, brain = _agent(lambda pcm: 0.9)
    agent.pending_confirm = True
    agent.lock.feed((np.sin(np.arange(9_600) / 7) * 9000).astype(np.int16).tobytes(),
                    sample_rate=24_000, channels=1)  # a bare "Yes." ~0.4s
    out = [c async for c in agent.llm_node(_ctx("Yes."), [], None)]
    assert out == [REFUSALS["too_short"]]
    assert agent.pending_confirm is True and brain.calls == 0  # nothing ran, gate still parked


async def test_spoken_kill_is_audited_as_a_kill_command(control) -> None:
    rows = []
    brain = _Brain()
    agent = FridayAgent(brain, "t", sense=lambda: None, lock=_lock(lambda pcm: 0.1),
                        audit=lambda kind, detail: rows.append((kind, detail)))
    await _say(agent, "stand down")
    assert ("kill_command", "spoken") in rows
