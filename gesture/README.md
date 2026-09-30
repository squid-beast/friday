# Gesture control — G0 → G2

Hand control of your Mac, built in safe steps. **G0** proved Apple Vision sees
your hand; **G1** projects it onto the `/gesture` screen; **G2** adds the live
camera feed, two-hand tracking, the full gesture vocabulary, and real cursor
control (opt-in).

## What's here
- `handpose.swift` — native Apple **Vision** + **AVFoundation** tracker: up to
  **two hands** per frame → 21 joints each as JSON on stdout; optionally writes
  the raw camera frame as a JPEG (the live feed).
- `classifier.py` — pure, tested: landmarks → a named gesture, the whole set:
  **fist, point, sarina's middle finger, pinch, peace, three, four, open_palm,
  thumbs_up**.
- `agent.py` — runs the tracker, publishes per-hand state + the frame, and (only
  while control is armed) drives the cursor.
- `actuator.py` — cursor move + click via Quartz CGEvent (the only Mac-touching bit).
- `spike.py` — the G0 terminal demo (prints the live gesture).

## Run it
From a **terminal** (so macOS can prompt for Camera / Accessibility):

```bash
make gesture                       # build the native tracker (once)
uv run python -m gesture.agent     # G1/G2: publish hands + feed; Ctrl-C to stop
```
Then open **`/gesture`** in the app. You'll see the live camera (mirrored) with
both hands' skeletons and each hand's gesture, and an **ON AIR** indicator.

G0 terminal-only demo (no app): `uv run python -m gesture.spike`.

## Cursor control (G2) — opt-in
On `/gesture`, click **Enable cursor control** (off by default):
- **Point** (index finger) → moves the cursor (whichever hand is pointing).
- **Pinch** (thumb + index) → clicks.
- **Swipe** an open hand left/right → switch desktop/Space (⌃← / ⌃→).  *(G3)*
- **Two hands** apart / together → zoom in / out (⌘+ / ⌘−).  *(G3)*
- **Hold an open palm still** → instantly **pauses** control.

The first click triggers a macOS **Accessibility** prompt — allow it (System
Settings → Privacy & Security → Accessibility). Moving the cursor needs no
permission; clicking does.

## Safety & privacy
- Cursor control is **off until you enable it**, and an open palm pauses it — your
  mouse is never hijacked unexpectedly.
- The camera feed is served behind your access key; the **"camera off"** cut and
  stopping the agent both end it instantly. Only this screen and the agent see it.
- Opt-in and manual — nothing runs at login (no launchd agent).

## Tuning
If a gesture misreads or the cursor/skeleton is offset, the knobs are
`_EXTEND_RATIO` / `_PINCH_RATIO` / `_THUMB_OUT` in `classifier.py` and the
`mirror` flag in `actuator.to_screen`. Hands and lighting vary — expect a little
calibration.

## Next (not built)
- **G4** — polish + a launchd agent so it's always available, with kill wiring
  and calibration in `.env`.
See `docs/archive/GESTURE-CONTROL.md`.
