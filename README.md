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
Six launchd agents (`com.friday.*`) keep Friday alive across reboots. Right now you can:
- **Open the app** → the URL above (first visit on a device: add
  `?key=<APP_ACCESS_KEY from .env>` once → year-long cookie). Local:
  `http://127.0.0.1:8787`.
- **Talk** → the active wake phrase is shown in the dashboard header. Until the
  custom model is trained, the fallback remains **"Hey Jarvis"**. After training,
  it becomes **"Hey Friday"**.
- **Stop** → during an active session, say **"Stand Down"**.

If something looks off, the first move is always `make doctor`.

## 2 · What it does on wake
- **Opens your apps + dashboard** — *every* wake opens Spotify + Chrome with
  Instagram, GitHub, Gmail, and the Friday dashboard. Edit the list with `WAKE_URLS`
  in `.env`; say **"open my apps"** to trigger it anytime. (No VS Code needed —
  launchd runs it all on login.)
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

## 4 · Commands
| Command | What it does |
|---|---|
| `make doctor` | Checks Anthropic, Deepgram, Cartesia, n8n, Chroma; lists what is dark by design |
| `make dashboard` | App server on `http://127.0.0.1:8787` (foreground) |
| `make voice` | Voice loop on the Mac's mic/speakers, barge-in, no Docker |
| `make ui` | Rebuild the SvelteKit UI into `ui/build` (after any `ui/src` change) |
| `make gesture` | Build the native hand-tracking spike (G0); then `uv run python -m gesture.spike` |
| `make install-launchd` | Install/refresh all launchd agents (idempotent) |
| `make snapshot` | rsync the repo → `~/friday-snapshots/` — the "undo" |
| `make lint` / `test-unit` | Lint (ruff) / L1 tests — before finishing any change |
| `make test-integration` / `test-scenario` | L2 / the demo, end-to-end |
| `make eval` | Router accuracy vs the real model (≥90% gate) |

Restart one agent: `launchctl kickstart -k gui/$(id -u)/com.friday.<name>`
(dashboard · killswitch · voiceworker · livekit · metrics · logrotate).
Screen recall (screenpipe) and camera sight (moondream) are dark by design —
their agents were removed 2026-09-29.

Runtime state lives outside the repo under `FRIDAY_STATE_DIR`.
Default: `~/Library/Application Support/Friday`.

## 5 · The dashboard
**One dashboard** at `/`: no tabs, no buttons, voice-first. It shows the live
state, recent context, Studio queue, Metrics, Today, weather in °F, system load,
snaps, notes, automations, and gesture tracking on one screen.

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
`make doctor` (2026-09-29): all clear **except n8n** — the VPS now answers plain
HTTP on :5678 (its tailnet TLS front is gone), so the configured `https://` base
URL fails. Your call: restore `tailscale serve` on the VPS, or switch
`N8N_BASE_URL` to `http://` (still WireGuard-encrypted inside the tailnet).
Phone voice needs Docker Desktop running (LiveKit); the Mac wake path does not.

| ✅ Working | ⏳ Needs you |
|---|---|
| Brain · PIN · voice keys · weather (°F) | **Phone/browser:** open the app once with `?key=` again (the old `jarvis_key` cookie is no longer accepted) |
| Calendar · HUD snaps tile (camera dark by design) | **Activate** your 5 n8n workflows — first switch their header check to `X-Friday-Secret` |
| Apps open on every wake · streaming replies | **Train** the custom `Hey Friday` wake model |
| HUD · access gate · log rotation | **Train** the owner-voice verifier for strict wake-only access |
| Caring check-in · calls scaffold (PIN-gated) | **Calls** provider (`docs/CALLS.md`) · **iPhone** Add to Home Screen (`docs/MOBILE.md`) |
| Spotify control · gesture G0–G3 (`gesture/README.md`) | **G3 live**: `make gesture` → `python -m gesture.agent` → allow Accessibility → point→cursor, pinch→click, swipe→space, spread→zoom |

### Working right now (v1, current truth)
- **Brain LLM:** Anthropic only (Sonnet + Haiku) via `adapters/llm.py`.
- **Voice out:** Cartesia TTS (`adapters/tts.py`); ElevenLabs env fallback only.
- **Wake:** "Hey Jarvis" fallback — custom "Hey Friday" model not trained yet.
- **Voice lock:** wake-only; per-utterance owner verification not armed.
- **Access:** Tailscale URL + `APP_ACCESS_KEY` cookie (not public internet yet).
- **Actions:** n8n tools defined in `config/tools.yaml` — need activating in n8n.
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
- **Voice change** → restart the voice worker.
- **No, VS Code does not need to stay open.** Launchd keeps Friday running after login.

## 8 · Keep these docs
- `README.md`
- `docs/UPGRADE-PLAN.md`  ← v2 roadmap (models · voice · deploy · voice-lock)
- `docs/SETUP.md`
- `docs/MOBILE.md`
- `docs/CALLS.md`

## 9 · If something breaks
1. `make doctor` — names the dark service.
2. Its log: `~/Library/Application Support/Friday/logs/<agent>.log`
   unless `FRIDAY_STATE_DIR` points somewhere else.
3. Restart it: `launchctl kickstart -k gui/$(id -u)/com.friday.<agent>`.
4. Roll back: copy from the newest `~/friday-snapshots/` folder.
