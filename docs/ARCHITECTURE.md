# FRIDAY — Official Architecture

The system as built and enforced (2026-08-19): 464 L1 unit + 11 L2 integration
+ 4 L4 scenario tests, a 33-case L3 router eval, lint under the official rule
set. Every claim below is backed by a test file named in the tables.

## 1 · The shape — ports and adapters around one brain

```
 mic/phone/API ──▶ SURFACES ──▶ BRAIN (LangGraph) ──▶ ADAPTERS ──▶ world
 voice/, ui/,      integrations/  brain/ (routing,     adapters/    (Anthropic,
 killswitch        server+api     gates, memory)       one file     n8n, EventKit,
                                                       per vendor   camera, ...)
```

One rule per layer, each machine-enforced:
- **adapters/** — the ONLY place vendor SDKs may be imported. One file per
  vendor; swap a vendor = replace one file, same signature.
- **brain/** — pure orchestration: pydantic state, async nodes with injectable
  adapter deps, interrupt-based gates. Nodes never raise; failures become
  in-persona apologies. New capability ≠ graph edit.
- **config/tools.yaml** — the ONLY place capabilities are declared
  (`name/description/adapter/webhook_path/risk`). Risk ladder:
  `safe | confirm | pin | blocked`.
- **integrations/** — the HTTP shell (gate, /api/v1, SvelteKit build serving)
  + platform collectors. Network code allowed here and in adapters only.
  The shell is split by concern: `server.py` (routing) + `access.py` (key
  gate) + `static_files.py` (contained file serving); endpoints live in
  route-group modules that export `GET_API`/`POST_API` and self-register —
  `api.py` (status/agenda/metrics/voice/daemon), `api_hud.py`,
  `api_devices.py` (Obsidian/gesture/snaps), `api_studio.py` (parked),
  `api_conversation.py` (recent turns, read-only from the checkpoint store),
  `jobs_api.py`. /api/v1/* only (unversioned aliases removed 2026-09-29). New route group =
  new module + one entry in server.py's registration loop.
- **Sanctioned vendor imports outside adapters/** (audited 2026-09-29, no
  drift): `voice/` uses the `livekit.agents` framework (CONVENTIONS);
  `gesture/actuator.py` Quartz (native Mac control); `client/killswitch.py`
  rumps/pynput (menu bar); `scripts/` tooling (httpx doctor, sounddevice
  recorders, openwakeword trainer). `brain/` imports none.
- **client/ + audit/** — the kill path: ZERO network imports
  (subprocess-proven), control-file IPC, append-only audit.
- **ui/** — SvelteKit SPA, built locally, served same-origin; tokens-only
  design system, computed-WCAG enforced.

## 2 · Feature map — every feature, its modules, its test cases

| Feature | Modules | Test cases |
|---|---|---|
| Routing (utterance → node) | brain/graph.py, brain/nodes/router.py (echoed tool name ⇒ ops) | test_router, test_graph, evals/router_cases.yaml (44 vs real model, ≥90%), evals/tool_cases.yaml + test_tool_eval (tool selection, every tool covered, ≥90%) |
| Conversation + persona | brain/nodes/chat.py, config/persona.md | test_nodes (16), test_agent (12) |
| Multi-provider LLM | adapters/llm.py (dispatch, per-loop client cache), adapters/llm_openai.py (openai/openrouter/gemini/compatible), config/providers.py (active keys for status + doctor) | test_llm, test_llm_providers (11 — base_url per provider, compat key, Claude ids refused) |
| Mood engine | brain/mood.py (5 dims, 6h decay, real triggers), brain/mood_sense.py (audit + calendar + fresh facts) | test_mood (14 — kills reset, declines ignored, word-bounded facts) |
| Emotional voice | voice/emotion.py (pure `style_for`, safety gate), voice/styling.py (line kinds, hold/release), adapters/tts.py (cartesia/openai/fishaudio) | test_emotion (7, TDD gate), test_styling (10), test_adapters |
| Buddy tools | adapters/vault_plan.py (today_plan), adapters/mac_actions.py (open_and_search), integrations/day_summary.py (send_summary → Friday-owned n8n) | test_buddy_actions (9), test_buddy_proactive |
| Proactive check-ins | scripts/proactive_checkin.py, brain/checkin.py, brain/pending_question.py, launchd/com.friday.checkin.plist | test_buddy_proactive (11), test_checkin |
| Only-my-voice (mic only) | voice/owner_lock.py (per-turn gate in llm_node), adapters/voiceprint.py (CAM++ ONNX), voice/session.py (wake privacy, preemptive off), scripts/enroll_voice.py | test_owner_lock (11, TDD), test_voiceprint (6, skipped without model), test_session (6), test_status_api (three-state lock) |
| Vault brain (his notes) | adapters/vault.py, brain/nodes/vault.py | test_vault_allowlist (11 — escapes/symlinks refused), test_nodes |
| Long-term memory | adapters/memory.py, brain/nodes/memory_writer.py | test_memory, test_nodes (extraction gate cases) |
| Ops + spoken gates | brain/nodes/ops.py, brain/confirm.py, adapters/n8n.py, config/tools.py | test_ops_node (10), test_confirm_gate (8), test_pin_gate (9), test_tools_registry (5), L2 n8n contract (9), L4 registry_risks |
| Camera sight (PARKED — lens never opens without a listening model) | adapters/camera.py (`_eyes_up` probe, imagesnap+Moondream) | test_camera (TDD safety), test_vision_nodes |
| Screen recall (DISARMED — route lands on `unarmed`) | adapters/screenpipe.py (parked) | test_screenpipe, test_graph |
| Web hands | adapters/browser.py | test_browser_adapter, test_vision_browser |
| Calendar | adapters/calendar.py (EventKit) | test_calendar (8 — refuses to guess times) |
| Voice-local tools | integrations/jobs_voice.py (jobs_status), adapters/vault.py `open_tool` (open_obsidian), adapters/apps.py (open_apps, wake switch decoupled) | test_voice_tools, test_wake_apps |
| HUD automations (read-only n8n) | integrations/automations.py (per-workflow latest, local time, errors shown), integrations/api_hud.py (60s memo) | test_hud, test_hud_cache |
| Voice pipeline | voice/agent.py, adapters/{stt,tts,llm,wakeword}.py | test_agent, test_wakeword (8), test_adapters (14), test_watchdog |
| Kill path (offline) | client/daemon.py, client/local_intents.py, client/killswitch.py | test_daemon (9), test_daemon_process (no-network proof), test_local_intents, test_killswitch, test_cuts (6) |
| Morning brief | brain/brief.py | test_brief (7 — every failure still greets) |
| Audit trail | audit/log.py | test_audit (6), L4 demo asserts rows |
| Access gate | integrations/server.py `_gate` | test_app_gate (6, TDD red-first) |
| API v1 + SPA serving | integrations/{server,access,static_files,api,api_hud,api_devices,api_studio,api_conversation}.py | test_api_v1 + test_api_v1_devices (positive/negative/adversarial), test_conversation_recent, test_dashboard_server (10), test_voice_server (7), test_status_api |
| Content Studio | integrations/content.py | test_content (9 — dedupe, two-tap, audit row) |
| Metrics board | integrations/{store,collect,n8n_pull,friday_health,metrics_voice}.py | test_metrics_store, test_collectors (7), test_collect_run, test_metrics_voice (zero-LLM digest) |
| Phone bridge | integrations/ask.py | test_ask_bridge (7 — kill phrases pre-graph) |
| Resilience + doctor | every node's failure branch, scripts/healthcheck.py | test_fallbacks (10), test_healthcheck, test_healthcheck_n8n (active POST paths, pagination) |
| UI design system | ui/src (14 files) | test_ui (12 — tokens, computed WCAG, 44px, a11y, zero-external, Svelte contracts) |
| Auto-start | launchd/com.friday.*.plist (5 core incl. checkin) + launchd/on-demand/<group>/ (phone: `make phone-voice[-off]`; tunnel: `make tunnel[-off]`), scripts/install_launchd.sh | test_launchd (per-plist parse, KeepAlive law), test_install_launchd (real script, fake HOME + stub launchctl) |
| Safety net | scripts/snapshot.sh, config/settings.py, .gitignore (biometrics + wake samples never committed) | test_snapshot (rm-escape regression), test_settings, test_gitignore |
| Public deploy | docs/DEPLOY.md, launchd/on-demand/tunnel/com.friday.tunnel.plist (Cloudflare Tunnel + Access) | test_launchd (tunnel plist parses) |
| THE DEMO | all of the above | scenario/test_demo_script (steps 2–7, one thread, gate mid-demo) |

## 3 · Official coding standards (enforced, not aspirational)

**Python 3.12** — `make lint` gates on ruff with the official set:
`E,W` (PEP 8), `F` (pyflakes), `I` (import order, PEP 8), `N` (pep8-naming),
`UP` (modern 3.12 idioms), `B` (bugbear), `SIM`, `RUF`. Line length 100.
Additionally: type hints everywhere; **pydantic models at every boundary**
(state, tools, settings, metrics); async for all I/O paths; files ≤ 200
lines; one concern per file; module docstrings state purpose + contract;
secrets only via config/settings.py (.env, no inline comments); every tool
execution goes through audit/log.py.

**JavaScript / Svelte 5** — ES modules only; runes (`$state/$derived/$props`);
single-responsibility components; the API client is the one fetch site;
colors only via app.css `:root` tokens; transitions via Svelte primitives;
heavy deps (livekit) dynamically imported. npm is build-time only — the
runtime loads zero external resources.

**Config** — YAML for registries (tools, metrics): adding a capability is a
data change, never a code change. `.env` is the single secrets file.

## 4 · Testing standard (docs/TESTING.md is the law)

- Pyramid: **L1 unit** (mocked, <30s, every change) → **L2 integration**
  (real sqlite/chroma, fake LLM) → **L3 evals** (router ≥90% vs real model)
  → **L4 scenario** (the demo, rehearsed by machine).
- Tests ship in the SAME session as the code. Safety code (gates, kill
  switches, allowlists, the access wall) is TDD — failing test first.
- Router/prompt edits require the eval set updated in the same session.
- Never skip/delete a failing test to pass a phase.
- Coverage 93% with every logic/fallback branch covered; live-only
  exclusions are named and sanctioned in docs/TESTING.md.

## 5 · How to extend (the recipes)

- **New capability**: one `async fn(arg, utterance) -> str` in adapters/ (or
  an n8n workflow + `adapters.n8n:run`) + one tools.yaml block with a risk
  level + tests for the adapter. The router, gates, and audit apply for free.
- **New screen**: one `ui/src/routes/<name>/+page.svelte` + nav entry in
  +layout.svelte + `make ui`; test_ui's laws apply automatically.
- **New endpoint**: function in integrations/api.py + one line in server.py's
  v1 route table + cases in test_api_v1.py (positive, negative, adversarial).
- **Swap a vendor**: replace its one adapters/ file, same signature; suite
  proves nothing else moved.

## 6 · Enforcement — what breaks if you cheat

Vendor import outside adapters/ → review + adapter tests fail · stray color
→ test_ui fails · missing 44px/aria → test_ui fails · unregistered tool →
ops refuses (registry is truth) · ungated risky tool → L4 registry_risks
fails · network import in the kill path → test_daemon_process fails ·
traversal in asset serving → test_api_v1 adversarial cases fail · lint
violation → make lint fails. The demo test rehearses the whole story on one
thread before sir ever speaks it.
