# Friday — System Review & Working Context (2026-09-28)

> **What this file is.** The single catch-up document for any person or Claude session opening this
> repo. It records what Friday is, what it runs today, what's broken, what was decided in the
> 2026-09-28 working session with Lohith ("sir"/Leo), and what should be kept, paused or removed.
> The build plan (`docs/PLAN-NEXT.md`, to be written) will be derived from this file.
>
> Measured live on the Mac (Apple M4, 16 GB RAM, macOS 26.6) on 2026-09-28 ~16:30 ET.
> Rules in `CLAUDE.md` still apply: no git commands, `make snapshot` before changes, files ≤ 200
> lines, tests with every feature, update README after every task.

---

## 1. What Friday is (one paragraph)

Friday is Lohith's local-first, voice-first personal AI OS. The Mac is the brain: a Python
dashboard server (`integrations/server.py`, port 8787) serves a SvelteKit UI and an API; a LangGraph
"brain" (`brain/`) routes requests to tools (`config/tools.yaml`) and adapters (`adapters/`); a
LiveKit voice worker (`voice/agent.py`) handles wake word → speech-to-text → Claude → text-to-speech;
Obsidian (`~/leos-brain`) is the long-term memory, searched through an embedded Chroma index. It is
reached on the laptop at `http://127.0.0.1:8787` and on the phone over Tailscale, gated by an access
key. The long-term goal is one place — `friday.paypilotlabs.com` — where Lohith sees and controls
everything (jobs, content, reminders, voice) live.

---

## 2. Session history — 2026-09-28 (what happened, in order)

| # | Topic | Outcome / decision |
|---|---|---|
| 1 | **Nightly job run** (scheduled task, runbook `~/Downloads/Jobs/_engine/RUNBOOK.md`) | Batch **2026-09-28** prepared: 35 roles (big 11 / mid 13 / startup 11), each with its own tailored resume + cover letter, fact-checked by an independent agent. 23 Claude-submittable (Ashby/Greenhouse), 11 portals, 1 Leo-only (Mintlify). **Nothing submitted** — waiting for Leo's OK. |
| 2 | Sponsorship filter | Leo: **skip postings that won't sponsor.** `lib/gates.py` NOSPON widened and made a hard gate (108 postings dropped that night). |
| 3 | Volume | Target raised from 30–40 to **50–100 roles/night** (aim ~70). |
| 4 | Experience | Roles asking 4–5 years are in. Leo asked to change his years on the resume; **declined** — experience is always stated truthfully (3 years). 6+ years stays out. |
| 5 | Roles per company | No fixed 2-per-company cap; only a company's own stated limit (`_engine/state/company_policy.json`, e.g. Salesforce). |
| 6 | Email codes | Code-requiring portals (Oracle guest forms, Workday verify-email) go to a queue (`_engine/state/code_queue.json`) for an **11:00 AM** daytime run that reads the code from the application inbox. The 11 AM scheduled task could **not** be created (blocked by the permission check) — pending Leo's decision. |
| 7 | Schedule | Nightly prep moved to **10:46 PM ET** (jittered from 11 PM). A **12:20 AM restart check** resumes a batch if the main run stopped part-way (`_engine/state/progress_<B>.json`). |
| 8 | Gmail | Application inbox **lohithkumarneerukonda@gmail.com** connected. Labels created: Applied, Assessment, Interview, Verification Code, Recruiter Outreach, Job Alerts (existing Rejection / Positive Response reused). 60-day analysis: 54 applications, 11 rejections, 0 interviews yet; entry-level "SE I / Associate" titles rejected fastest; backend and FDE roles hold up best; no evidence of instant sponsorship auto-rejects. |
| 9 | Profile answers saved (`_engine/profile/me.json`) | Travel: anywhere. Notice period: none (start immediately). Not authorized to work in Canada. No relatives at any company. GitHub: only the profile link until Leo makes repos public. *Still missing: current job level.* |
| 10 | Accounts | Checklist at `~/Downloads/Jobs/ACCOUNTS_TO_CREATE.md` (24 Workday tenants, 12 IT-services portals, what needs no account). Claude never creates accounts or types passwords. |
| 11 | Dashboard idea | Leo wants one live visual place instead of MD files + prompting. Agreed: build it **inside Friday**, local-first; Friday owns job data, Obsidian stays the readable mirror. Login later: **email + password + authenticator (TOTP)** modeled on BookYourSlot (Cal.com) — no Google sign-in. |
| 12 | On-demand services | Leo wants services to run **only when needed**. Agreed architecture: one small always-on gateway + a supervisor that starts/stops modules (voice, vision, screen memory) with idle timeouts, memory caps and "one heavy model at a time". |
| 13 | Free local models | Leo wants free/local models. Recommended stack for 16 GB: Qwen3 8B (brain), Qwen3 1.7B (router), Gemma 3 4B + Apple Vision OCR (vision), Whisper large-v3-turbo (STT), Kokoro (everyday TTS), Chatterbox (emotional TTS), nomic-embed-text (vault search), via Ollama with `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE=5m`. Personality: supportive, witty, straight-talking — original character, **no cloned real-actor voice**. |
| 14 | VPS (Hostinger KVM 4, 2.25.89.115) | Good for always-on, background work (gateway, jobs DB, n8n, small Ollama models, embeddings); **too slow for live voice with 8B on CPU**. Ollama must **never** be exposed publicly — Tailscale only. |
| 15 | **Built: Jobs command center v1** | `/jobs` page + cockpit Jobs card + `/api/v1/jobs/*` + 13 tests. Full unit suite 576 passed, ruff clean. See §4. |
| 16 | Breakage found & partly fixed | Repo moved to `~/friday` this morning; launchd agents still point to `~/Jarvis Life OS` → most services crash-looping. Dashboard fixed; others pending. See §6. |

---

## 3. Architecture today

```
Phone / laptop ──(Tailscale, access-key cookie)──> integrations/server.py :8787
                                                    ├─ ui/build (SvelteKit static)
                                                    ├─ /api/v1/*  (integrations/api.py, jobs_api.py)
                                                    └─ /api/v1/conversation → brain (LangGraph)
brain/graph.py → router → nodes (chat, ops, vault, vision, memory_writer)
                         → tools.yaml → adapters/* (Claude, n8n, calendar, Spotify, telephony…)
voice/agent.py (LiveKit agents): wake word → Deepgram STT → Claude → Cartesia TTS
Memory: Obsidian vault (~/leos-brain) + Chroma (embedded) + SQLite (audit, checkpoints, content, metrics)
Background: launchd agents (§5). External: n8n (content studio, business workflows).
Job engine (separate): Claude cloud runs nightly → ~/Downloads/Jobs/<date>/ → Friday /jobs reads it.
```

Code size (non-test): adapters 1,090 lines · brain 979 · integrations 1,523 · client 428 ·
gesture 507 · voice 155 · scripts 468 · config 192 · UI 990. Tests: 67 files, 6,719 lines, 576 passing.

---

## 4. Feature inventory — keep / change / pause / remove

| Feature | Where | State today | Recommendation |
|---|---|---|---|
| Dashboard server + cockpit UI | `integrations/server.py`, `ui/` | Running (fixed today) | **Keep** — becomes the gateway. |
| **Jobs command center** (new) | `integrations/jobs*.py`, `ui/src/routes/jobs` | Built; data calls hang until macOS allows Python to read `~/Downloads` | **Keep** — core. Grant Downloads access (or move job data out of Downloads). |
| Conversation / brain | `brain/`, `adapters/llm.py` | Works via Claude API | **Keep**; add Ollama provider (local-first) with Claude as optional fallback. |
| Voice worker | `voice/agent.py`, LiveKit | **Crash-looping** (old path) | **Change**: on-demand; swap Deepgram → Whisper, Cartesia → Kokoro/Chatterbox. |
| LiveKit (Docker) | `docker-compose.yml` | Docker not running (exit 14 loop) | **Pause**: only needed for phone voice; start on demand. |
| Wake word + kill switch | `voice/wakeword`, `client/killswitch.py` | **Crash-looping** (old path) | **Keep** (safety); fix path. |
| Vision — Moondream | `scripts/moondream_serve.py`, `~/.moondream-station` (1.1 GB) | **Crash-looping**; M3 too heavy, M2 fallback | **Remove**; replace with Apple Vision OCR + Gemma 3 4B (Ollama, on demand). |
| Screen memory — Screenpipe | was launchd `com.jarvis.screenpipe` | **REMOVED 2026-09-28** (Leo): agent stopped, plist moved to `~/jarvis-snapshots/removed/`, 26 GB recordings deleted (disk free 24 → 50 GB) | Remove code in PLAN-NEXT Phase 3; replace with on-demand screen reading (Phase 5). |
| Gesture control | `gesture/` (Swift spike) | Not running; spec'd, G0 only | **Park** — keep code, no agent. Revisit later. |
| Content Studio (Instagram via n8n) | `integrations/content.py` | Webhooks set | **Keep if still posting**; otherwise pause. |
| Metrics collector (hourly) | `integrations/collect.py` | **Failing** (old path) | Keep; fix path. Confirm the Metrics panel is still wanted. |
| Log rotation (hourly) | `scripts/rotate_logs.py` | **Failing** (old path) → logs grew to 171 MB | **Keep**; fix path first. |
| Tools: weather, reminder, calendar, open_apps, spotify | `tools.yaml` | Available | **Keep**. |
| Tool: job_search | `tools.yaml` | Overlaps the Claude job engine | **Replace** with "jobs status/show jobs" backed by the Jobs module. |
| Tools: review_draft, lead_intake, vendor_report, maintenance_request | `tools.yaml` → n8n | Small-business demo tools (not personal) | **Remove from Friday** unless Leo uses them daily; they belong in the business stack (VoxPilot/momentum.ops). |
| Tool: make_call | `adapters/telephony.py` | Telephony key empty → dormant | **Remove or park** until a provider is chosen. |

---

## 5. Processes (launchd agents) — measured 2026-09-28

| Agent | Starts at login | State | Cost | Action |
|---|---|---|---|---|
| com.jarvis.dashboard | yes, KeepAlive | running (fixed) | ~70 MB | keep always-on |
| com.jarvis.killswitch | yes, KeepAlive | crash loop, exit 1 | CPU churn, 61 MB log | fix path |
| com.jarvis.voiceworker | yes, KeepAlive | crash loop, exit 1 | CPU churn | on-demand |
| com.jarvis.livekit | yes | crash loop, exit 14 (Docker off) | CPU churn | on-demand |
| com.jarvis.moondream | yes, KeepAlive | crash loop, exit 2 | CPU churn, 26 MB log | remove |
| com.jarvis.screenpipe | yes, KeepAlive | running | ~1 GB RAM, 26 GB disk | pause / opt-in |
| com.jarvis.metrics | hourly | failing | small | fix path |
| com.jarvis.logrotate | hourly | failing | logs unbounded | fix path |
| Ollama.app (not Friday's) | yes | idle (only a cloud model) | ~40 MB | keep; pull local models later |

Four agents respawn roughly every 10 seconds all day. That is wasted CPU and the main source of
log growth. **Fix: `make install-launchd`** re-points every agent at `~/friday` (it will also
re-arm Moondream and Screenpipe — so disable those two first, per §4).

---

## 6. Logs & monitoring — findings

- **Two log locations.** Old: `~/Jarvis Life OS/data/logs` (171 MB: killswitch 61 MB, screenpipe 43 MB,
  dashboard 32 MB, moondream 26 MB). New: `~/Library/Application Support/Friday/logs`.
  After the path fix, archive the old folder.
- **Nothing alerted** when the repo move broke six services. There is no crash-loop detection.
- **`ui/build` was missing** → the dashboard had been serving "UI not built". Rebuilt today.
- **`.venv` console scripts** carry the old path (`uv run pytest` fails); `uv sync --reinstall` fixes it.
- **Jobs endpoint hang**: the dashboard's Python has no macOS permission for `~/Downloads`; requests
  block (BrokenPipe in log). Handlers need a timeout, and the data folder should not require TCC.

**Monitoring to build (professional baseline):**
1. `GET /api/v1/health` — one JSON: each agent's state, last exit code, restarts in the last hour,
   log sizes, disk free, memory pressure, last nightly job run.
2. Crash-loop guard — `ThrottleInterval` in plists + the supervisor disables an agent after N
   failures in 10 minutes and tells Leo (push + dashboard banner) instead of looping forever.
3. Structured JSON logs (level, module, event) in ONE folder; rotation that actually runs;
   hard cap per file.
4. `make doctor` checks paths, build, venv, permissions (Downloads/TCC), Docker, disk < 15 % free.
5. A "System" card on the cockpit showing red/amber/green from `/health`.
6. Nightly job run writes `progress_<B>.json`; the dashboard shows it live (already wired in `/jobs`).

---

## 7. Decisions (Leo, later on 2026-09-28)
- Dashboard Approve **and** saying "approve" both count as approval (runbook + nightly task updated).
- Screenpipe removed + recordings deleted. Gesture control and Content Studio panel: not used now (parked).
- Voice: "Hey Friday" talks; single precise actions (open one app, play a named song / Liked Songs, meetings, weather); never open every app on wake. Reels: make, name, caption, post (with approval).
- The build plan is `docs/PLAN-NEXT.md`.

### Originally open (kept for history)

1. Dashboard "Approve" counts as "submit" approval? (Today: recorded only; Claude still waits for chat OK.)
2. Create the 11 AM code-queue task again, or set it up himself?
3. Current job level for application forms.
4. Wake word always listening, or start Friday by click/shortcut?
5. Screenpipe: off, opt-in toggle, or work-hours schedule? OK to prune its 26 GB?
6. Remove the business demo tools and `make_call` from Friday?
7. VPS: add to Tailscale and host the always-on gateway + small models there?

---

## 8. What comes next (inputs for `docs/PLAN-NEXT.md`)

Phase order proposed (each phase: snapshot → build → tests → README/PROGRESS):
1. **Stabilize** — fix all agent paths, pause Moondream/Screenpipe, archive old logs, `uv sync --reinstall`, Downloads permission, request timeouts.
2. **Monitor** — `/api/v1/health`, crash-loop guard, one log folder, System card, `make doctor` upgrades.
3. **Trim** — remove Moondream code/agent, business demo tools, telephony (if agreed); park gesture.
4. **On-demand supervisor** — `services.yaml` registry, start/stop/idle-timeout, memory caps.
5. **Local models** — Ollama provider for the brain, Whisper STT, Kokoro/Chatterbox TTS, Gemma 3 vision.
6. **Auth** — email + password + TOTP + backup codes + lockout (pattern from BookYourSlot/Cal.com).
7. **VPS split** — Tailscale, Ollama small models + gateway on the VPS, Mac for live voice/vision.
8. **Jobs v2** — dashboard approval → queue, Gmail status sync, pipeline charts, interview prep.
