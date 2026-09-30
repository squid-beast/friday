> **2026-09-28:** the active plan is `docs/PLAN-NEXT.md` (read `docs/SYSTEM-REVIEW.md` first). This file is the original v2 build doc.

# FRIDAY — Phased Implementation Plan v2 (Claude Code Build Doc)

> **How to use:** Project home is `/Users/lohithkumar/langgraph` (git removed; upstream LangGraph source preserved under `reference/langgraph-src/` for studying internals — never import from it, always pip-install langgraph). Rename this file to `PLAN.md` at the folder root. Work ONE phase per Claude Code session: "Read PLAN.md and implement Phase N. Do not start the next phase." Every session ends by running `/wrap` (defined in Phase 1) so project memory stays current. `[LOHITH INPUT]` = things only you can provide.

---

## 0. Locked Decisions

| Decision | Value |
|---|---|
| Brain + everything | MacBook (Apple Silicon 16GB). Hostinger VPS = n8n only (authed webhooks). |
| LLMs | Anthropic API — Sonnet (thinking), Haiku (routing) |
| STT / TTS | Deepgram Nova / Cartesia (ElevenLabs fallback) |
| Voice runtime | LiveKit server + Agents, both local |
| Wake phrase | "Wake up, Daddy's home" · Kill phrase: "Stand down" |
| Persona | Full Friday roleplay — "sir", dry British wit; spoken replies ≤3 sentences unless asked to elaborate |
| Runtime memory | leos-brain vault (native path) + mem0/Chroma facts |
| **Project memory** | **Memory-bank pattern: CLAUDE.md (≤150 lines) + imported `memory-bank/` files, updated every session via `/wrap`** |
| Vision | screenpipe (screen) + moondream (camera, on-demand) + browser-use (web) |
| Codebase | Python 3.12 monorepo, `uv`, pydantic-settings, ruff |
| **Version control** | **Private GitHub remote allowed (`squid-beast/friday`, updated 2026-09-29). Secrets never committed — `.env*`, `data/`, build output are gitignored. Commit/push only on Lohith's ask. `make snapshot` → `~/friday-snapshots/` stays the safety net.** |
| Phone access | Deferred → Phase 7 |
| n8n details | Placeholders, filled at Phase 4 |
| Project home | `/Users/lohithkumar/friday` (moved 2026-09-28); upstream LangGraph source lives in `reference/langgraph-src/` (reference only, never imported, gitignored) |

---

## 1. Architecture Principles

1. **Two memory systems, never confused.** *Project memory* = what WE are building (CLAUDE.md + memory-bank/, read by Claude Code). *Runtime memory* = what FRIDAY knows about Lohith (vault + mem0, read by the agent). Different folders, different consumers.
2. **Ports and adapters.** Vendor SDKs live ONLY in `adapters/`. Brain code imports interfaces. Swap Deepgram for whisper later = one file.
3. **Everything is a tool.** New capability = entry in `config/tools.yaml` + one adapter. `graph.py` routing never changes for new tools.
4. **Risk is config.** `tools.yaml` marks tools `safe` / `confirm` / `blocked`; the confirm-gate node reads it.
5. **Local overrides beat cloud.** "Stand down" / "camera off" matched in `client/local_intents.py` before any network call.
6. **One state object.** Typed `FridayState` (pydantic) flows through the graph. No globals.
7. **Boring persistence.** SQLite + Chroma under `data/`, excluded from snapshots' size by keeping media out.
8. **Every phase shippable.** System runs at the end of every phase; later features are polite stubs ("not armed yet, sir").
9. **CLAUDE.md stays small.** Under 150 lines; everything detailed lives in `memory-bank/` files it imports. (Community rule: bloated CLAUDE.md = context rot.)

---

## 2. Repo Layout — merged: Claude Code workspace layer + runtime layer

```
langgraph/                           # /Users/lohithkumar/langgraph — NO git
├── PLAN.md                          # this file
├── reference/langgraph-src/         # upstream LangGraph source — READ-ONLY reference, never imported
├── CLAUDE.md                        # ≤150 lines; imports memory-bank files (§3)
├── .claude/
│   ├── settings.json                # hooks config (§4)
│   └── commands/
│       ├── wrap.md                  # /wrap — end-of-session memory update ritual
│       ├── status.md                # /status — read memory-bank, say where we are
│       └── test-all.md              # /test-all — run lint + tests, summarize
├── memory-bank/                     # PROJECT MEMORY (for Claude Code, not Friday)
│   ├── PROJECT.md                   # vision, what Friday is, why, end-state
│   ├── DECISIONS.md                 # append-only log: date, decision, reason
│   ├── PROGRESS.md                  # current phase, what works, what's next, open bugs
│   └── CONVENTIONS.md               # code style, patterns, how to add a tool/adapter
├── pyproject.toml                   # uv workspace
├── docker-compose.yml               # livekit-server, chroma (bind 127.0.0.1)
├── .env.example                     # every var documented; .env NEVER in snapshots shared anywhere
├── Makefile                         # run / voice / test / lint / eval / doctor / snapshot
├── config/
│   ├── settings.py                  # pydantic-settings — ONLY config entry point
│   ├── tools.yaml                   # tool registry: name, description, adapter, risk
│   └── persona.md                   # Friday system prompt
├── brain/
│   ├── graph.py                     # LangGraph wiring
│   ├── state.py                     # FridayState
│   ├── nodes/                       # router, chat, vault, ops, vision, memory_writer
│   └── confirm.py                   # interrupt() confirm-gate
├── adapters/                        # ALL vendor SDKs live here, one file each
│   ├── llm.py  stt.py  tts.py
│   ├── vault.py  memory.py          # runtime memory (leos-brain + mem0)
│   ├── n8n.py                       # Phase 4
│   └── screenpipe.py  camera.py  browser.py   # Phase 5
├── voice/
│   ├── agent.py                     # LiveKit worker STT→graph→TTS
│   └── wakeword/                    # trained model (Phase 3)
├── client/
│   ├── daemon.py                    # DORMANT/ACTIVE state machine
│   ├── local_intents.py             # offline kill/capture commands
│   └── killswitch.py                # menu-bar + hotkey
├── audit/log.py                     # append-only SQLite audit of tool calls
├── data/                            # runtime state: checkpoint.db, chroma/, audit.db
├── scripts/
│   ├── record_wakeword.py
│   ├── snapshot.sh                  # rsync → ~/friday-snapshots/friday-YYYYMMDD-HHMM/ (excludes data/, .env kept LOCAL)
│   └── healthcheck.py
└── tests/                           # pytest; graph tests use fake adapters
```

Why this merge (vs. the two structures you screenshotted): the "AI Agent Project Structure" post is the runtime layer — ours is that, with `adapters/` instead of a `utils/` dump so vendor code can't leak everywhere. The "Claude Code Project Structure" post is the workspace layer — CLAUDE.md + `.claude/` + memory files — which is exactly Anthropic's own guidance for project memory. You need both layers; neither image alone covers the other's job. Skipped from that image as overkill for a solo project: `agents/*.yml` teams, plugins/, marketplace stuff — add later only if a real need appears.

---

## 3. Project Memory System (Claude Code layer)

**CLAUDE.md** (create in Phase 1, verbatim skeleton):
```markdown
# Friday
Personal voice assistant. SECRET project — local only, no git, no remotes, never reference it outside this folder.

@memory-bank/PROJECT.md
@memory-bank/PROGRESS.md
@memory-bank/CONVENTIONS.md
@memory-bank/DECISIONS.md

## Rules
- Read PLAN.md before any work. Implement only the phase asked.
- Python 3.12, uv, ruff, type hints, pydantic at boundaries.
- Vendor SDKs only inside adapters/. Brain imports interfaces only.
- Secrets only via config/settings.py (.env). Never hardcode or log them.
- Every tool execution goes through audit/log.py.
- New capability = tools.yaml entry + adapter. Never edit graph routing for it.
- Files ≤200 lines. make lint && make test must pass before finishing.
- End EVERY session by running /wrap.
```

**The `/wrap` command** (`.claude/commands/wrap.md`): "Update memory-bank/PROGRESS.md (current phase, what now works, next step, open bugs). Append any decisions made this session to DECISIONS.md with date + one-line reason. If conventions changed, update CONVENTIONS.md. Then run `make snapshot`. Summarize in 3 bullets what a fresh session needs to know."

**The `/status` command**: "Read memory-bank/ and PLAN.md. Tell me: current phase, last session's work, today's suggested next step. 5 lines max."

This is how the project "remembers what we're making": every new Claude Code session auto-loads CLAUDE.md → which imports the four memory-bank files → zero re-explaining.

---

## 4. Hooks (`.claude/settings.json`) — no-git edition

- **SessionStart**: run `scripts/healthcheck.py --quick` and print PROGRESS.md's "Next step" line.
- **PostToolUse (write/edit)**: `ruff check --fix` the touched file.
- **No PreCommit hooks** (no git). Snapshot safety instead: `/wrap` runs `make snapshot`.
- **Notification**: none for now (secret project — no Slack/webhook pings).

---

## 5. Phase Plan

### PHASE 1 — Skeleton + Memory Bank + Voice Loop
**Build:** repo layout §2; CLAUDE.md §3; the three `/commands`; hooks §4; `memory-bank/` seeded (PROJECT.md written from PLAN §0–1, PROGRESS.md = "Phase 1 in progress", DECISIONS.md seeded with §0 table, CONVENTIONS.md = adapter/tool patterns); `scripts/snapshot.sh`; docker-compose (livekit dev, chroma, 127.0.0.1 only); adapters llm/stt/tts; persona.md (roleplay rules, 3-sentence cap); `voice/agent.py` (VAD, barge-in); push-to-talk client v0; healthcheck; tests.
**[LOHITH INPUT]:** `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY` in `.env`; Docker Desktop; Cartesia voice ID → `TTS_VOICE_ID`.
**Accept:** 10-turn spoken convo, interruptions work, in character; `/status` and `/wrap` work; `make snapshot` produces a browsable copy; lint+tests green.

### PHASE 2 — Brain Graph + Vault + Runtime Memory
**Build:** `state.py`; router (Haiku → chat|vault|ops|vision|recall; unarmed routes reply "not armed yet, sir"); chat + vault nodes; graph wiring + SQLite checkpointer; `adapters/vault.py` (ripgrep search, READ + APPEND-to-inbox only, path allowlist, off-limits config); `adapters/memory.py` (mem0+Chroma: remember/recall); async `memory_writer`; swap voice agent onto the graph; 20-utterance router test.
**[LOHITH INPUT]:** confirm `VAULT_PATH=/Users/lohithkumar/leos-brain`; off-limits folders (default none).
**Accept:** vault question answered correctly; fact told → full restart → recalled; router ≥90% on test set.

### PHASE 3 — Wake Phrase, Sessions, Kill Switches
**Build:** `record_wakeword.py` (50 samples, guided near/far/quiet/loud) + openWakeWord training steps in README; daemon v1 state machine (DORMANT: only wake model listening, zero streaming → ACTIVE on phrase, chime + "At your service, sir" → ends on stop-phrase/120s silence/hotkey); `local_intents.py` offline matcher (stand down, go to sleep, camera off, stop watching my screen, mute yourself, resume …) killing real processes; menu-bar killswitch (rumps) + global hotkey; session events → audit.
**[LOHITH INPUT]:** ~30 min recording session; hotkey choice (default ⌥⌘J).
**Accept:** wakes across the room; <2 false wakes/day; "stand down" works with Wi-Fi off; menu-bar state truthful.

### PHASE 4 — Hands: n8n Ops
**Build:** `adapters/n8n.py` (POST + `X-Friday-Secret` header, timeout, one retry); tools.yaml entries for 5 workflows; ops node: select tool → risk=`confirm` → interrupt "Shall I proceed, sir?" → spoken yes → execute → spoken summary; README steps for adding header-auth in n8n; full audit.
**[LOHITH INPUT] fill-in table:**

| # | Workflow | Does what | Webhook path | Safe/Destructive |
|---|---|---|---|---|
| 1–5 | ____ | ____ | ____ | ____ |

Plus `N8N_BASE_URL`, shared `N8N_WEBHOOK_SECRET` (openssl rand -hex 32, mirrored in n8n).
**Accept:** safe workflow voice-triggered end-to-end; destructive refuses without spoken yes; "what did you do today, sir?" reads audit log.

### PHASE 5 — Eyes: Screen, Camera, Browser
**Build:** screenpipe (brew) + `adapters/screenpipe.py` (local search API, exclusion list) + vision/recall routes live; `adapters/camera.py` — single-frame capture → moondream (lazy-loaded) → describe, auto-release, menu-bar flash, NEVER continuous; `adapters/browser.py` — browser-use, dedicated Chrome profile `~/friday-chrome`, max-steps cap, submit/purchase = `confirm`; re-verify P3 kill commands against these real processes.
**[LOHITH INPUT]:** screenpipe exclusions (suggest banking + WhatsApp); log the dedicated profile into needed accounts.
**Accept:** "that repo I looked at yesterday afternoon?" answers; camera Q&A works, light goes off after; one browser task completes; kill commands verified.

### PHASE 6 — Polish + Reliability
**Build:** LangSmith tracing (optional) + 30-case router eval (`make eval`); spoken morning brief (launchd/n8n cron → brain → spoken on first wake of the day); launchd plists auto-start livekit/daemon/worker with crash-restart; spoken 4-digit PIN for highest-risk tools; `make doctor`.
**[LOHITH INPUT]:** spoken PIN; LangSmith key (optional).
**Accept:** reboot → everything up with zero terminal; a week of daily use hands-free.

### PHASE 7 — Phone via Tailscale + PWA (v1 BUILT 2026-08-10; pulled forward by Lohith)
Text chat + Mission Board on the phone; the server stays on 127.0.0.1 and
`tailscale serve` proxies it into the private tailnet over TLS (docs/PHONE.md).
integrations/ask.py bridges phone text into the SAME brain — router, confirm/PIN
gates, audit, and kill phrases all hold over text ("stand down" typed on the phone
cuts the session at home). /chat PWA (Add to Home Screen), com.friday.dashboard
launchd agent. The tailnet already exists (Mac, iPhone, Hostinger VPS).
**[LOHITH INPUT]:** `tailscale serve --bg 8787` on the Mac; toggle Tailscale on
on the iPhone; Add to Home Screen.
**Accept:** from the phone (Wi-Fi off, cellular): board loads, a chat turn answers,
a confirm-gated tool asks and obeys, "stand down" ends the home session.
**P7.5 — App Screens + Content Studio (BUILT 2026-08-11; scope set by Lohith):**
Four screens on one nav — / (board), /chat, /studio, /today. Content Studio =
Instagram + n8n as one section: n8n trending webhook -> review cards (score, hook,
editable caption) -> two-tap POST -> n8n publishes to Instagram (creds stay in n8n;
every publish audited). Today = calendar + activity with honest permission empty-states.
integrations/content.py (data/content.db, new->posted|skipped), api.py, route tables.
**[LOHITH INPUT]:** the two n8n workflows + CONTENT_*_WEBHOOK env (docs/CONTENT-STUDIO.md).
**Accept:** PULL TRENDS fills cards from your n8n; POST publishes to IG and the item
leaves review; "what did you do today, sir?" mentions the ig_publish.

**P7.6 — Voice from the phone (BUILT 2026-08-11):** /voice screen (5th tab) with the
VENDORED livekit-client SDK (integrations/static/, zero external resources rule holds);
/api/voice-token mints a JWT scoped to room "phone" only; signalling rides tailscale
serve HTTPS/WSS (iOS secure-context mic), WebRTC media flows directly over the tailnet
(compose: LIVEKIT_BIND_IP/--node-ip, default stays loopback). Same agent, same barge-in,
same kill phrases. Setup + undo: docs/PHONE.md.
**[LOHITH INPUT]:** 3 .env lines (tailscale IP x2, VOICE_WS_URL), the 8443 serve
listener, `make run`, mic permission on the phone.
**Accept:** from cellular via tailnet — CONNECT, converse with barge-in, "stand down"
ends the session; unconfigured Voice screen shows setup, never errors.

### PHASE D — Dashboard & Integrations (added 2026-08-10, Lohith's decision — see DECISIONS.md)
Visual tracking across platforms, inside this repo. Architecture: platform credentials
stay IN N8N; the Mac pulls metrics from authed n8n webhooks into data/metrics.db;
the Mission Board serves 127.0.0.1 only. Docs: docs/DASHBOARD.md.

**D1 — Board + pipeline (BUILT 2026-08-10):** integrations/ package (store, friday_health,
n8n_pull, collect, server + dashboard.html); config/metrics.yaml registry;
`make collect` / `make dashboard`; hourly launchd timer (com.friday.metrics).
**[LOHITH INPUT]:** the four n8n metrics workflows (table in docs/DASHBOARD.md) + their
paths in config/metrics.yaml.
**Accept:** board shows live Instagram/BookYourSlot/leads/n8n/Friday cards after one
`make collect`; survives a dead webhook; hourly refresh hands-free.

**D2 — Calendar + voice metrics (BUILT 2026-08-10):** adapters/calendar.py (EventKit read +
LLM-parsed create, confirm-gated via tools.yaml); integrations/metrics_voice.py (spoken
Mission Board); tools.yaml carries its first three live entries; brief leads with the first
event; board gains a calendar card; tool-adapter contract is now fn(arg, utterance).
Docs: docs/CALENDAR.md. Calendar choice resolved: EventKit reads Calendar.app — adding the
Google account there covers Google (DECISIONS.md).
**[LOHITH INPUT]:** allow the macOS Calendar permission prompt on first use.
**Accept:** brief mentions today's first event; a spoken metrics question answers from the store.

---

## 6. .env.example

```bash
# LLM
ANTHROPIC_API_KEY=
MODEL_SMART=claude-sonnet-latest
MODEL_FAST=claude-haiku-latest
# Voice
DEEPGRAM_API_KEY=
CARTESIA_API_KEY=
TTS_VOICE_ID=
ELEVENLABS_API_KEY=            # optional fallback
# LiveKit local
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=            # openssl rand -hex 32
# Runtime memory
VAULT_PATH=/Users/lohithkumar/leos-brain
VAULT_EXCLUDE=
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
# n8n (Phase 4)
N8N_BASE_URL=
N8N_WEBHOOK_SECRET=
# Vision (Phase 5)
SCREENPIPE_URL=http://127.0.0.1:3030
SCREENPIPE_EXCLUDE=
# Sessions
SESSION_SILENCE_TIMEOUT_S=120
WAKE_THRESHOLD=0.6
# Observability (optional)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=friday
```

---

## 7. Master Input Checklist

| When | Item |
|---|---|
| P1 | 3 API keys · Docker Desktop · Cartesia voice ID |
| P2 | Vault path confirm + off-limits folders |
| P3 | 50 wake-phrase recordings · hotkey choice |
| P4 | n8n URL · 5-workflow table · shared secret |
| P5 | screenpipe exclusions · Chrome profile logins |
| P6 | Spoken PIN · LangSmith key (optional) |

---

## 8. Claude Code Session Prompts

- **P1:** `Read PLAN.md. Implement Phase 1 exactly — full skeleton, CLAUDE.md + memory-bank seeded, /wrap /status /test-all commands, hooks, snapshot script, adapters, voice agent with persona, push-to-talk client, tests. No git — do not run git init. Stop at the acceptance list and tell me how to run it. Then run /wrap.`
- **P2:** `Read PLAN.md and /status. Implement Phase 2. Include the router test set. End with /wrap.`
- **P3:** `Read PLAN.md and /status. Implement Phase 3. The kill path must work with zero network. End with /wrap.`
- **P4:** `Read PLAN.md and /status. Implement Phase 4 with this table: <paste>. Confirm-gate via LangGraph interrupt + spoken yes. End with /wrap.`
- **P5:** `Read PLAN.md and /status. Implement Phase 5. Camera is single-frame on-demand only. Re-verify all kill commands. End with /wrap.`
- **P6:** `Read PLAN.md and /status. Implement Phase 6. End with /wrap.`
