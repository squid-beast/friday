"""friday · tests/unit/test_gesture_motion.py

gesture/ G3 — motion gestures (swipe/zoom/pause over frames), the actuator's
keyboard shortcuts, and the agent actuating motion actions."""


# --- G3 motion gestures ---

def _palm_at(x: float) -> dict:
    return {"gesture": "open_palm", "landmarks": {"wrist": [x, 0.5]}}


def _fist_at(x: float) -> dict:
    return {"gesture": "fist", "landmarks": {"wrist": [x, 0.5]}}


def test_motion_swipe_right() -> None:
    from gesture.motion import Motion

    m = Motion(cooldown_s=0.0)
    assert m.update([_palm_at(0.3)], 0.0) is None
    assert m.update([_palm_at(0.4)], 0.1) is None
    assert m.update([_palm_at(0.6)], 0.2) == "swipe_right"  # dx 0.3 > swipe_dx


def test_motion_pause_on_held_palm() -> None:
    from gesture.motion import Motion

    m = Motion()
    out = None
    for t in (0.0, 0.2, 0.4, 0.5):  # palm stationary for > hold_s
        out = m.update([_palm_at(0.5)], t)
    assert out == "pause"


def test_motion_zoom_in_then_out() -> None:
    from gesture.motion import Motion

    m = Motion(cooldown_s=0.0)

    def two(gap: float) -> list:
        return [_fist_at(0.4), _fist_at(0.4 + gap)]

    assert m.update(two(0.1), 0.0) is None            # baseline distance
    assert m.update(two(0.3), 0.1) == "zoom_in"       # spread apart
    assert m.update(two(0.1), 0.2) == "zoom_out"      # come together


def test_motion_cooldown_suppresses_refire() -> None:
    from gesture.motion import Motion

    m = Motion(cooldown_s=0.7)
    m.update([_palm_at(0.3)], 0.0)
    assert m.update([_palm_at(0.6)], 0.1) == "swipe_right"
    m.update([_palm_at(0.3)], 0.2)
    assert m.update([_palm_at(0.6)], 0.3) is None  # within cooldown -> suppressed


def test_actuator_shortcuts_map_to_the_right_keys(monkeypatch) -> None:
    from gesture import actuator

    calls = []
    monkeypatch.setattr(actuator, "key", lambda kc, **kw: calls.append((kc, kw)))
    actuator.switch_space("right")
    actuator.switch_space("left")
    actuator.zoom("in")
    actuator.zoom("out")
    assert calls == [(actuator.KEY_RIGHT, {"ctrl": True}), (actuator.KEY_LEFT, {"ctrl": True}),
                     (actuator.KEY_EQUALS, {"cmd": True}), (actuator.KEY_MINUS, {"cmd": True})]


def test_agent_actuates_motion_actions(monkeypatch) -> None:
    from gesture import actuator, agent

    calls = []
    monkeypatch.setattr(actuator, "switch_space", lambda d: calls.append(("space", d)))
    monkeypatch.setattr(actuator, "zoom", lambda d: calls.append(("zoom", d)))
    agent._actuate_motion("swipe_left")
    agent._actuate_motion("zoom_in")
    assert calls == [("space", "left"), ("zoom", "in")]
