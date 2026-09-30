"""gesture/ — the whole-set classifier, the multi-hand agent, and the cursor
actuator's coordinate mapping. Synthetic hands (wrist at bottom, fingers up =
higher y). Distances are scale-normalized, so only extended-vs-curled matters."""

import json

from gesture.classifier import classify


def _hand(index=True, middle=True, ring=True, little=True, thumb_out=True, thumb=None):
    """A hand with named fingers extended/curled; thumb out (sideways) or tucked."""
    lm = {"wrist": (0.5, 0.0), "middle_mcp": (0.5, 0.3)}  # scale = 0.3
    for f, x in {"index": 0.35, "middle": 0.5, "ring": 0.6, "little": 0.7}.items():
        up = {"index": index, "middle": middle, "ring": ring, "little": little}[f]
        lm[f"{f}_mcp"] = (x, 0.3)
        lm[f"{f}_pip"] = (x, 0.4)
        lm[f"{f}_tip"] = (x, 0.9) if up else (x, 0.25)
    lm["thumb_tip"] = thumb if thumb is not None else ((0.05, 0.5) if thumb_out else (0.37, 0.28))
    return lm


def _lm(**kw):
    """The list-form landmarks the native binary would emit for such a hand."""
    return {k: list(v) for k, v in _hand(**kw).items()}


# --- classifier: the whole set ---

def test_open_palm() -> None:
    assert classify(_hand()) == "open_palm"


def test_four_is_palm_without_thumb() -> None:
    assert classify(_hand(thumb_out=False)) == "four"


def test_three() -> None:
    assert classify(_hand(little=False)) == "three"


def test_peace() -> None:
    assert classify(_hand(ring=False, little=False)) == "peace"


def test_point() -> None:
    assert classify(_hand(middle=False, ring=False, little=False)) == "point"


def test_sarinas_middle_finger() -> None:
    assert classify(_hand(index=False, ring=False, little=False)) == "sarina's middle finger"


def test_fist() -> None:
    assert classify(_hand(False, False, False, False, thumb_out=False)) == "fist"


def test_thumbs_up() -> None:
    assert classify(_hand(False, False, False, False, thumb_out=True)) == "thumbs_up"


def test_pinch() -> None:
    assert classify(_hand(thumb=(0.33, 0.86))) == "pinch"


def test_unrecognized_combo_is_none() -> None:
    assert classify(_hand(index=True, middle=False, ring=True, little=False)) == "none"
    assert classify({}) == "none"


# --- G0 spike runner: native frame line -> first hand's gesture ---

def test_gesture_for_line_first_hand() -> None:
    from gesture.spike import gesture_for_line

    frame = json.dumps({"hands": [{"chirality": "right", "landmarks": _lm()}]})
    assert gesture_for_line(frame) == "open_palm"
    assert gesture_for_line("garbage") is None
    assert gesture_for_line('{"hands": []}') is None


# --- G1/G2 agent: multi-hand state, pointer selection, cursor edge-clicks ---

def test_frame_state_classifies_each_hand() -> None:
    from gesture.agent import frame_state

    payload = {"hands": [
        {"chirality": "right", "landmarks": _lm(middle=False, ring=False, little=False)},
        {"chirality": "left", "landmarks": _lm(ring=False, little=False)},
    ]}
    st = frame_state(payload)
    assert len(st["hands"]) == 2 and "ts" in st
    assert st["hands"][0]["gesture"] == "point" and st["hands"][0]["chirality"] == "right"
    assert st["hands"][1]["gesture"] == "peace"


def test_frame_state_drops_empty_and_rejects_bad() -> None:
    from gesture.agent import frame_state

    assert frame_state({"hands": [{}]})["hands"] == []  # a hand with no landmarks
    assert frame_state({"nope": 1}) is None


def test_pointing_hand_prefers_pinch_then_point() -> None:
    from gesture.agent import pointing_hand

    hands = [{"gesture": "point", "landmarks": {}}, {"gesture": "pinch", "landmarks": {}}]
    assert pointing_hand(hands)["gesture"] == "pinch"
    assert pointing_hand([{"gesture": "point", "landmarks": {}}])["gesture"] == "point"
    assert pointing_hand([{"gesture": "open_palm", "landmarks": {}}]) is None


def test_cursor_moves_and_clicks_on_pinch_edge() -> None:
    from gesture.agent import Cursor

    moves, clicks = [], []
    c = Cursor(size=(1000, 800), move=lambda x, y: moves.append((x, y)),
               click=lambda x, y: clicks.append((x, y)))
    def at(g):
        return {"gesture": g, "landmarks": {"index_tip": (0.5, 0.5)}}

    c.drive(at("point"))
    assert len(moves) == 1 and clicks == []       # point moves, never clicks
    c.drive(at("pinch"))
    assert len(clicks) == 1                        # click on the pinch edge
    c.drive(at("pinch"))
    assert len(clicks) == 1                        # held pinch: no second click
    c.drive(at("point"))
    c.drive(at("pinch"))
    assert len(clicks) == 2                        # a fresh pinch clicks again


# --- actuator: pure coordinate mapping (Quartz calls are live-only) ---

def test_to_screen_mirrors_x_and_flips_y() -> None:
    from gesture.actuator import to_screen

    assert to_screen(0.0, 1.0, 1000, 800) == (1000.0, 0.0)
    assert to_screen(1.0, 0.0, 1000, 800) == (0.0, 800.0)
    assert to_screen(0.0, 1.0, 1000, 800, mirror=False) == (0.0, 0.0)


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
