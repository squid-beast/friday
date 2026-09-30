# CONVENTIONS

## Code
- Python 3.12, uv, ruff. Type hints everywhere. pydantic models at all boundaries.
- Files <= 200 lines. One class/concern per file.
- Async for I/O paths (voice pipeline, adapters). No blocking calls in graph nodes.

## How to add a capability (the ONLY way)
1. Write one adapter function: `async fn(arg: str, utterance: str) -> str` (arg = the
   tool's webhook_path, may be ""; utterance = what sir said). Vendor SDKs allowed in
   adapters/ and integrations/ only.
2. Register it in config/tools.yaml: name, description (router + selector read this),
   adapter "module:function", risk (safe|confirm|pin|blocked).
3. Done. ops node discovers it from YAML. graph.py is never edited for new tools.
   Proof: calendar + spoken metrics landed in D2 with zero graph edits.

## Integrations (Phase D)
- integrations/ = platform metric collectors + the local dashboard. Same one-file-per-
  platform discipline as adapters/; network code allowed here only.
- Platform credentials NEVER land on the Mac: n8n holds them and exposes metrics
  webhooks; the Mac pulls (config/metrics.yaml). Adding a platform = n8n workflow +
  one YAML line, no code.
- The dashboard binds to 127.0.0.1 only. Voice-side access to metrics goes through a
  normal tools.yaml entry (Phase D2), never a new route.

## How to swap a vendor
Replace the single file in adapters/ keeping the same interface signature. Nothing else changes.

## Adapter pattern (established Phase 1)
- Each adapter exposes get_*() factories returning configured components (LiveKit plugin objects
  for the voice pipeline); voice/ and client/ import adapters + livekit.agents framework only,
  never livekit.plugins.* or vendor SDKs directly.
- Factories raise ValueError on missing keys; config/settings.py never raises.
- scripts/ run as modules from repo root: `uv run python -m scripts.healthcheck`.

## Brain/node pattern (established Phase 2)
- Nodes are async functions of FridayState with adapter deps as keyword args defaulting to
  the real adapters; tests pass fakes from tests/fakes.py (FakeLLM is scripted and fails
  loudly when over-asked). build_graph(checkpointer, *, think, search, ...) binds overrides.
- Nodes never raise: every adapter failure becomes an in-persona apology line in `reply`.
- State helpers live in brain/state.py (assistant_reply, last_user); persona() in nodes/chat.py.
- Unarmed routes reply from graph.py's _unarmed_node — do NOT stub future nodes early.

## Kill-path pattern (established Phase 3)
- Kill/capture code (client/, audit/) must import ZERO network stacks — enforced by a
  subprocess import test (test_daemon_process.py). Never add a network import there.
- Daemon deps are injected callables (spawn/listen/chime/audit) — threading tests use
  fakes + wait_until, poll_s=0.01. Wrappers (_listen_safe/_audit_safe) guarantee a dead
  mic or full disk degrades, never crashes the daemon.
- Transcripts hit client/local_intents.match BEFORE any graph/LLM dispatch.
- The public daemon state must be truthful: flip it only after the fact it reports.

## Interrupt pattern (established Phase 4)
- Any node that interrupts must be REPLAY-SAFE: everything before the interrupt() call is
  deterministic (state lookups only). LLM calls happen in a PRIOR node that persists its
  result in state (see ops_select → pending_tool → ops_execute).
- The voice agent resumes a parked gate with Command(resume=<utterance>); local kill
  intents are checked before resume, and a fresh topic abandons the gate safely.

## Memory discipline
- Project memory: memory-bank/*.md — updated ONLY via /wrap at session end.
- Runtime memory: Friday's own (vault + mem0) — code never writes to memory-bank.

## Testing (full rules: docs/TESTING.md — mandatory)
- Pyramid: L1 unit (mocked, <5s, every change) -> L2 integration (real sqlite/chroma, fake LLM)
  -> L3 evals (router >=90%, persona rubric) -> L4 scenario (demo steps scripted, kill path offline).
- L4 lives in tests/scenario/ (`make test-scenario`) and mirrors docs/DEMO-SCRIPT.md; if the
  demo script changes, the scenario test changes in the same session.
- Tests written in the SAME session as the code. Safety code is TDD (test first).
- Prompt/router edits = update tests/evals/router_cases.yaml in the same session.
- make test-unit before /wrap; test-integration + eval before phase completion.

## LLM call discipline (2026-08-11)
- All Anthropic calls go through adapters/llm.py think(); new call sites pass
  max_tokens when the output is structurally short (classifier = 16).
- A per-turn background LLM call needs a cheap deterministic gate in front of it
  (pattern: memory_writer's _FACT_HINT). Gates err permissive.

## README discipline (2026-08-20, Lohith's standing instruction)
- After completing ANY task, update README.md (status table, checklist, commands)
  as part of "done" — not a separate step. It's his single source of truth.

## UI truthfulness (2026-08-30)
- The main dashboard is passive and voice-first. Avoid adding button-led controls
  unless Lohith explicitly asks for them back.
- If the configured identity and the active runtime state can differ, surface BOTH.
  Example: desired wake phrase = `Hey Friday`, active fallback = `Hey Jarvis` until
  the custom model exists. The UI/API must report the real armed state, not the wish.
- Voice-lock language must stay precise: current scope is `wake-only` unless full
  per-utterance speaker verification is actually implemented.

## Naming (2026-09-29, Lohith's call)
- The product, packages, identifiers, labels (`com.friday.*`), paths and docs are
  **Friday**. Never introduce "jarvis" in new code or docs.
- Sole exception: the literal "Hey Jarvis" where it names the bundled fallback
  wake model that is really armed (UI truthfulness). Remove it once the custom
  "Hey Friday" model is trained.

## HTTP shell pattern (2026-09-29)
- Endpoints live in route-group modules (`integrations/api*.py`, `jobs_api.py`)
  that export `GET_API`/`POST_API` dicts; server.py registers them in one loop.
  A new endpoint group = a new module, never a growing api.py.
- Request-handler concerns are mixins: `access.AccessGate` (key wall),
  `static_files.StaticFiles` (contained serving). server.py only routes.
- API tests use `tests/api_harness.py` helpers + the `served` fixture in
  tests/unit/conftest.py.

## n8n + tools (2026-09-29)
- Friday may call ONLY Friday-owned n8n workflows: POST webhook + headerAuth
  `X-Friday-Secret`. Business/client workflows are never edited, activated, called,
  or targeted by a tool. `make doctor` enforces "registered path = active POST".
- Every tools.yaml change updates tests/evals/tool_cases.yaml (every tool covered)
  and, if routing wording changes, router_cases.yaml — run `make eval` (both >=90%).
- Local-first: a capability that reads local data (jobs, notes, calendar) is a
  local tool, not an n8n round-trip.
