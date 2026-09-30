# Friday on your phone (Tailscale)

Control and talk to Friday from your iPhone over your **already-connected**
Tailscale tailnet. Nothing is exposed to the public internet beyond your gated
URL; the Mac stays the brain.

## One-time setup (5 min)
1. **Tailscale ON** on the iPhone (you already have this).
2. In Safari open your Friday URL **with the key once**:
   `https://lohiths-macbook-pro.tail8d7575.ts.net/?key=<APP_ACCESS_KEY from .env>`
   → the key becomes a year-long cookie, so afterwards the plain URL just works.
3. **Share → Add to Home Screen.** You now have a Friday app icon.

## What you can do from the phone (current truth, 2026-09-29)
- **Glance** — the dashboard is passive and voice-first (no buttons): Friday's
  state, the recent conversation (your last spoken turns), Now, Metrics, Today,
  Jobs, HUD (time, weather °F, system vitals, notes & reminders, automations).
- **Jobs** — `/jobs` is the one screen with buttons: approve / skip / answer /
  open files for the latest job batch.
- **Text API** — `POST /api/v1/conversation` with `Authorization: Bearer <key>`
  reaches the same brain, tools and gates (e.g. from a Shortcut). No chat box.

## Talking to it
Spoken conversation uses the **Mac's** mic — wake it with the wake phrase and it
answers on the Mac. Phone-microphone voice has **no client today**: the browser
LiveKit client (ui/src/lib/voice.js) was removed on 2026-09-29. `make phone-voice`
(Docker Desktop running) starts only the server side — LiveKit + the voiceworker —
for a future client; `make phone-voice-off` removes both and stops the container.

## Killing it from the phone
There is no stand-down button (passive dashboard). From the phone, send
`POST /api/v1/daemon/stand-down` with the Bearer key, or say "stand down" at the
Mac; the Mac's menu-bar 😴 always works offline.

## If it won't load
- Tailscale off on either device → turn it on.
- Locked out (key rotated)? Re-open with `?key=<new key>` once.
- Everything else: on the Mac, `make doctor` names what's dark.
