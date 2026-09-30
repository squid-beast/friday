# Friday OS — Run Book

Your local-first, voice-first personal AI. The Mac is the brain; snapshots are
the safety net; the code backs up to a **private** GitHub repo
(`squid-beast/friday`) — secrets are never committed. This page tells you how to
run it and what's live. The v2 roadmap (other models, emotional Fish-Audio voice,
public `friday.paypilotlabs.com`, only-my-voice) lives in **`docs/UPGRADE-PLAN.md`**.
Deep docs live in `docs/` (older references in `docs/archive/`).

Repo: `/Users/lohithkumar/friday` · Public URL:
`https://lohiths-macbook-pro.tail8d7575.ts.net`

---

> **2026-09-28 review:** `docs/SYSTEM-REVIEW.md` lists what runs, what is broken, and what to keep, pause or remove.

## 1 · It's already running
Four launchd agents (`com.friday.*`: dashboard, killswitch, metrics, logrotate) keep
Friday alive across reboots. Right now you can:
- **Open the app** → the URL above (first visit on a device: add
  `?key=<APP_ACCESS_KEY from .env>` once → year-long cookie). Local:
  `http://127.0.0.1:8787`.
- **Talk** → the active wake phrase is shown in the dashboard header. Until the
  custom model is trained, the fallback remains **"Hey Jarvis"**. After training,
  it becomes **"Hey Friday"**.
- **Stop** → during an active session, say **"Stand Down"**.

If something looks off, the first move is always `make doctor`.

## 2 · What it does on wake
- **No app storm** — waking does NOT open apps (`WAKE_APPS_ENABLED=false`). Say
  **"open my apps"** when you want Spotify + your Chrome tabs (`WAKE_URLS`).
- **Warm check-in** — Friday greets you, then asks one caring question (health,
  what you're learning, where you are, what you did) and remembers the answer.
  Replies **stream** now — it starts speaking on the first word, not the last.

## 3 · Strict owner-only wake
If you want **only your voice** to wake Friday, this is what you need to do:
1. Record 50 positive clips for **"Hey Friday"**.
2. Record 25 negative clips in your normal voice without saying the phrase.
3. Train the wake model and the owner-voice verifier.
4. Set `WAKE_MODEL_PATH`, `WAKE_VERIFIER_PATH`, and `WAKE_REQUIRE_VERIFIER=true`.

Important truth:
- This is **wake-only** right now.
- Once Friday is awake, the conversation path still accepts speech normally.
- Fully verifying every spoken turn is a separate future feature.

## 3b · What you can say (every command is linked, 2026-09-29)
| Say | Friday does | Tool |
|---|---|---|
| "what's the weather?" | Live Open-Meteo conditions for `WEATHER_CITY` | weather |
| "remind me to …" | Saves a reminder (HUD Notes card) | reminder |
| "what's on my calendar today?" | Reads Calendar.app | calendar_today |
| "book lunch with Sam tomorrow at noon" | Asks "Shall I proceed?", then books | calendar_event (confirm) |
| "how's my job search going?" | Latest batch, decisions, questions waiting, tracker | jobs_status |
| "open my notes" / "open the note called X" | Opens Obsidian | open_obsidian |
| "play some music" / "skip" / "pause" | Controls Spotify | spotify_play |
| "open my apps" | Spotify + Chrome tabs | open_apps |
| "how many times did you wake today?" | Friday's own metrics | metrics_report |
| "what did you do today?" | Reads the audit log | (built in) |
| any question about your notes / "take a note: …" | Answers from / writes to leos-brain | vault route |
| "remember that …" | Stores the fact | memory |
| "stand down" | Ends the session | kill path |

Dark by design (say it and Friday tells you so, the camera never switches on):
camera ("what am I holding?"), screen recall. Browser tasks use `~/friday-chrome`
— sign in there once for the sites you want Friday to operate.
n8n: Friday calls ONLY Friday-owned workflows (none registered today); business
workflows are never touched. A new one needs a POST webhook + header auth
`X-Friday-Secret`; `make doctor` fails if a registered path isn't served.

## 4 · Commands
| Command | What it does |
|---|---|
| `make doctor` | Checks Anthropic, Deepgram, Cartesia, n8n, Chroma; lists what is dark by design |
| `make dashboard` | App server on `http://127.0.0.1:8787` (foreground) |
| `make voice` | Voice loop on the Mac's mic/speakers, barge-in, no Docker |
| `make ui` | Rebuild the SvelteKit UI into `ui/build` (after any `ui/src` change) |
| `make gesture` | Build the native hand-tracking spike (G0); then `uv run python -m gesture.spike` |
| `make install-launchd` | Install/refresh the 4 always-on launchd agents (idempotent) |
| `make phone-voice` / `make phone-voice-off` | Server side of phone voice (LiveKit + voiceworker) on / off. No phone client exists today — kept for a future one. Start Docker Desktop first |
| `make snapshot` | rsync the repo → `~/friday-snapshots/` — the "undo" |
| `make lint` / `test-unit` | Lint (ruff) / L1 tests — before finishing any change |
| `make test-integration` / `test-scenario` | L2 / the demo, end-to-end |
| `make eval` | Router + tool-selection accuracy vs the real model (≥90% gates) |

Restart one agent: `launchctl kickstart -k gui/$(id -u)/com.friday.<name>`
(dashboard · killswitch · metrics · logrotate; voiceworker · livekit only between
`make phone-voice` and `make phone-voice-off`). Screen recall (screenpipe) and camera sight (moondream) are
dark by design — their agents were removed 2026-09-29.

Runtime state lives outside the repo under `FRIDAY_STATE_DIR`.
Default: `~/Library/Application Support/Friday`.

## 5 · The dashboard
**One dashboard** at `/`: no tabs, no buttons, voice-first. It shows the live
state, the recent conversation (your last spoken turns, from the brain's own
store), Now, Metrics, Today, Jobs, weather in °F, system load, snaps, notes, and
automations (one row per n8n workflow, local time; errors shown, not hidden).
Studio and gesture panels are parked (code kept, not mounted).

The header tells the truth about:
- which wake phrase is actually active
- whether strict voice lock is armed
- whether Friday is listening, resting, or off
- that the current voice lock is **wake-only**

### Jobs command center (`/jobs`, added 2026-09-28)
The one screen with buttons. Shows the latest job batch from `~/Downloads/Jobs`
live (refreshes every 5s while open): approve / skip / undo each role, answer its
"needs you" questions, and open its resume, letter or folder on the Mac. Clicks
are saved to `~/Downloads/Jobs/_engine/state/decisions_<batch>.json`, which the
nightly Claude run reads. The cockpit shows a read-only Jobs card linking here.
API: `GET /api/v1/jobs/overview`; `POST /api/v1/jobs/{batch,decide,answer,open}`.

## 6 · What still needs you
`make doctor` (2026-09-30): **all clear**. n8n is reached over the tailnet at
`http://…:5678` (WireGuard-encrypted). Phone voice: server side on demand
(`make phone-voice`), no phone client today; the Mac wake path never needs Docker.

| ✅ Working | ⏳ Needs you |
|---|---|
| Brain · PIN · voice keys · weather (°F) | **Phone/browser:** open the app once with `?key=` again (the old `jarvis_key` cookie is no longer accepted) |
| Calendar · jobs status · Obsidian · Spotify by voice | **Browser tasks:** sign in once in the `~/friday-chrome` profile |
| Streaming replies · honest camera ("eyes offline") | **Train** the custom `Hey Friday` wake model |
| HUD · access gate · log rotation | **Train** the owner-voice verifier for strict wake-only access |
| Caring check-in · recent-conversation card | **iPhone** Add to Home Screen (`docs/MOBILE.md`) |
| Spotify control | Gesture control is **parked** (panel unmounted; code in `gesture/`, manual `python -m gesture.agent` only) |

### Working right now (v1, current truth)
- **Brain LLM:** Anthropic only (Sonnet + Haiku) via `adapters/llm.py`.
- **Voice out:** Cartesia TTS (`adapters/tts.py`); ElevenLabs env fallback only.
- **Wake:** "Hey Jarvis" fallback — custom "Hey Friday" model not trained yet.
- **Voice lock:** wake-only; per-utterance owner verification not armed.
- **Access:** Tailscale URL + `APP_ACCESS_KEY` cookie (not public internet yet).
- **Actions:** 9 local tools in `config/tools.yaml` (table in §3b); no n8n tools
  registered (calls/business demo tools removed 2026-09-29; calls doc archived).
- **Emotion:** mood engine exists (`docs/EMOTIONS.md`) — colors word choice, not
  yet the voice.

### Backlog — unbuilt n8n ideas (removed from tools.yaml 2026-09-29)
content_pipeline · review_request · lead_followup · booking_reminders ·
morning_report · lead_finder · draft_replies · send_outreach — each = one n8n
workflow + one `config/tools.yaml` entry when wanted.

### Planned — v2 (see `docs/UPGRADE-PLAN.md`; NOT yet armed)
- Call other models (OpenAI / Gemini / OpenRouter / local) — Phase 8.
- Fish Audio cloud voice + audible emotion, cloned target voice — Phase 9.
- More real actions + proactive buddy behaviors (n8n-first) — Phase 10.
- Public `friday.paypilotlabs.com` via Cloudflare Tunnel + Access — Phase 11.
- Only-my-voice: trained wake + per-utterance owner verifier — Phase 12.

## 7 · How changes show up
- **UI change** → rebuild the UI, then refresh the browser.
- **Backend change** → restart the dashboard agent.
- **Voice change** → restart the killswitch (it spawns a fresh voice session each wake).
- **No, VS Code does not need to stay open.** Launchd keeps Friday running after login.

## 8 · Keep these docs
- `README.md`
- `docs/UPGRADE-PLAN.md`  ← v2 roadmap (models · voice · deploy · voice-lock)
- `docs/SETUP.md`
- `docs/MOBILE.md`
- `docs/DEMO-SCRIPT.md` ← v1 definition of done (redefined 2026-09-29)

## 9 · If something breaks
1. `make doctor` — names the dark service.
2. Its log: `~/Library/Application Support/Friday/logs/<agent>.log`
   unless `FRIDAY_STATE_DIR` points somewhere else.
3. Restart it: `launchctl kickstart -k gui/$(id -u)/com.friday.<agent>`.
4. Roll back: copy from the newest `~/friday-snapshots/` folder.
