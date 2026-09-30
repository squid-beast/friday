"""friday · brain/mood.py

The emotion engine (design: docs/EMOTIONS.md). Simulated affect, honestly
scoped: five dimensions in 0..1 that decay toward a composed 0.5 baseline,
moved ONLY by real events — tool successes/failures and stand-downs from the
audit log, late-night wakes, and (at wake) remembered facts about sleep,
deadlines and wins plus today's calendar load. Rules, not LLM guesses.

Outputs: named_mood() -> (proud|worried|…|content, intensity) and a one-line
disposition() that brain/nodes/chat.persona() appends to the system prompt.
Mood never touches gates, kills, the 3-sentence cap or safety rules; the voice
layer (voice/emotion.py) decides separately whether a line may carry it.
State persists in settings.mood_path (JSON) and survives restarts.
"""

import json
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from config.settings import get_settings

DIMS = ("valence", "arousal", "warmth", "confidence", "concern")
BASELINE = 0.5
HALF_LIFE_H = 6.0  # a feeling fades by half every 6h: nothing lasts a day without cause

TRIGGERS: dict[str, dict[str, float]] = {  # docs/EMOTIONS.md trigger table
    "tool_success": {"confidence": 0.08, "valence": 0.06},
    "tool_failure": {"confidence": -0.15, "valence": -0.05},
    "late_night": {"concern": 0.15, "arousal": -0.1},
    "poor_sleep": {"concern": 0.2, "warmth": 0.05},
    "deadline_soon": {"arousal": 0.12, "concern": 0.15},
    "busy_day": {"arousal": 0.1},
    "win": {"valence": 0.15, "warmth": 0.05},
    "return_after_absence": {"warmth": 0.15},
}
_FACT_SIGNALS = {  # remembered facts -> events (checked at wake)
    "poor_sleep": re.compile(r"slept (badly|poorly|little)|no sleep|didn'?t sleep|tired|"
                             r"exhausted|insomnia|up all night", re.I),
    "deadline_soon": re.compile(r"deadline|due (today|tomorrow|friday|monday)|submit by", re.I),
    "win": re.compile(r"shipped|launched|got the (job|offer)|interview (went|passed)|won|"
                      r"closed (a|the) deal|signed", re.I),
}


class MoodState(BaseModel):
    dims: dict[str, float] = Field(default_factory=lambda: dict.fromkeys(DIMS, BASELINE))
    updated: float = 0.0  # last write (for decay)
    cursor: float = 0.0  # newest audit event already observed
    context_day: str = ""  # context signals (facts/calendar/clock) apply once per day


def _path() -> Path:
    return Path(get_settings().mood_path)


def _decayed(state: MoodState, now: float) -> MoodState:
    if state.updated:
        keep = 0.5 ** (max(0.0, now - state.updated) / 3600 / HALF_LIFE_H)
        state.dims = {d: BASELINE + (v - BASELINE) * keep for d, v in state.dims.items()}
    state.updated = now
    return state


def load_raw() -> MoodState:
    try:
        return MoodState.model_validate_json(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MoodState()


def load(now: float | None = None) -> MoodState:
    return _decayed(load_raw(), time.time() if now is None else now)


def save(state: MoodState) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(), encoding="utf-8")
    tmp.replace(path)  # atomic: a crash never leaves half a mood


def apply(state: MoodState, event: str) -> MoodState:
    if event == "kill":  # stand-down: neutral instantly, warmth untouched (never resentful)
        state.dims = {d: (v if d == "warmth" else BASELINE) for d, v in state.dims.items()}
        return state
    for dim, delta in TRIGGERS.get(event, {}).items():
        state.dims[dim] = min(1.0, max(0.0, state.dims[dim] + delta))
    return state


def events_from_audit(events) -> list[str]:
    out = []
    for e in events:
        if e.kind == "stand_down":
            out.append("kill")
        elif e.kind == "tool" and e.detail:
            try:
                result = str(json.loads(e.detail).get("result", ""))
            except ValueError:
                continue
            failed = result.startswith(("failed", "aborted"))
            out.append("tool_failure" if failed else "tool_success")
    return out


def events_from_context(facts: list[str], n_events_today: int, hour: int,
                        hours_away: float) -> list[str]:
    out = [name for name, rx in _FACT_SIGNALS.items() if any(rx.search(f) for f in facts)]
    if n_events_today >= 5:
        out.append("busy_day")
    if 0 <= hour < 5:
        out.append("late_night")
    if hours_away >= 48:
        out.append("return_after_absence")
    return out


def observe(state: MoodState, events) -> MoodState:
    """Fold audit events newer than the cursor into the mood (idempotent)."""
    fresh = [e for e in events if e.ts > state.cursor]
    for name in events_from_audit(fresh):
        apply(state, name)
    if fresh:
        state.cursor = max(e.ts for e in fresh)
    return state


def named_mood(state: MoodState, hour: int | None = None) -> tuple[str, float]:
    d = state.dims
    hour = time.localtime().tm_hour if hour is None else hour
    intensity = min(1.0, 2 * max(abs(v - BASELINE) for v in d.values()))
    if d["concern"] >= 0.65:
        return ("protective" if d["warmth"] >= 0.65 else "worried"), intensity
    if 0 <= hour < 5 and d["arousal"] <= 0.45:
        return "weary", intensity
    if d["confidence"] >= 0.62 and d["valence"] >= 0.55:
        return "proud", intensity
    if d["valence"] >= 0.68:
        return "delighted", intensity
    if d["confidence"] <= 0.38:
        return "sheepish", intensity
    if d["warmth"] <= 0.35:
        return "irritated", intensity
    return "content", intensity


def disposition(state: MoodState, hour: int | None = None) -> str:
    name, intensity = named_mood(state, hour)
    degree = "mildly" if intensity < 0.33 else "noticeably" if intensity < 0.66 else "strongly"
    return (f"Current disposition: {degree} {name}. Let it color word choice only — "
            f"never the 3-sentence cap, confirmations, or safety.")
