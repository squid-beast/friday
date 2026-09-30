# Phase 1 — Code cleanup + integrations

> **Goal:** stabilize and de-drift the existing codebase and wire the integrations cleanly, so
> every later phase builds on solid ground. **No new features in this phase.**
> Guardrails: files ≤200 lines · tests in the same session · `make lint && make test` green ·
> end with `/wrap` + `make snapshot`.

---

## Part A — Code cleanup (concrete targets found in the repo)

### A1. Split files over the 200-line rule
The ≤200-line rule (`CLAUDE.md`) is currently violated by these files — split each into cohesive
modules (same public interface, no behavior change):

| File | Lines | Suggested split |
|---|---|---|
| `integrations/api.py` | 318 | route groups → `api_voice.py` / `api_metrics.py` / `api_content.py`, or a small `integrations/api/` package |
| `integrations/server.py` | 245 | keep the ASGI app; move auth-gate + static serving into helpers |
| `tests/unit/test_api_v1.py` | 306 | split by route group to mirror the source split |
| `tests/unit/test_gesture.py` | 215 | split by G-level (G0–G3) |
| `tests/unit/test_nodes.py` | 206 | split by node (chat/vault/ops/vision) |
| `tests/unit/test_agent.py` | 202 | split voice-agent vs barge-in cases |

Rule: split for cohesion, not just to duck the line count. Interfaces stay identical; tests stay green.

### A2. Resolve `config/tools.yaml` TODO placeholders
The commented capability blocks carry `/webhook/TODO` placeholders. Either fill real webhook paths
(when the n8n workflow exists — that's Phase 4) or delete the dead commented blocks so the file only
declares live tools. Keep the risk policy comments at the top.

### A3. Kill the Jarvis ↔ Friday naming drift
The product is **Friday**, but "jarvis" is scattered across launchd labels (`com.jarvis.*`),
`config/settings.py`, `brain/nodes/*`, tests, and docs. Decide and document one policy in
`memory-bank/DECISIONS.md`:
- **Recommended:** keep the `com.jarvis.*` **launchd label IDs** frozen (renaming them means
  reinstalling all 8 agents and updating every `launchctl kickstart` reference — risk with no user
  benefit), but make **every user-facing string, comment, and doc** say "Friday".
- Whatever you choose, apply it consistently and note it so future sessions stop re-introducing the
  other name.

### A4. Sync `.env.example` with `config/settings.py` (the config contract)
`.env.example` is stale — **~26 settings fields are undocumented in it**, including:
`app_access_key`, `mood_path`, `reminders_path`, `wake_verifier_path`, `wake_verifier_threshold`,
`wake_require_verifier`, `weather_city`, `assistant_name`, `wake_phrase_text`,
`stand_down_phrase_text`, the `*_db_path` set, `vision_snaps_*`, and the `gesture_*` files.
`.env.example` is the onboarding contract — every settable field belongs there with a one-line
comment (secrets blank).

### A5. Lint, tests, coverage, git policy
- `make lint` (ruff) clean; `make test` (L1) + `make test-integration` (L2) + `make eval` (router
  ≥90%) green; check the existing `.coverage` and note the current number in `PROGRESS.md`.
- **Git policy:** the repo already has a remote (`squid-beast/friday`). Make it **private**, update
  `CLAUDE.md` + `PLAN.md §0` to say "private GitHub remote allowed; secrets never committed", and
  confirm `.gitignore` still excludes `.env*`, `data/`, build output (it does). Rotate any key that
  ever landed in a commit.

---

## Part B — Integrations audit

### B1. Inventory the `integrations/` package
Confirm each module is wired, tested, healthchecked, and documented:
`api.py`, `server.py`, `ask.py` (phone text bridge), `automations.py`, `collect.py`, `content.py`
(Content Studio), `jarvis_health.py`, `metrics_voice.py`, `n8n_pull.py`, `reminders.py`, `store.py`.
For each: does `make doctor` cover it? Is there a test? Is it referenced by a launchd agent or a
`tools.yaml`/route entry, or is it dead? Delete or document anything orphaned.

### B2. launchd agents
`make install-launchd` must be idempotent and install all 8 agents
(`dashboard · killswitch · voiceworker · moondream · screenpipe · livekit · metrics · logrotate`).
Confirm each `.plist` label matches what `README §4` documents for `launchctl kickstart`.

### B3. Adapter contract consistency
Every adapter used as a tool follows `async fn(arg: str, utterance: str) -> str` (CONVENTIONS).
Spot-check `adapters/*.py` for drift; vendor SDKs stay inside `adapters/` and `integrations/` only.

### B4. Front-end + healthcheck
`make ui` builds clean into `ui/build`; `make doctor` reports **all clear** (or a truthful list of
dark services). The dashboard header still tells the truth (active wake phrase, voice-lock scope).

---

## Acceptance (Phase 1 done when all true)
- No non-test file over 200 lines; oversized test files split too.
- `make lint && make test && make test-integration && make eval` all green.
- `make doctor` = all clear.
- `.env.example` documents every `settings.py` field; secrets blank.
- Naming policy decided + applied to user-facing strings/docs; recorded in `DECISIONS.md`.
- `tools.yaml` has no `TODO` placeholders (filled or removed).
- GitHub repo private; git policy reconciled in `CLAUDE.md`/`PLAN.md`.
- **Zero new features added.** Then `/wrap` + `make snapshot`.
