"""friday · gesture/motion.py

Motion-gesture detection over time (G3). Pure + stateful: fed the per-frame hand
list + a timestamp, it returns ONE action name or None. No I/O, no Mac control —
the agent maps actions to keystrokes.

  - swipe_left / swipe_right : an OPEN PALM moving fast horizontally
  - zoom_in / zoom_out       : TWO hands moving apart / together
  - pause                    : an OPEN PALM held still (stop control)

An open palm HELD still pauses; an open palm MOVING swipes — velocity tells them
apart. Thresholds are calibration knobs (hands/cameras vary). ponytail: tune live.
"""

from collections import deque
from math import hypot


class Motion:
    def __init__(self, *, swipe_dx: float = 0.18, zoom_dx: float = 0.12,
                 still_dx: float = 0.04, hold_s: float = 0.45,
                 cooldown_s: float = 0.7, window_s: float = 0.35) -> None:
        self.swipe_dx, self.zoom_dx, self.still_dx = swipe_dx, zoom_dx, still_dx
        self.hold_s, self.cooldown_s, self.window_s = hold_s, cooldown_s, window_s
        self._hist: deque = deque()  # (t, wrist_x) of the open-palm hand
        self._still_since: float | None = None
        self._pair_base: float | None = None
        self._last_fire = -1e9  # "never fired" — the first action is always ready

    def update(self, hands: list, now: float) -> str | None:
        ready = now - self._last_fire >= self.cooldown_s
        # zoom: two hands spreading apart / coming together
        if len(hands) >= 2:
            d = self._pair_dist(hands)
            if self._pair_base is None:
                self._pair_base = d
            elif ready and abs(d - self._pair_base) > self.zoom_dx:
                action = "zoom_in" if d > self._pair_base else "zoom_out"
                self._pair_base, self._last_fire = d, now
                return action
        else:
            self._pair_base = None
        # swipe / pause: the open-palm hand
        palm = next((h for h in hands if h["gesture"] == "open_palm"), None)
        if palm is None or not palm["landmarks"].get("wrist"):
            self._hist.clear()
            self._still_since = None
            return None
        x = palm["landmarks"]["wrist"][0]
        self._hist.append((now, x))
        while self._hist and now - self._hist[0][0] > self.window_s:
            self._hist.popleft()
        dx = x - self._hist[0][1]
        if ready and abs(dx) > self.swipe_dx:
            self._last_fire, self._still_since = now, None
            self._hist.clear()
            return "swipe_right" if dx > 0 else "swipe_left"
        if abs(dx) < self.still_dx:
            if self._still_since is None:  # note: not `or` — the first ts can be 0.0
                self._still_since = now
            if now - self._still_since > self.hold_s:
                self._still_since = None
                return "pause"
        else:
            self._still_since = None
        return None

    def _pair_dist(self, hands: list) -> float:
        a = hands[0]["landmarks"].get("wrist")
        b = hands[1]["landmarks"].get("wrist")
        return hypot(a[0] - b[0], a[1] - b[1]) if a and b else 0.0
