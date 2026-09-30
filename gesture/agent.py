"""jarvis-life-os · gesture/agent.py

G1/G2 agent: run the native tracker, publish per-hand landmarks + gestures for
the /gesture screen, write the live camera frame, and — only while cursor control
is explicitly armed — drive the real mouse from the pointing hand.

Safety: cursor control is OFF unless the arm flag (gesture_control_file) exists
(the UI toggle / a voice command creates it), and an OPEN PALM instantly clears
it (pause). Honors the camera_off cut. Opt-in, manual (no launchd):

    make gesture                      # build the native binary (once)
    uv run python -m gesture.agent    # publish state + frame; open /gesture
"""

import contextlib
import json
import subprocess
import time
from pathlib import Path

from config.settings import get_settings
from gesture import actuator
from gesture.classifier import classify
from gesture.motion import Motion
from gesture.spike import _BINARY


def _actuate_motion(action: str) -> None:
    """Map a G3 motion action to a real keystroke (swipe -> Space, spread -> zoom)."""
    kind, _, direction = action.partition("_")
    if kind == "swipe":
        actuator.switch_space(direction)
    elif kind == "zoom":
        actuator.zoom(direction)


def _tuply(lm: dict) -> dict:
    return {k: tuple(v) for k, v in lm.items()}


def frame_state(payload: dict) -> dict | None:
    """One native frame {"hands":[{chirality,landmarks}]} -> published state, or None."""
    hands_in = payload.get("hands")
    if not isinstance(hands_in, list):
        return None
    hands = []
    for h in hands_in:
        lm = h.get("landmarks") if isinstance(h, dict) else None
        if isinstance(lm, dict) and lm:
            hands.append({"chirality": h.get("chirality", "unknown"),
                          "gesture": classify(_tuply(lm)), "landmarks": lm})
    return {"hands": hands, "ts": time.time()}


def pointing_hand(hands: list) -> dict | None:
    """The hand that drives the cursor: whichever is pinching, else pointing."""
    for want in ("pinch", "point"):
        for h in hands:
            if h["gesture"] == want:
                return h
    return None


class Cursor:
    """Edge-triggered control: move on point/pinch, click once per pinch."""

    def __init__(self, *, size, move=actuator.move, click=actuator.click) -> None:
        self._w, self._h = size
        self._move, self._click = move, click
        self._pinched = False

    def drive(self, hand: dict) -> None:
        tip = hand["landmarks"].get("index_tip")
        if not tip:
            return
        px, py = actuator.to_screen(tip[0], tip[1], self._w, self._h)
        self._move(px, py)
        pinch = hand["gesture"] == "pinch"
        if pinch and not self._pinched:
            self._click(px, py)  # click only on the pinch edge, not every frame
        self._pinched = pinch


def _publish(state_file: Path, data: dict) -> None:
    tmp = state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(state_file)


def run(*, binary: Path = _BINARY) -> int:
    s = get_settings()
    state_file, camera_off = Path(s.gesture_state_file), Path(s.camera_off_file)
    control_on, frame = Path(s.gesture_control_file), Path(s.gesture_frame_file)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if not binary.exists():
        print("Build the native tracker first:  make gesture")
        return 1
    proc = subprocess.Popen([str(binary), str(frame)], stdout=subprocess.PIPE,
                            text=True, bufsize=1)
    cursor, motion = None, Motion()
    try:
        for line in proc.stdout or []:
            if camera_off.exists():
                break
            try:
                state = frame_state(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
            if state is None:
                continue
            if control_on.exists():
                action = motion.update(state["hands"], time.time())
                if action == "pause":
                    control_on.unlink(missing_ok=True)  # open palm held = pause
                elif action:
                    with contextlib.suppress(Exception):
                        _actuate_motion(action)  # swipe / zoom keystroke
                elif (hand := pointing_hand(state["hands"])):
                    try:
                        cursor = cursor or Cursor(size=actuator.screen_size())
                        cursor.drive(hand)
                    except Exception:  # a Quartz/permission hiccup must not kill tracking
                        pass
            state["control"] = control_on.exists()
            _publish(state_file, state)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        state_file.unlink(missing_ok=True)
        frame.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
