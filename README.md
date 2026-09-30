# Friday — a local-first, voice-first personal AI

Friday is Lohith's personal assistant: you wake her by voice, talk naturally, and she
answers from your own notes and memory, runs your Mac (calendar, Spotify, apps, web
searches, Obsidian), keeps your day plan, checks in on you like family, and acts only
through spoken gates (a "yes" for anything that changes the world, a PIN for the riskiest).
**The Mac is the brain.** Only model calls (LLM / speech) leave it.

| | |
|---|---|
| Repo | `~/friday` · private GitHub `squid-beast/friday` (secrets never committed) |
| Dashboard | `http://127.0.0.1:8787` (key-gated) · tailnet `https://lohiths-macbook-pro.<tailnet>.ts.net` |
| Health | `make doctor` |
| Tests | 719 automated (unit · integration · scenario) + real-model evals |
| Status (2026-09-30) | Phases 1–6 built and committed; see **[TODO](#15--todo--what-still-needs-doing)** for what only you can do |

---

## Contents
1. [How Friday works](#1--how-friday-works)
2. [Daily use in 60 seconds](#2--daily-use-in-60-seconds)
3. [Everything you can say](#3--everything-you-can-say)
4. [Features in detail](#4--features-in-detail)
5. [Setup from zero](#5--setup-from-zero)
6. [Configuration (.env)](#6--configuration-env)
7. [Commands](#7--commands)
8. [What runs in the background (launchd)](#8--what-runs-in-the-background-launchd)
9. [Safety model](#9--safety-model)
10. [Testing](#10--testing)
11. [Deployment (GitHub + friday.paypilotlabs.com)](#11--deployment)
12. [Project layout](#12--project-layout)
13. [Troubleshooting](#13--troubleshooting)
14. [Docs index](#14--docs-index)
15. [TODO — what still needs doing](#15--todo--what-still-needs-doing)
16. [History (phase commits)](#16--history-phase-commits)

---

## 1 · How Friday works

```
 "Hey Jarvis"* ──▶ killswitch daemon (menu bar 😴/🎙, offline wake word, offline kill)
                     │ spawns one voice session per wake
                     ▼
 mic ──▶ VAD ──▶ STT (Deepgram) ──▶ FridayAgent.llm_node
                     │  1. local intents FIRST (stand down / camera off / mute) — offline
                     │  2. owner-voice lock (every turn, when armed)
                     │  3. mood update (audit events)
                     ▼
            LangGraph brain: router ─┬─ chat   (persona + mood line)
                                     ├─ vault  (answers from leos-brain, "take a note")
                                     ├─ ops    (tools.yaml → confirm/PIN gates → adapters)
                                     ├─ vision (camera / web browser tasks)
                                     └─ recall (screen memory — switched off)
                     │  memory_writer → Chroma facts (fire-and-forget)
                     ▼
 speakers ◀── TTS (Cartesia │ OpenAI tone │ Fish Audio cloned voice) ◀── emotion safety gate

 Dashboard (SvelteKit, :8787) ─ same brain for text (phone / API), read-only views
 n8n (Hostinger VPS, over the tailnet) ─ ONLY Friday-owned workflows
```
\* The active wake phrase is the bundled **"Hey Jarvis"** model until you train
**"Hey Friday"** (TODO #3) — the dashboard header always shows which one is armed.

Layers (enforced by tests): `adapters/` is the only place vendor SDKs live · `brain/` is
pure orchestration · capabilities are declared only in `config/tools.yaml` (no graph edits)
· `client/` + `audit/` (the kill path) import zero network stacks.

---

## 2 · Daily use in 60 seconds

1. Say the wake phrase shown in the dashboard header (today: "Hey Jarvis"). You hear a
   chime; Friday greets you (a spoken morning brief on the first wake of the day), then
   asks one caring question — or follows up on the nudge she sent you earlier.
2. Talk. Replies are ≤ 3 sentences and stream as they're generated.
3. Anything that changes the world asks **"Shall I proceed, sir?"** — say "yes". With the
   voice lock armed, a bare "yes" is too little audio to verify, so say "yes, go ahead"
   (Friday asks again, politely, if it was too short).
4. Say **"stand down"** to end the session. The menu-bar 😴 kills it offline too.
5. Glance at the dashboard for your day; `/jobs` is the one screen with buttons.

---

## 3 · Everything you can say

### Tools (config/tools.yaml — each is one adapter, risk-gated)
| Say | Friday does | Tool | Risk |
|---|---|---|---|
| "what's the weather?" / "do I need an umbrella?" | live Open-Meteo conditions (°F) for `WEATHER_CITY`, or a city you name | `weather` | safe |
| "remind me to call the vendor" | saves a reminder (HUD Notes card) | `reminder` | safe |
| "what's on my calendar today?" | reads Calendar.app (Google included if added there) | `calendar_today` | safe |
| "book lunch with Sam tomorrow at noon" | creates the event after your spoken yes; refuses to guess a time | `calendar_event` | **confirm** |
| "how's my job search going?" / "show me my jobs" | latest batch: roles, approved/skipped/undecided, questions waiting on you, tracker totals | `jobs_status` | safe |
| "add call the bank to today's plan" / "what's on my plan?" | checkbox in your Obsidian daily note `daily/YYYY/YYYY-MM-DD.md` under "## Friday plan" | `today_plan` | safe |
| "open my notes" / "open the note called weekly review" | opens Obsidian (the vault or one note) | `open_obsidian` | safe |
| "open Slack" · "search YouTube for lo-fi" · "google flights to Austin" · "find coffee on maps" | opens an INSTALLED app, or a search on Google/YouTube/GitHub/Amazon/Maps/Wikipedia | `open_and_search` | safe |
| "play some music" · "skip" · "pause" · "what's playing?" | controls Spotify | `spotify_play` | safe |
| "open my apps" | Spotify + your Chrome tabs (`WAKE_URLS`) | `open_apps` | safe |
| "send me a summary of my day" | calendar + plan + reminders + jobs + activity → your Telegram (Friday-owned n8n) | `send_summary` | **confirm** |
| "how many times did you wake up today?" | Friday's own metrics (wakes, tool runs/failures, calendar load) | `metrics_report` | safe |

### Built into the brain (no tool needed)
| Say | Friday does |
|---|---|
| anything conversational | answers in persona (dry British wit, ≤ 3 sentences, mood-coloured) |
| "remember that my locker code is 4242" | stores the fact in long-term memory (Chroma) |
| a question about your notes ("what did I quote the Receivly client?") | answers from leos-brain, grounded in the notes |
| "take a note: …" / "add to my inbox: …" | appends to `_inbox/friday-notes.md` in your vault |
| "what did you do today?" | reads the audit log back |
| "stand down" · "camera off" · "stop watching my screen" · "mute" | offline, instant, from ANY voice |
| "resume" | re-enables capture (owner-only when the voice lock is armed) |
| "what am I holding?" / "what was that page I saw?" | honestly says the camera / screen memory is switched off (the camera never turns on without a vision model) |
| "go to the site and book the slot" | browser task in the dedicated `~/friday-chrome` profile, after your yes |

---

## 4 · Features in detail

**Voice loop & wake.** The killswitch daemon listens offline (openWakeWord) while
dormant; a wake spawns one LiveKit console session (Deepgram STT, VAD, barge-in, streaming
replies). A silence watchdog ends idle sessions. Owner-only wake is supported via an
openWakeWord verifier (`WAKE_VERIFIER_PATH`, `WAKE_REQUIRE_VERIFIER`, fail-closed).

**Kill paths (always offline).** "Stand down", "camera off", "stop watching my screen",
the menu-bar 😴, and (optional) a hotkey. Kill phrases are matched locally before any cloud
call; the daemon's stand-down chime fires the instant the kill lands.

**Brain & routing.** A fast model routes each turn to chat / vault / ops / vision / recall
(44-case router eval, ≥ 90% gate). Ops selects a tool from `config/tools.yaml` (31-case
tool-selection eval, every tool covered, business asks select nothing), runs it through
its risk gate, audits it, and speaks a one-line summary.

**Multi-provider LLM (Phase 2).** `LLM_PROVIDER` = `anthropic` (default) | `openai` |
`openrouter` | `gemini` | `compatible` (any OpenAI-compatible server: Ollama, vLLM, LM
Studio via `LLM_BASE_URL`). One seam (`adapters/llm.py`); `think(model=…)` overrides per
call; Claude model ids never leak to another provider (provider defaults apply).

**Memory.** Facts are extracted after each turn (cheap regex gate, then a fast model) into
an embedded Chroma store; answers to Friday's own questions (check-ins, nudges) are always
remembered. The Obsidian vault is read live (never copied), with an allowlist that refuses
escapes and hidden/excluded folders; Friday writes only `_inbox/friday-notes.md` and your
daily plan.

**Mood engine (Phase 3).** Five decaying dimensions (valence, arousal, warmth,
confidence, concern) moved only by real events: tool successes/failures and stand-downs
(every turn), plus — once a day at wake — remembered sleep/deadline/win facts, calendar
load, late-night hours and long absences. One disposition line colours word choice; it
never touches gates, kills or the 3-sentence cap. Design: `docs/EMOTIONS.md`.

**Emotional voice (Phase 3).** `TTS_PROVIDER` = `cartesia` (default) · `openai`
(gpt-4o-mini-tts; the mood becomes per-line tone instructions — works on your OpenAI key) ·
`fishaudio` (your cloned target voice, S1 inline tags like "(worried)"). A tested safety
gate keeps kill, cut, confirmation, PIN, refusal and apology lines — and everything while
you're stressed — flat and tag-free.

**Buddy (Phase 4).** Proactive check-ins at 09:00 / 13:00 / 19:00: one caring line from
memory + calendar + mood as a macOS notification, followed up out loud at your next wake.
Today's plan in your daily note. Open-app / web-search actions. A Telegram day summary via
a Friday-owned n8n workflow.

**Owner voice (Phase 5).** When armed, every spoken turn's own audio is scored against
your enrolled voiceprint (WeSpeaker CAM++ ONNX, no torch) before the brain runs:
strangers are politely refused, too-short audio is asked again, and a missing model or
voiceprint fails closed. Stand-down / camera-off / mute work from any voice; everything
that grants capability is yours only. PIN-risk tools still need the spoken PIN. Scope:
the lock guards the **microphone**; typed turns over HTTP (phone/API) are guarded by the
access key (+ Cloudflare Access when public), not by your voice. The dashboard shows the
real state — `wake-only` (lock off), `every turn` (armed + voiceprint present), or `every
turn — no voiceprint, refusing` (armed but not enrolled: fails closed). While armed, a
wake that wasn't verified as you (no wake verifier trained yet) gets only a neutral
"At your service, sir." — no brief, no calendar, no personal check-in until you speak.

**Jobs command center.** `/jobs` shows the nightly job batch from `~/Downloads/Jobs`:
approve / skip / undo, answer the "needs you" questions, open the resume/letter/folder.
Decisions land in `_engine/state/decisions_<batch>.json` for the next run.

**Dashboard.** One passive, voice-first screen: Friday's state and the real active wake
phrase, the recent conversation (from the brain's own checkpoint store), Now, Metrics,
Today (calendar + activity), Jobs, HUD (clock, weather, system vitals, snaps, notes &
reminders, n8n automations — one row per workflow, local time, errors shown).

**n8n.** Reached over the tailnet at `http://srv1852068.<tailnet>:5678`. Friday calls
**only Friday-owned workflows** (today: "Friday — Send me a summary"). Business/client
workflows on the same instance are never edited, activated, called or targeted.

**Phone.** The same dashboard over Tailscale (and publicly via Cloudflare after Phase 6),
key-gated; text turns via `POST /api/v1/conversation` (Bearer key). Phone-microphone voice
has no client today (`make phone-voice` starts only its server side).

**Parked (code kept, not running).** Camera sight (Moondream), screen recall
(screenpipe), gesture control, Content Studio, Mission-Board business metrics.

**Audit trail.** Every tool run, wake, stand-down, refusal and nudge is logged locally
(`db/audit.db`) — "what did you do today?" reads it.

---

## 5 · Setup from zero

```bash
# prerequisites: macOS (Apple Silicon), Homebrew, uv, Node 20+, Docker Desktop (phone voice only)
git clone https://github.com/squid-beast/friday.git ~/friday && cd ~/friday
uv sync                                  # Python deps (3.12)
cp .env.example .env && chmod 600 .env   # then fill in the keys (§6)
make ui                                  # build the dashboard
make install-launchd                     # the 5 always-on agents (§8)
make doctor                              # must end with "all clear, sir"
```
Then grant the one-time macOS prompts as they appear: **Microphone** (killswitch),
**Calendar** (first calendar question), **Files and Folders → Downloads** (jobs).
The speaker model for the voice lock is not in git: download it into `voice/models/` as
described in `adapters/voiceprint.py` (name, source and SHA-256 are in its docstring).
Full walkthrough with every key: `docs/SETUP.md`.

---

## 6 · Configuration (.env)

`.env.example` documents **every** setting (82 fields; values equal the code defaults;
secrets blank). Rules: comments on their own line; quote values with spaces. The ones
you'll touch:

| Group | Keys |
|---|---|
| LLM | `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `LLM_API_KEY` + `LLM_BASE_URL` (`compatible` only), `MODEL_SMART`, `MODEL_FAST` |
| Voice in/out | `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `TTS_VOICE_ID`, `TTS_PROVIDER`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`, `FISH_API_KEY`, `FISH_VOICE_ID`, `FISH_MODEL`, `FISH_EMOTION_ENABLED` |
| Wake & locks | `WAKE_MODEL_PATH`, `WAKE_VERIFIER_PATH`, `WAKE_REQUIRE_VERIFIER`, `VOICE_LOCK_TURNS`, `VOICEPRINT_PATH`, `VOICEPRINT_THRESHOLD`, `KILL_MODEL_PATH`, `FRIDAY_PIN` |
| Vault & jobs | `VAULT_PATH`, `VAULT_EXCLUDE`, `JOBS_DIR`, `JOBS_TRACKER_NOTE` |
| n8n | `N8N_BASE_URL`, `N8N_WEBHOOK_SECRET`, `N8N_API_KEY` (the Telegram chat id lives in the n8n workflow, not here) |
| Buddy | `PROACTIVE_CHECKINS`, `WAKE_APPS_ENABLED`, `WAKE_URLS`, `WEATHER_CITY` |
| App | `APP_ACCESS_KEY`, `DASHBOARD_PORT`, `FRIDAY_STATE_DIR` |

Runtime state (audit, memory, mood, checkpoints, logs) lives outside the repo in
`FRIDAY_STATE_DIR` (default `~/Library/Application Support/Friday`).

---

## 7 · Commands

| Command | What it does |
|---|---|
| `make doctor` | active LLM provider, Deepgram, Cartesia, n8n (key + every registered path served by an ACTIVE POST workflow), Chroma; names what is dark by design |
| `make dashboard` | app server on :8787 in the foreground (launchd normally runs it) |
| `make voice` | a console voice session on the Mac's mic (no wake word) |
| `make ui` | rebuild the SvelteKit dashboard after any `ui/src` change |
| `make install-launchd` | install/refresh the 5 always-on agents (idempotent) |
| `make phone-voice` / `make phone-voice-off` | on-demand LiveKit + voiceworker (Docker Desktop first) |
| `make tunnel` / `make tunnel-off` | on-demand Cloudflare Tunnel (see §11; voice lock first) |
| `make lint` · `make test` · `make test-integration` · `make test-scenario` | ruff · L1 · L2 · L4 (the demo) |
| `make eval` | router + tool-selection accuracy vs the real model (export the key first, §10) |
| `make snapshot` | rsync the repo to `~/friday-snapshots/` — the local undo |
| `make collect` · `make gesture` · `make run` | metrics sweep now · build the gesture spike · docker LiveKit + dev worker |
| `uv run python -m scripts.enroll_voice` | build your voiceprint (Phase 5) |
| `uv run python -m scripts.proactive_checkin` | send one proactive check-in now |

---

## 8 · What runs in the background (launchd)

| Agent | When | Does |
|---|---|---|
| `com.friday.dashboard` | always (KeepAlive) | the app server on 127.0.0.1:8787 |
| `com.friday.killswitch` | always (KeepAlive) | menu bar, offline wake word, offline kill, spawns voice sessions |
| `com.friday.metrics` | hourly | collects Friday's own metrics + calendar load |
| `com.friday.logrotate` | hourly | gzip + truncate logs > 10 MB, prune > 7 days |
| `com.friday.checkin` | 09:00 · 13:00 · 19:00 | proactive caring notification (never at login) |
| `com.friday.livekit` + `com.friday.voiceworker` | on demand (`make phone-voice`) | phone-voice server side |
| `com.friday.tunnel` | on demand (`make tunnel`) | Cloudflare Tunnel to friday.paypilotlabs.com |

Restart one: `launchctl kickstart -k gui/$(id -u)/com.friday.<name>` · logs:
`~/Library/Application Support/Friday/logs/<name>.log`.

---

## 9 · Safety model

- **Gates.** `safe` runs; `confirm` asks "Shall I proceed, sir?" and runs only on an
  explicit yes (any negation or doubt refuses); `pin` also needs your spoken 4-digit PIN
  (never logged; unset = locked shut); `blocked` refuses. The gate is replay-safe: the tool
  confirmed is the tool that runs.
- **Kill paths** are offline and beat everything, from any voice.
- **Owner voice** (armed): strangers can't act **by voice**; fail-closed. The HTTP side
  (dashboard, `/jobs`, typed turns) relies on `APP_ACCESS_KEY` + Cloudflare Access.
- **Access.** Every HTTP route needs `APP_ACCESS_KEY` (cookie or Bearer); Cloudflare Access
  in front when public (Phase 6).
- **Honest by construction.** The header shows the real armed wake phrase and lock scope;
  status flags are true only when the thing can actually run; the camera never switches on
  without a vision model; doctor fails when a registered n8n path isn't served.
- **Business isolation.** No Friday tool points at a business/client n8n workflow.
- **Secrets & privacy.** Keys only in `.env` (gitignored, 0600). Voiceprint + speaker model
  in gitignored `voice/models/`. Tests run in a throwaway state dir and never read `.env`.

---

## 10 · Testing

Pyramid (`docs/TESTING.md`): **L1** unit (fakes, < 40 s) · **L2** integration (real
SQLite/Chroma, fake LLM) · **L3** evals vs the real model (router ≥ 90%, tool selection
≥ 90%) · **L4** the demo scenario (`docs/DEMO-SCRIPT.md`) on one thread with the real
`tools.yaml`. Safety code (kill path, gates, emotion gate, voice lock, camera) is TDD.

```bash
make lint && make test && make test-integration && make test-scenario
(set -a; . ./.env; set +a; make eval)    # key scoped to this one command
```

---

## 11 · Deployment

Full guide: **`docs/DEPLOY.md`**. In short:
1. **GitHub** — `git push -u origin main` publishes the phase-wise history (private repo).
2. **Cloudflare** — move `paypilotlabs.com` DNS to Cloudflare (copy existing records
   first!), `cloudflared tunnel create friday`, route `friday.paypilotlabs.com`, put an
   **Access** policy (your email OTP / passkey) in front.
3. **Run** — `make tunnel` (launchd, auto-restart).
4. **Gate** — only after the owner-voice lock is armed, the PIN is set and doctor is clear.
5. **Then** retire the public Tailscale Funnel; keep the tailnet path as the fallback.

---

## 12 · Project layout

```
adapters/      vendor seams: llm(+openai), stt, tts, wakeword, voiceprint, memory, vault(+plan),
               calendar, weather, spotify, apps, mac_actions, camera, browser, n8n, screenpipe
brain/         LangGraph graph + nodes (router, chat, vault, ops, vision, memory_writer),
               confirm/PIN gates, mood + mood_sense, check-in, brief, pending_question
voice/         FridayAgent (llm_node, stt tee), session entrypoint, emotion gate, styling,
               owner_lock, wakeword training assets
client/        killswitch daemon + menu bar + local intents (offline kill path)
integrations/  HTTP server (access gate, static files, /api/v1 route groups), jobs,
               automations (n8n read-only), metrics, reminders, day_summary, jobs_voice
config/        settings (pydantic), tools.yaml, persona.md, metrics.yaml
scripts/       healthcheck, installers, enroll_voice, proactive_checkin, recorders, snapshot
launchd/       core agents + on-demand/{phone,tunnel}
deploy/        cloudflared config template
ui/            SvelteKit dashboard (built to ui/build, gitignored)
tests/         unit · integration · scenario · evals
docs/          guides (below) · memory-bank/ project memory
```

---

## 13 · Troubleshooting

| Symptom | Do |
|---|---|
| anything odd | `make doctor` |
| doctor: `n8n: no active POST workflow for tool(s): send_summary` | activate "Friday — Send me a summary" in the n8n editor (TODO #1) |
| dashboard shows old data after a code change | `launchctl kickstart -k gui/$(id -u)/com.friday.dashboard` (+ `make ui` for UI changes) |
| a changed `.env` value isn't picked up | restart the dashboard (settings are cached per process); voice sessions read `.env` fresh each wake |
| "My voice lock can't verify you" | voiceprint/model missing while `VOICE_LOCK_TURNS=true` → run `scripts.enroll_voice` or turn the lock off |
| "I only take instructions from sir" for you | lower `VOICEPRINT_THRESHOLD` a little or re-enroll in the room you use |
| jobs data hangs | macOS Privacy → Files and Folders → allow Downloads for the app's Python |
| camera / screen questions | parked by design (doctor says so) |
| roll back code | `git revert <commit>` or copy from `~/friday-snapshots/` |

---

## 14 · Docs index

| Doc | For |
|---|---|
| `docs/SETUP.md` | every key and integration, in order |
| `docs/DEPLOY.md` | GitHub + Cloudflare Tunnel + Access, the go-live gate, rollback |
| `docs/ARCHITECTURE.md` | layers, feature → module → test map, coding standards |
| `docs/EMOTIONS.md` | the mood engine and emotional voice |
| `docs/TESTING.md` | the test pyramid rules |
| `docs/DEMO-SCRIPT.md` | v1 definition of done |
| `docs/MOBILE.md` | using Friday from the phone |
| `docs/phases/` | the Phase 1–6 specs this build implements |
| `docs/SYSTEM-REVIEW.md`, `PLAN-NEXT.md`, `UPGRADE-PLAN.md` | history / roadmap context |
| `memory-bank/` | project memory: PROGRESS, DECISIONS, CONVENTIONS |

---

## 15 · TODO — what still needs doing

Everything code-side for Phases 1–6 is done and tested. These items need **you**
(accounts, recordings, clicks) — in this order:

- [ ] **1. Activate the summary workflow.** n8n editor → "Friday — Send me a summary" →
      open the **"Send to Telegram"** node → replace `SET_YOUR_TELEGRAM_CHAT_ID` with your
      chat id (message @userinfobot to get it) → Save → toggle **Active**.
      Check: `make doctor` → all clear; say "send me a summary of my day" → "yes, go ahead".
- [ ] **2. Add your OpenAI key.** `.env` → `OPENAI_API_KEY=` (you have ~$8: Anthropic stays
      the default brain). To hear the emotional OpenAI voice: `TTS_PROVIDER=openai`.
      To try OpenAI as the brain for a turn: `LLM_PROVIDER=openai` (flip back after).
- [ ] **3. Record + train "Hey Friday".** `uv run python -m scripts.record_wakeword`
      (~50 clips, near/far, quiet/noisy) → train (voice/wakeword/README.md) → set
      `WAKE_MODEL_PATH`. The header then shows "Hey Friday".
- [ ] **4. Arm only-my-voice.** Record normal speech:
      `uv run python -m scripts.record_voice_verifier` (+ optional 2–5 min reads in
      `voice/enroll/*.wav`) → `uv run python -m scripts.enroll_voice` → set the suggested
      `VOICEPRINT_THRESHOLD`, `VOICE_LOCK_TURNS=true` → test with a friend's voice (must be
      refused). Optional wake verifier: `scripts.train_voice_verifier` + `WAKE_VERIFIER_PATH`,
      `WAKE_REQUIRE_VERIFIER=true`.
- [ ] **5. Set a spoken PIN** if you haven't: `FRIDAY_PIN=` (4 digits).
- [ ] **6. Fish Audio voice (optional).** Get `FISH_API_KEY`, upload a clean 15–60 s sample
      of the voice Friday should have → `FISH_VOICE_ID`, then `TTS_PROVIDER=fishaudio`.
- [ ] **7. Push to GitHub.** `git push -u origin main` (history already committed per phase).
- [ ] **8. Go public (only after #4 and #5).** Follow `docs/DEPLOY.md`: Cloudflare DNS
      (copy existing records first), `brew install cloudflared`, tunnel create/route,
      `~/.cloudflared/config.yml` from `deploy/`, Access policy, `make tunnel`, test on
      cellular, then retire Tailscale Funnel.
- [ ] **9. Browser tasks:** open Chrome once with the `~/friday-chrome` profile and sign in to
      the sites you want Friday to operate.
- [ ] **10. Housekeeping:** `~/Jarvis Life OS/` (old logs only) — archive or delete, your call.

Later (code, when you want them): phone-mic voice client, Fish emotion polish after
listening tests, an on-demand screen-reading replacement for screenpipe, Apple Vision OCR
+ a small local model for the camera, business metrics on the Metrics card.

---

## 16 · History (phase commits)

| Commit | Phase |
|---|---|
| v1 baseline | Jarvis Life OS as of 2026-09-29 |
| Phase 1 | cleanup, full Jarvis → Friday rename, integrations audit |
| Phase 1b | link everything to Friday + adversarial-review fixes |
| Phase 2 | multi-provider LLM |
| Phase 3 | mood engine + emotional voice |
| Phase 4 | buddy behaviours + actions |
| Phase 5 | only-my-voice (per-turn owner verification) |
| Phase 6 | public deploy scaffold (Cloudflare Tunnel + Access) |
| Docs | this README, final docs, review fixes |
