# Phase G — Gesture Control ("move my Mac with my hands")

Your decisions (2026-08-20): **Full Mac control** · **Apple Vision** engine ·
gestures = **pinch-zoom, swipe L/R (tab/desktop), pinch (click), point (cursor),
open palm (stop/wake)**. This spec is the plan; nothing is built yet.

## 1 · What it is

A native macOS agent watches the camera, tracks your hand with Apple's Vision
framework, turns gestures into real Mac actions (move the cursor, click, switch
tabs/desktops, zoom), and streams a live view of what it sees into the Jarvis
UI so you can watch yourself being tracked.

## 2 · Why native (not the browser)

A browser is sandboxed — it can render a camera feed but **cannot move windows
or control other apps**. Full Mac control needs a native process with the
**Accessibility** permission. So Vision + AVFoundation live in a small local
agent; the UI just shows the feed and status.

## 3 · Architecture (fits the existing pattern)

```
 camera ─▶ com.jarvis.gesture (native agent)
             ├─ AVFoundation: 30fps frames
             ├─ Vision: VNDetectHumanHandPoseRequest → 21 hand landmarks
             ├─ gesture engine: landmarks → {pinch, swipe, point, palm, zoom}
             ├─ actuator: CGEvent / CGWarpMouseCursorPosition → the Mac
             └─ MJPEG on 127.0.0.1 → the UI's /gesture screen shows the feed + overlay
 kill: "camera off" control-file + open-palm gesture + menu-bar toggle
```

- New launchd agent `com.jarvis.gesture` — like every other organ, runs on
  login, **no VS Code or terminal needed** (that's the whole launchd design;
  building needs my tools, running needs nothing).
- Reuses the existing camera-off control file so "camera off" kills it instantly.
- The UI gains a `/gesture` screen: the live camera rectangle + tracked-hand
  overlay + an ON-AIR indicator. Start/stop from there or by voice.

## 4 · Gesture → action map (first cut)

| Gesture (Vision landmarks) | Action (CGEvent) |
|---|---|
| Index finger point | Move cursor (fingertip → screen coords) |
| Thumb+index pinch (quick) | Click |
| Thumb+index pinch, hold + move apart/together | Zoom in / out (⌘+ / ⌘−) |
| Open hand swipe L / R | Switch desktop/Space (⌃→ / ⌃←) or browser tab (⌘⇧] / ⌘⇧[) |
| Open palm held | Stop gesture mode (and, optionally, wake Jarvis) |

Tuning knobs (thresholds, dwell times, smoothing) live in `.env`/config — the
"physical world needs calibration" reality; hands and lighting vary.

## 5 · Safety (this is the highest-blast-radius capability in the system)

- **Opt-in mode only** — off by default; you start it explicitly (voice, UI, or
  hotkey). It is NOT armed at login.
- **Continuous camera while active** — this deliberately breaks the "camera is
  single-frame" rule, so: a visible ON-AIR indicator whenever it runs, the macOS
  green camera light (hardware-truthful), and three kills — open-palm gesture,
  "camera off" / "stand down", and the menu bar.
- **Accessibility permission** — required to move windows; macOS prompts once.
- **No network** — everything is local; frames never leave the Mac.

## 6 · Build sequence (each piece testable before the next)

1. **G0 · Vision spike** — a standalone script: camera → hand landmarks printed.
   Proves Vision works on your Mac. (You run it; I can't see your camera here.)
2. **G1 · Live projection** — `/gesture` UI screen shows the feed + landmark
   overlay + ON-AIR. No Mac control yet. Safe, satisfying, verifiable by eye.
3. **G2 · Cursor + click** — point moves the cursor, pinch clicks. Accessibility
   granted here. Small, high-delight.
4. **G3 · Swipe + zoom** — desktop/tab switching and pinch-zoom.
5. **G4 · Safety + polish** — open-palm stop, calibration knobs, kill wiring,
   launchd agent, tests for the pure logic (gesture classifier is unit-testable
   even though the camera path is live-only).

## 7 · What I can verify vs. what only you can

- **I can build & unit-test**: the gesture classifier (landmarks → gesture), the
  action map, the UI screen, the agent scaffolding, the safety/kill wiring.
- **Only you can verify live** (no camera/Accessibility in my sandbox): that
  Vision sees your hand, that gestures actually move your windows, that the
  feed projects. So we build in small steps and you test each one.

## 8 · Honest cost

This is the most ambitious capability in Jarvis — a multi-step native build,
and the riskiest (it can control your whole Mac). The projection phase (G1) is
low-risk and quick; the control phases (G2–G4) are where the power and the care
concentrate. Recommend building G0→G1 first so you see it working before we arm
Mac control.
