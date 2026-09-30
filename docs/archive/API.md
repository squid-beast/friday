# JARVIS API — every way to command the system

One server, three addresses (same routes, same auth everywhere):

| Address | Reach | Notes |
|---|---|---|
| `https://lohiths-macbook-pro.tail8d7575.ts.net` | **public internet** (funnel) | verified live |
| `http://lohiths-macbook-pro.tail8d7575.ts.net` | tailnet only | no-TLS fallback |
| `http://127.0.0.1:8787` | this Mac | launchd-owned |

## Auth — every request needs the key (APP_ACCESS_KEY in .env)

- **Browser, once per device**: visit any page with `?key=<KEY>` → year cookie.
- **API clients**: header `Authorization: Bearer <KEY>`.
- Missing/wrong key → `401`. Rotate: new `openssl rand -hex 16`, restart.

## The API (v1 — the professional surface, 2026-08-19)

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/conversation` | Talk to the brain: `{"text": "..."}` → `{"reply", "pending"}`. Routing, vault, memory, tool gates, audit — identical to speaking. Confirm-gated tools answer with the question; send `{"text": "yes"}` to proceed. |
| GET | `/api/v1/system/status` | Daemon state (active/dormant/off), armed systems, queue depth, next event, activity |
| GET | `/api/v1/metrics` | 14-day metric series per platform (sparkline data) |
| GET | `/api/v1/agenda` | Today's calendar + Jarvis activity log |
| GET | `/api/v1/studio/queue` | Content review queue `{items, armed}` |
| POST | `/api/v1/studio/queue/refresh` | Pull trending items from n8n |
| POST | `/api/v1/studio/publish` | `{"id", "caption"}` → n8n posts to Instagram; audited |
| POST | `/api/v1/studio/skip` | `{"id"}` → drop from queue forever |
| GET | `/api/v1/voice/session` | LiveKit JWT scoped to room "phone" |
| POST | `/api/v1/daemon/wake` | Wake the Mac mic session (chime, ACTIVE) — the cockpit pill |
| POST | `/api/v1/daemon/stand-down` | End the Mac session; also what "stand down" does |
| GET | `/api/v1/hud` | One glance payload: system vitals, weather (°F), notes+reminders, automations, agent state |
| POST | `/api/v1/automations/detail` | `{"id"}` → one n8n run's outcome + data preview (HUD tap-to-expand) |

Unversioned paths (`/api/ask`, `/api/status`, ...) remain as **deprecated
aliases** so older installed phones keep working; new clients use v1 only.

```bash
curl -s https://lohiths-macbook-pro.tail8d7575.ts.net/api/v1/conversation \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"text": "run the vendor report"}'
```

## The UI (SvelteKit, built locally, served same-origin)

`/` cockpit — conversation (text + voice) with the mission deck ·
`/chat` `/studio` `/today` `/voice` focused views. Client-side navigation
keeps the transcript alive between screens. Rebuild after UI changes:
`make ui` (npm build → `ui/build`, zero external resources at runtime).

## Voice commands (mic or Voice screens — same brain as the API)

- **Wake**: "Hey Jarvis" (bundled) → your trained phrase (Stage 6).
- **Kill — local, works offline**: "stand down" · "camera off" · "screen off";
  "resume"/"dismissed" said alone. Menu bar 😴/🎙 and ⌥⌘J do the same.
- **Vault/memory**: "what did I quote X?" · "remember ..." · "take a note ...".
- **Calendar**: "what's on my calendar?" · "book a meeting ..." (confirm).
- **Weather**: "what's the weather?" · "will it rain today?" (WEATHER_CITY in .env).
- **Ops**: "find me jobs" (confirm) · "draft a reply to that review" ·
  "run the vendor report" · "what did you do today?".
- **Eyes**: "what am I holding?" (camera) · "that page I saw yesterday" (recall).
- **Web hands**: "go to the site and book the slot" (confirm, 15-step cap).
- **Risk ladder**: safe = instant · confirm = spoken yes · pin = spoken PIN.

## What arms the still-dark pieces

| Dark today | Arms when |
|---|---|
| Studio + metrics cards | the n8n content/metrics workflows exist (docs/CONTENT-STUDIO.md, docs/DASHBOARD.md) |
| n8n voice tools answering | the 5 workflows are ACTIVATED in the n8n editor |
| Camera sight | moondream-2 weights finish (station switched; watcher armed) |
| PIN tools | 4-digit `JARVIS_PIN` in .env |
