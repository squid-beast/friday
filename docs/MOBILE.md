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

## What you can do from the phone
- **Chat** — type to Friday in the cockpit; same brain, memory, and tools as voice.
- **Wake / Stand down** — the masthead pill (● Active / ○ Dormant) starts or ends
  the Mac's listening session from your pocket.
- **HUD** — glance screen: time, weather (°F), system vitals, notes & reminders,
  today's automations (tap a run to see its data).
- **Studio** — review trending content cards, two-tap publish.
- **Notes** — recent notes on the dashboard; tapping one opens it in Obsidian
  **on the Mac** (the server runs there). Browsing and graphing live in Obsidian
  itself, not in Friday. Asking Friday *about* your notes works from anywhere.

## Talking to it
Spoken conversation uses the **Mac's** mic — the
phone is your remote and screen. Wake it with the pill or the wake phrase, talk,
and it answers on the Mac. (Phone-microphone voice is kept in the code but off in
the UI; ask to re-enable it if you want it.)

## Killing it from the phone
Tap the pill to **Stand down** — audited, instant. The Mac's menu-bar 😴 and the
spoken "stand down" are the other two kill paths.

## If it won't load
- Tailscale off on either device → turn it on.
- Locked out (key rotated)? Re-open with `?key=<new key>` once.
- Everything else: on the Mac, `make doctor` names what's dark.
