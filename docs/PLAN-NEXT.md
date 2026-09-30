# Friday — Next Build Plan (v3) · for Claude Code

> Read first: `CLAUDE.md`, `docs/SYSTEM-REVIEW.md` (current state + decisions), then the phase you are asked to do.
> Rules that always apply: **no git commands** · `make snapshot` before each phase · files ≤ 200 lines ·
> tests in the same session (safety code = TDD) · `uv run ruff check .` and `uv run python -m pytest tests/unit -q`
> green before finishing · update `README.md` + `memory-bank/PROGRESS.md` after every phase · end with `/wrap`.
> Do ONE phase per session. Each phase lists its goal, work, acceptance checks and the session prompt to paste.

## Decisions locked with Lohith (2026-09-28)

- **Approvals:** a role is approved when Lohith clicks **Approve** on `/jobs` *or* says "approve" / "submit all" /
  numbers. Skip = never submitted. (Runbook + nightly task already updated.)
- **Removed:** Screenpipe (agent stopped, plist moved to `~/friday-snapshots/removed/`, 26 GB of recordings
  deleted). Replace later with on-demand screen reading (Phase 5).
- **Parked (not running, no UI):** gesture control, Content Studio panel.
- **Wanted voice behaviour:** "Hey Friday" → talks back. Then single, precise actions — "open Spotify and play my
  Liked Songs", "play Die With A Smile", "what are my meetings today", "what's the weather". **Never open every app
  on wake.**
- **Wanted content feature:** make a reel, name it, write the caption, and post it — with Lohith's OK before posting.
- **Local-first models** on the Mac; the Hostinger VPS for always-on/background work, reached only over Tailscale.
- **Login:** email + password + authenticator (TOTP) + backup codes. No Google sign-in.

---

## Phase 1 — Stabilize (fix what's broken)
**Goal:** every service that should run, runs; nothing crash-loops.
1. Delete launchd templates `launchd/com.friday.screenpipe.plist` and `launchd/com.friday.moondream.plist`
   (moondream is removed in Phase 3); unload `com.friday.moondream` on the Mac.
2. `make install-launchd` so every remaining agent points at `~/friday` (not `~/Friday`).
3. `uv sync --reinstall` (the venv console scripts still carry the old path).
4. Wake behaviour: set `WAKE_APPS_ENABLED=false` in `.env` (no apps/tabs on wake). Keep the `open_apps` tool.
5. Jobs API: give every jobs endpoint a hard timeout (a blocked `~/Downloads` read must return 503, not hang).
   Document the one-time macOS permission (Privacy & Security → Files and Folders → Downloads) in `docs/SETUP.md`.
6. Archive `~/Friday/data/logs` → `~/friday-snapshots/old-logs-2026-09-28.tar.gz`, then remove the folder
   (ask Lohith before deleting).
**Accept:** `launchctl print` shows dashboard, killswitch, metrics, logrotate healthy; voiceworker/livekit either
healthy or intentionally unloaded; `/jobs` loads data; unit suite green.
**Prompt:** `Do Phase 1 of docs/PLAN-NEXT.md. Snapshot first. Show me each launchd agent's state at the end.`

## Phase 2 — Monitoring & logs (professional baseline)
1. `GET /api/v1/health`: per-agent state, last exit code, restarts in the last hour, log sizes, disk free %,
   memory pressure, last nightly job run (from `~/Downloads/Jobs/_engine/state/progress_*.json`).
2. Crash-loop guard: `ThrottleInterval` in every plist; `scripts/watchdog` disables an agent after 5 failures in
   10 min and raises an alert (audit event + dashboard banner + macOS notification).
3. One log folder (`~/Library/Application Support/Friday/logs`), JSON lines (ts, level, module, event),
   rotation that runs hourly, 10 MB cap per file, 7 days kept.
4. Cockpit "System" card: green/amber/red from `/health`, read-only.
5. `make doctor` checks: repo path matches plists, `ui/build` exists, venv healthy, Downloads permission,
   Docker (only if voice-over-phone is on), disk free > 15 %.
**Accept:** break a plist path on purpose in a test → watchdog disables it and the card turns red.
**Prompt:** `Do Phase 2 of docs/PLAN-NEXT.md (TDD for the watchdog).`

## Phase 3 — Trim the codebase
Remove (code, settings, tests, docs, tools.yaml entries) — keep a snapshot:
- **Screenpipe:** `adapters/screenpipe.py`, its uses in `brain/nodes/vision.py`, `client/local_intents.py`,
  `scripts/healthcheck.py`, settings `screenpipe_*`, tests (`test_screenpipe.py` and references).
- **Moondream:** `scripts/moondream_serve.py`, `moondream_endpoint` setting and callers (vision falls back to
  "not available" until Phase 5). Ask before deleting `~/.moondream-station` (1.1 GB).
- **Business demo tools** in `tools.yaml`: `review_draft`, `lead_intake`, `vendor_report`, `maintenance_request`.
- **Telephony:** `make_call` + `adapters/telephony.py` (no provider configured).
- **Parked, not deleted:** `gesture/` (no agent, no cockpit panel); Content Studio panel removed from the cockpit,
  `integrations/content.py` kept for Phase 7.
- Replace `job_search` tool with `jobs_status` (reads the Jobs module: "how's my job search", "show my jobs" → opens
  `/jobs`).
- Update `test_ui.py` panel list, router eval set, and README feature list.
**Accept:** suite green; `rg -i "screenpipe|moondream|make_call"` finds nothing outside snapshots/docs history.
**Prompt:** `Do Phase 3 of docs/PLAN-NEXT.md. List every file you plan to delete and wait for my OK first.`

## Phase 4 — Voice commands that do exactly one thing
1. Wake: "Hey Friday" → greeting + listens; no apps opened.
2. Intent router (fast path in `client/local_intents.py` + LLM fallback) returns ONE action with arguments:
   `open_app(name)`, `spotify(play|pause|next|liked_songs|track, query)`, `calendar_today`, `calendar_event`,
   `weather`, `reminder`, `jobs_status`.
3. Spotify: add the **Spotify Web API** (search track/playlist, "Liked Songs", play on the Mac's device).
   Needs a Spotify developer app + OAuth refresh token in `.env`; playback control requires **Spotify Premium**.
   Fallback without Premium: `open spotify:search:<query>` and tell Lohith.
4. Calendar + weather answers spoken in one or two sentences.
5. Eval set: 40 utterances → exactly one correct tool call each (≥ 95 %).
**Accept:** "play Die With A Smile" plays that track; "play my liked songs" plays Liked Songs; nothing else opens.
**Prompt:** `Do Phase 4 of docs/PLAN-NEXT.md. Start with the eval set, then the router, then Spotify Web API.`

## Phase 5 — On-demand services + local models
1. `config/services.yaml` + `client/supervisor.py`: start on first use, health check, stop after idle
   (voice 5 min, vision 10 min), memory cap, one heavy model at a time, refuse to start under memory pressure.
2. launchd at login: only dashboard + killswitch + wake listener. Everything else via the supervisor.
3. Ollama provider (`LLM_PROVIDER=ollama`): Qwen3 8B (brain), Qwen3 1.7B (router); Claude optional fallback.
   `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE=5m`.
4. STT: Whisper large-v3-turbo (MLX). TTS: Kokoro (default) + Chatterbox (emotional), driven by the mood engine
   (`docs/EMOTIONS.md`). Original voice — never a cloned real person.
5. Vision replacement for Moondream/Screenpipe: "look at my screen" = one screenshot → Apple Vision OCR →
   Gemma 3 4B (Ollama) only if needed. Optional tiny activity log (front app + window title per minute).
**Accept:** idle RAM < 300 MB for Friday; a spoken turn starts replying < 2.5 s; `/health` shows what's loaded.
**Prompt:** `Do Phase 5 of docs/PLAN-NEXT.md in two sessions: 5a supervisor, 5b local models.`

## Phase 6 — Login (email + password + authenticator)
Argon2id password hash, TOTP (RFC 6238) with QR enrolment, 10 one-time backup codes, 5-attempt lockout with
back-off, HttpOnly/SameSite=Strict session cookie, CSRF token on every POST, audit of every login. Pattern from
BookYourSlot (Cal.com) — re-implemented in Python, not copied. Replaces the access-key gate.
**Accept:** full login/lockout/backup-code tests (TDD); `/jobs` Approve requires a fresh session.

## Phase 7 — Reels: make, name, caption, post
1. `/studio` page: pick clips (or a finished video), Friday suggests title + caption + hashtags (in Lohith's voice),
   he edits, **approves**, then it posts.
2. Posting via the Instagram Graph API (Business/Creator account) through n8n (existing publish webhook) — or Postiz
   if preferred. Nothing posts without the approve click or "post it".
3. Voice: "make a reel from today's clips, call it X" → draft appears on `/studio` for approval.
**Needs from Lohith:** which Instagram account, and whether it's a Business/Creator account.

## Phase 8 — VPS split (Hostinger KVM 4)
Tailscale on the VPS; Ollama bound to the tailnet only (never public); small models + embeddings there; the
public `friday.paypilotlabs.com` gateway behind Phase-6 login; the Mac stays the fast path for voice/vision/Chrome.

## Phase 9 — Jobs v2
Daily 11 AM "submit run" for approved roles (incl. ones that need an emailed code); Gmail status sync into the
pipeline; charts (applied → reply → interview); interview-prep notes per company.
