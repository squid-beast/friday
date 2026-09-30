# PROGRESS

## Current phase
Phases 1–7 + D1 + D2 + G0–G3 + Friday Phase A/B code + tests COMPLETE. Friday is
now the active product identity in the persona, dashboard, run book, wake-recording
scripts, and status API. Remaining: Lohith's strict-owner wake recordings/training +
live acceptance runs -> DEMO-SCRIPT clean takes = v1 DONE.

## Friday rename + strict wake-only voice lock + passive dashboard (2026-08-30)
- Product identity is now Friday across the visible system: persona, dashboard title,
  dashboard header, run book, mobile/setup/demo docs, and the open-apps tool copy.
  Internal module/class names stay Jarvis for stability; user-facing behavior says Friday.
- The dashboard is now one passive voice-first screen: no tabs, no composer, no
  buttons, no click-to-expand automations, no Obsidian-launch controls. The header
  tells the truth about daemon state, active wake phrase, stand-down phrase, and
  voice-lock scope (`wake-only`).
- Strict owner-only wake is scaffolded and documented. New settings:
  `WAKE_VERIFIER_PATH`, `WAKE_VERIFIER_THRESHOLD`, `WAKE_REQUIRE_VERIFIER`.
  New scripts: `scripts/record_voice_verifier.py` and `scripts/train_voice_verifier.py`.
  The wake path fails closed if strict mode is on without a verifier path.
- IMPORTANT truth preserved in code + docs: until Lohith trains a custom wake model,
  the active wake phrase is still the bundled fallback "Hey Jarvis". Once the model
  exists, the header/API switch to "Hey Friday". The strict verifier currently guards
  the wake phrase only; full per-utterance speaker verification is NOT built yet.
- Build/run hygiene tightened: `make ui` is PHONY now, so it actually rebuilds the
  SvelteKit app instead of silently no-op'ing when the `ui/` directory exists.
- Verification: `make lint` green, targeted Friday suite 123 tests green, full
  `make test` green (554 passed), and the production UI rebuilt successfully.

## LLM cost optimization (2026-08-11)
- Anthropic key OBTAINED (not yet in .env — doctor still warns until pasted).
- memory_writer now gates the per-turn Haiku extraction behind a permissive
  fact-hint regex (digits/"remember"/"i like"...) — fact-free turns make 2 calls
  (route+reply), not 3. think() max_tokens default 512, router capped at 16.
- Prompt caching deliberately NOT added: persona ~450 tokens < Anthropic's 1024
  (Sonnet) / 4096 (Haiku) cacheable minimum — cache_control would silently no-op.
- docs/SETUP.md: Stage 1a marked obtained + new "Cost & call budget" section
  (per-turn anatomy, ~$12–15/mo at 100 turns/day, knobs = MODEL_* in .env).
- 425 unit + 11 integration tests green; lint green.

## Everything-view board + assistant capabilities (2026-08-11)
- Board "/" now shows the whole system: /api/status (config-only flags, instant)
  -> systems chips (✓/—) + NOW card (next event, studio queue, last activity) +
  metric cards. 3 new files-worth of tests; strict UI suite still green; 434 unit.
- REAL BUG the new UI caught: .env inline comments parsed as VALUES (pin chip
  lied armed, voice JWTs would sign with a comment). Both env files rewritten,
  comments on own lines. .env format rule logged in DECISIONS.
- Lohith rewrote persona.md live (wit + emotions; hard rules intact). Tests
  re-pinned to invariants. NOTE: persona references docs/EMOTIONS.md mood engine
  that doesn't exist — roleplay-only until someone builds it.
- Lohith's capability ask (job search, leads, drafts, calls) registered as
  commented tools.yaml blocks w/ risk ladder (safe/confirm/pin) + SETUP Stage 4
  list. Each = one n8n workflow + uncomment; zero code. Stale adapters.n8n:call
  in the template fixed to :run.

## Access gate + open-world prep (2026-08-11, Lohith's call)
- Server gained a TDD'd APP_ACCESS_KEY wall (6 new tests, red-first): 401 without
  the key on every route incl. /api/ask; one-time ?key= -> HttpOnly cookie (303 +
  clean URL); Authorization Bearer for APIs; hmac.compare_digest; unset key =
  old open behavior. Key set in .env (openssl rand -hex 16). Verified live:
  401/303/200 locally AND over the tailnet URL. 431 unit + 11 integration green.
- REAL BUG found by Stage 5: all suites depended on no .env existing — fixed
  root-cause with tests/conftest.py (Settings env_file=None for tests).
- OPEN WORLD LIVE (2026-08-11): Lohith enabled HTTPS certs -> cert minted ->
  `tailscale funnel --bg 8787` up. Verified THROUGH THE PUBLIC INGRESS
  (209.177.145.192, via 8.8.8.8 DNS): no key = 401, key = 200. Public URL:
  https://lohiths-macbook-pro.tail8d7575.ts.net (first-visit ?key= from .env).
  Voice tab stays tailnet-only by design (UDP media can't ride funnel).
  NOTE: app server runs under the dev session — `make install-launchd` to
  make the public URL survive reboots/sessions.

## Tailnet serve LIVE (2026-08-11)
- All three tailscale serve listeners up: 443 + plain-http 80 -> :8787 (app),
  8443 -> :7880 (voice signalling). .env voice lines written (BIND/NODE_IP =
  100.118.41.0, VOICE_WS_URL = wss://lohiths-macbook-pro.tail8d7575.ts.net:8443).
- Verified: HTTP 200 + live /api/today over http://lohiths-macbook-pro.tail8d7575.ts.net.
- OPEN: Let's Encrypt cert mint fails ("acme order status: invalid") -> https
  URLs dark; Lohith must check login.tailscale.com -> DNS -> HTTPS Certificates,
  then `tailscale cert lohiths-macbook-pro.tail8d7575.ts.net`. Voice tab needs https.
- iPhone side pending: Tailscale toggle ON (offline 14d) + Add to Home Screen.

## FIRST LIVE CONVERSATION (2026-08-11)
- `make dashboard` run live in-browser: board renders, `make collect` filled the
  Jarvis card (calendar collector needs Lohith's one-time macOS permission).
- Chat tab: real end-to-end turn through BrainBridge -> real Haiku route -> real
  Sonnet reply, in persona. The brain is verified live. Anthropic + Deepgram keys
  in .env; Cartesia is the last Stage 1 item before `make voice`.

## Phase 7 — Phone (built 2026-08-10, pulled forward by Lohith)
- integrations/ask.py BrainBridge: phone text -> same brain (kill phrases first,
  interrupt->pending->resume over HTTP, thread "phone"); server routes /chat + /api/ask
  + manifest; chat.html PWA; com.jarvis.dashboard launchd agent (5 agents total).
- Tailnet ALREADY LIVE (Mac 100.118.41.0, iPhone, Hostinger VPS). Lohith:
  `tailscale serve --bg 8787`, toggle phone Tailscale on, Add to Home Screen
  (docs/PHONE.md). P7 accept: board + chat + gated tool + "stand down" from cellular.
- Coverage audit: 93%, every logic/fallback branch covered (new test_fallbacks.py,
  registry-risk L4, daemon crash-survival, camera timeout, recorder resume, tracing).
  Policy + sanctioned live-only exclusions documented in docs/TESTING.md.
- 371 tests total: 356 L1 unit, 11 L2 integration, 4 L4 scenario, 33-case L3 eval.

## Phase 7.6 — Voice from the phone (built 2026-08-11)
- /voice (5th tab): orbit + CONNECT pill (the reference's "enter with sound" moment);
  vendored livekit-client 2.21.0 served from /static/ (zero-external-resources holds).
- /api/voice-token: JWT scoped to room "phone"/identity sir-phone; 400 until configured.
- Transport: page+signalling via tailscale serve WSS (:8443 -> 7880); media direct
  over tailnet (compose LIVEKIT_BIND_IP + --node-ip, defaults loopback-only).
- Lohith setup (docs/PHONE.md): 3 .env lines, the 8443 serve listener, make run,
  phone mic permission. Live WebRTC acceptance is his — everything testable is tested
  (420 unit + 11 integration + 4 scenario; token grants decoded and asserted).

## Phase 7.5 — App Screens + Content Studio (built 2026-08-11, Lohith's scope)
- Four screens, one bottom nav: Board / Chat / Studio / Today (nav consistency is a
  tested invariant). Today = calendar + Jarvis activity with honest permission hints.
- Content Studio: n8n trending pull -> review cards (score/source chips, hook,
  editable caption) -> two-tap POST -> n8n publishes to Instagram -> item posted +
  ig_publish audit row. SKIP removes. Dedupe by id; reviewed items never resurface.
  IG creds stay in n8n. integrations/content.py + api.py; server = route tables.
- Lohith input: build the 2 n8n workflows + set CONTENT_TRENDING_WEBHOOK /
  CONTENT_PUBLISH_WEBHOOK (contracts in docs/CONTENT-STUDIO.md).
- 409 unit + 11 integration + 4 scenario tests; strict UI suite covers all 4 pages
  (identical tokens, computed WCAG, 44px targets, nav, zero external resources).
- Verified live: Studio cards + two-tap confirm + Today empty-states, phone viewport.

## UI pass (2026-08-10, after P7)
- Mission Board + chat restyled to the daoism.systems language (Lohith's reference):
  mono/tracking, LED-matrix texture, hairline cards with crosshair corners, numbered
  ◆ chips, ruler bars, brick-red accent. Verified live in-browser, desktop + mobile.
- STRICT UI suite (tests/unit/test_ui.py, 26 checks): token-only colors, identical
  token set across pages, computed WCAG contrast (AAA body/AA secondary), 44px touch
  targets, safe-area/dvh, aria, installable PWA, zero external resources.
- Real bug found by live verification: chromadb/onnxruntime segfault when the brain
  lazy-booted in a request thread → BrainBridge now boots main-thread at server start
  (regression-tested). 380 unit tests total now.

## Phase D2 — Calendar + spoken metrics (built 2026-08-10)
- adapters/calendar.py: EventKit (lazy imports); events_today; create_from_speech (Haiku
  parses title/time from the utterance; refuses without a clear date+time). Google events
  covered by adding the account to Calendar.app. First use = macOS permission prompt.
- tools.yaml is LIVE with three local entries: calendar_today (safe), calendar_event
  (confirm — spoken yes required to book), metrics_report (safe, reads the Mission Board
  aloud via a deterministic no-LLM digest). Zero graph edits — the adapter pattern held.
- Tool contract now fn(arg, utterance); n8n tools use adapters.n8n:run (utterance as
  payload). Morning brief leads with the first event; board gains a calendar card.
- Eval set 33 cases; 324 unit tests; docs/CALENDAR.md has the setup + voice examples.

## Phase D1 — Mission Board (added by Lohith 2026-08-10, built same day)
- integrations/: metrics store (data/metrics.db), jarvis_health collector (zero creds),
  generic n8n_pull (creds stay in n8n; config/metrics.yaml lists metric webhooks),
  collect runner, dashboard server + page. `make collect` / `make dashboard` ->
  http://127.0.0.1:8787 (localhost ONLY). Hourly launchd timer com.jarvis.metrics.
- Board: card per platform (instagram/bookyourslot/leads/n8n/jarvis), latest + delta +
  14-day sparklines, 60s auto-refresh. Verified visually against seeded sample data.
- Lohith input: build the 4 n8n metrics workflows (table in docs/DASHBOARD.md) and
  uncomment their paths in config/metrics.yaml. Jarvis's own card works today.
- 309 unit tests total; store/collectors/server all covered.

## What works
- Everything from Phases 1–5 plus:
- Spoken PIN gate for risk=pin tools: exact digit-string match (word-digits normalized,
  "four two four two" = 4242), negation vetoes, an eager "yes" is NOT a PIN, unset
  JARVIS_PIN locks the tool shut without even asking, digits never reach the audit log.
- Morning brief: first wake of the day (audit "brief" marker = once-only, restart-safe),
  date + remembered facts -> <=3 persona sentences; every failure path still greets.
- launchd auto-start: launchd/*.plist (killswitch KeepAlive w/ healthcheck-first,
  screenpipe KeepAlive, livekit retry-until-Docker-up) + `make install-launchd`
  (idempotent, --uninstall supported). Reboot -> everything up with zero terminal.
- Doctor: `make doctor` now also checks screenpipe/moondream/chroma/n8n (n8n skipped
  until configured); `--quick` warns on dark eye services.
- LangSmith tracing armed automatically iff LANGSMITH_API_KEY is set (opt-in, no-op else).
- Eval set at 30 cases (>=90% gate); L4 scenario test rehearses DEMO-SCRIPT steps 2–7
  through the real graph on one thread (`make test-scenario`).
- Tests: lint green; 293 L1 unit; 9 L2 integration; 1 L4 scenario; 30-case L3 eval.

## Next step
Lohith: complete Friday's owner-only wake path, then do live acceptance:
1. Record the 50 `Hey Friday` clips + 25 owner negative clips.
2. Train `voice/wakeword/wake.onnx` + `voice/wakeword/owner.joblib`.
3. Set `WAKE_MODEL_PATH`, `WAKE_VERIFIER_PATH`, `WAKE_REQUIRE_VERIFIER=true`.
4. Restart the voice worker / killswitch and confirm the dashboard header flips
   from `Hey Jarvis` fallback to `Hey Friday`, with `Voice lock armed`.
5. Then continue the remaining live setup items: camera TCC, n8n workflow activation,
   calls provider, and DEMO-SCRIPT clean runs.

## Open bugs / blockers
- [ ] Lohith: strict Friday wake is not live until he records/trains the custom
      wake model and owner verifier, then sets the three env vars noted above.
- [ ] Lohith: camera under launchd still depends on the one-time macOS permission.
- [ ] Lohith: n8n workflows / real Studio publish / calls provider remain setup work.
- [ ] Nothing code-blocked; Friday rename, passive dashboard, and wake-only lock path
      are implemented and fully unit-tested.

## n8n WIRED over the tailnet (2026-08-15)
- Base URL + API key in .env; n8n reachable (200) at the VPS's ts.net name.
- 49 workflows enumerated via API — ALL inactive. 5 wired live in tools.yaml
  (job_search, review_draft, lead_intake, vendor_report, maintenance_request)
  with the real webhook paths + risk ladder. 434 unit green; router eval with
  8 tools PASSED (export ANTHROPIC_API_KEY first — conftest hides .env).
- Board: n8n ops chip armed. Studio/content + metrics workflows don't exist in
  his n8n yet — those stay dark until he builds them (contracts in docs).
- LOHITH: activate the 5 workflows in the n8n editor (they 404 until active),
  then say e.g. "run the vendor report" / "find me jobs" to Jarvis.

## launchd INSTALLED — system is permanent (2026-08-15)
- All 5 agents loaded. Dashboard handed from dev session to launchd (orphan
  killed, kickstart) — public URL verified 200 via funnel under launchd.
  LiveKit container up. Metrics timer ran clean. Killswitch RUNNING (menu bar).
- Lohith's two permission clicks: Accessibility (hotkey, killswitch prompt) +
  Screen Recording (screenpipe crash-loops politely until granted).
- Reboot test pending: after next restart everything should self-start
  (Docker Desktop "start at login" must be ON).
- Permissions verified 2026-08-15: screenpipe RECORDING (frames ok -> screen
  recall data flowing; audio stale, nonessential). Doctor down to 2 fails:
  cartesia key + moondream station. Calendar permission STILL pending — needs
  `make collect` run from Lohith's own Terminal to trigger the macOS prompt.
- Calendar CONFIRMED working (2026-08-15): collect wrote calendar rows; live
  end-to-end ask through the launchd server -> calendar_today tool -> real
  EventKit read -> in-persona reply. (Claude Code's own shell stays denied —
  macOS per-app TCC; irrelevant to production surfaces.)

## DOCTOR ALL-CLEAR + last-mile services (2026-08-15)
- Cartesia key + TTS_VOICE_ID wired (voice "Linda" — female; Jarvis-shaped
  alternatives shortlisted in chat: Alistair/George/Benedict). `make doctor`:
  "all clear, sir" — first fully green run. make voice is UNBLOCKED.
- moondream-station installed via `uv tool` (pyenv bypassed), 6th launchd agent
  added (plist + installer glob + tests updated, 437 green). Station serves
  :2020 but the md3p model is HF-GATED: needs a free HuggingFace read token
  (huggingface.co/settings/tokens) -> write to ~/.cache/huggingface/token ->
  restart agent. Camera E2E verified up to the model call (imagesnap capture OK
  after PATH fix: launchd plists for dashboard+killswitch now carry brew PATH —
  bare launchd PATH broke subprocess lookups, found live via "my eyes aren't
  available").

## Voice ON THE UI — wake/stop buttons live (2026-08-15)
- 7th launchd agent com.jarvis.voiceworker: voice.agent dev, sources .env
  (set -a) for LIVEKIT_* — "registered worker" confirmed against the
  tailnet-bound livekit. Fixed on the way: LIVEKIT_API_SECRET was empty
  (Stage 1d never ran) -> generated; LIVEKIT_URL now ws://100.118.41.0:7880
  (compose binds the tailnet IP, loopback dial failed); compose recreated.
- /api/voice-token mints real JWTs now (was 400 on empty secret).
- Voice tab: CONNECT = wake; STAND DOWN now fires the REAL kill path
  (/api/ask "stand down" -> audited, Mac session ends) then hangs up.
- 440 unit tests green; lint green. Voice from the phone browser is fully
  self-serve: open /voice -> CONNECT -> talk -> STAND DOWN.
- Voice-connect fix (2026-08-15): livekit now dual-binds loopback + tailnet IP
  (serve/worker dial 127.0.0.1; phone media hits the tailnet binding); serve
  8443 verified 200. screenpipe runs --disable-audio: its whisper-download
  crash loop (and the resulting permission re-prompts every respawn) is gone —
  first-ever "status":"healthy", frames flowing, audio intentionally null.

## PRE-LIVE GATE RUN + docs/GOING-LIVE.md (2026-08-15)
- Full pyramid executed as the go-live gate: lint + 440 L1 + 11 L2 + 4 L4 +
  33-case L3 vs real Haiku + doctor — ALL GREEN after the gate caught two real
  issues: (1) exporting ANTHROPIC_API_KEY for eval poisons L1 "unconfigured"
  asserts — scope the export to the eval command; (2) test_demo_script still
  scripted pre-gate 3-call turns — realigned (only "Remember:" extracts).
- docs/GOING-LIVE.md written: macOS one-time prompts vs Jarvis's deliberate
  confirm/pin asks (tools.yaml risk knob), what runs unattended, 8-entry risk
  register w/ mitigations + residual ratings, payoff, gate commands, live-fire
  checklist. THE doc for "how risky / how do I benefit".

## THE COCKPIT — single-screen app (2026-08-15, Lohith's call)
- "/" is now app.html + static/app.js: EVERYTHING on one screen. Conversation
  (text + voice) is the centerpiece — one composer [VOICE][input][SEND]; the
  VOICE button is the /voice connect flow inline (STAND DOWN fires the real
  kill path). Deck panels around it: NOW / STUDIO (two-tap publish kept) /
  METRICS (sparklines from __DATA__), refreshed by JS every 60s WITHOUT
  touching the transcript (no meta-refresh — it would wipe the conversation).
- Responsive truth: phone = chips -> collapsed glanceable panels -> conversation
  -> composer in the thumb zone, all in one viewport (deck order:-1, 42dvh cap);
  desktop >=960px = two columns, deck auto-opens (matchMedia LISTENER — the
  pane settles width late; a load-time check alone missed).
- dashboard.html DELETED (board content lives in the cockpit); nav label for
  "/" renamed Board->Jarvis everywhere; PWA start_url -> "/". Old tabs remain
  as focused deep links; nav invariant (5 hrefs, one aria-current) unchanged.
- test_ui.py re-pinned: APP+APP_JS join the law (tokens/WCAG/44px/nav/zero-
  external all hold); new cockpit contracts (no http-equiv refresh, setInterval
  panels, composer aria, two-tap publish, vendored SDK). 442 unit green, lint
  green, verified live in-browser desktop + mobile incl. a REAL conversation
  through the cockpit composer (calendar answer in persona).

## SVELTEKIT MIGRATION + /api/v1 (2026-08-19, Lohith's call)
- UI rewritten as a SvelteKit SPA (ui/: Svelte 5 runes + adapter-static,
  63 npm packages BUILD-TIME only; runtime stays zero-external — build output
  served same-origin by the gated Python server). Old integrations/*.html +
  vendored livekit UMD DELETED; livekit-client now npm-bundled, lazy-loaded.
- The cockpit "/" + focused /chat /studio /today /voice as client-side routes;
  the transcript lives in shared stores and SURVIVES navigation (verified live).
  Animations = Svelte transitions (fly/slide/fade), one attribute each.
- API resurfaced as /api/v1/* (conversation, system/status, metrics, agenda,
  studio/queue[+refresh|publish|skip], voice/session); unversioned paths kept
  as deprecated aliases. Server serves ui/build with resolve+containment
  (traversal/null-byte hardened), immutable cache headers, no more __DATA__.
- Tests: new test_api_v1.py (positive/negative/EXCEPTIONAL: %2e%2e + null-byte
  traversal, unicode/emoji, 100KB bodies, HEAD=501, wrong-method 404s);
  test_ui.py re-pinned to ui/src + build (tokens/WCAG/44px/nav/a11y/zero-
  external + Svelte contracts: transitions used, two-tap publish, lazy livekit,
  real stand-down). 464 unit green; lint green; verified live desktop+mobile
  incl. a real /api/v1/conversation turn. make ui = rebuild; snapshots exclude
  ui/node_modules + .svelte-kit. docs/API.md rewritten for v1.

## OFFICIAL ARCHITECTURE DOC + ruff standards restored (2026-08-19)
- docs/ARCHITECTURE.md written: layer rules, feature->modules->tests map
  (every feature names its test files + counts), enforced coding standards,
  extension recipes, enforcement list. THE architecture reference.
- REAL FIND: pyproject had NO ruff rule selection (defaults only) — 12 stale
  noqa comments proved a broader set was lost at some point. Restored
  officially: select = E,W,F,I,N,UP,B,SIM,RUF. 20 violations surfaced ->
  all fixed (12 auto, 8 wrapped lines incl. brain/mood.py placeholder + an
  en-dash docstring). 464 unit green under the stricter law.

## UI ACTIVE/DORMANT control + daemon state (2026-08-19)
- client/control.py (kill-path pure, no-network proven): wake/stand_down/state
  files beside data/control/stand_down. Daemon (TDD red-first, harness extracted
  to tests/test_daemon_harness.py): wake file wakes DORMANT (consumed once,
  stale cleared at dormant entry — crash never insta-wakes), state file truthful
  (active only after spawn; off on quit).
- /api/v1/daemon/wake + /daemon/stand-down; system/status carries daemon state.
- Masthead pill on every screen: ● Active — stand down / ○ Dormant — wake /
  — daemon off. LIVE-FIRED end to end: API wake -> chime+mic ACTIVE ->
  stand-down -> DORMANT, audit rows wake|control_file + stand_down.
- 472 unit green; lint green. WHY "Wake up Daddy's home"/offline "stand down"
  don't work in background: Stage 6 models UNTRAINED — bundled "Hey Jarvis"
  is the only wake phrase; offline kill unarmed until KILL_MODEL_PATH.
  Lohith to record + train (voice/wakeword/README.md) and send 2 .onnx paths.

## Spoken stand-down UX + weather sense (2026-08-19)
- FOUND LIVE: spoken "stand down" WAS working (audit proved both fires) but the
  10s SIGINT teardown was silent -> felt broken. Fixed: Submarine chime the
  instant the kill lands (before teardown), SIGINT grace 10s -> 4s. TDD'd.
- Weather (Stark ask "tell me whether"): adapters/weather.py via Open-Meteo
  (keyless), WEATHER_CITY in .env, tools.yaml `weather` (safe), 4 mocked tests
  (format/unconfigured/unknown-city/failure), 2 new router eval cases — eval
  PASSED vs real model. LOHITH: set WEATHER_CITY=<his city> in .env.
- 478 unit green; killswitch + dashboard restarted with the new code.
- Weather LIVE for Farmington Hills (2026-08-19): WEATHER_CITY set; adapter now
  honors a spoken place ("weather in Austin?") over home city (6 tests).
  Verified end-to-end through /api/v1/conversation with real Open-Meteo data,
  in persona. "Location tracking" = home city + spoken override by design
  (no IP-geo third parties; a desk Mac has no GPS).
- LANE 2 (web hands) LIVE-FIRED (2026-08-19): conversation -> confirm gate ->
  "yes" -> real Chrome (jarvis profile) drove example.com -> heading reported
  in persona. IG use needs Lohith's one-time login in ~/jarvis-chrome.
- LANE 1 scaffolds CREATED in his n8n via API (INACTIVE, his activation law):
  "JV Studio Trending (scaffold)" id=CAulvKUC9jdscncR returns 3 labeled sample
  items; "JV Studio Publish (scaffold)" id=te3ky7rt4nzmQ6Bx deliberately 409s
  so Studio never falsely marks posted until IG Graph API is wired. .env
  webhooks set; studio chip TRUE. He inspects + activates + wires IG creds.

## Vault GRAPH removed — hand off to Obsidian instead (2026-08-25)
Lohith: "remove the vault, it's not helping me like obsidian. it's a very poor
implementation." Clarified scope via AskUserQuestion (the word "vault" covers two
different things) -> he chose "Screen -> 'Open in Obsidian'": kill the graph
screen, KEEP Jarvis answering from / writing to notes by voice.
- Mapped every touchpoint first with a 6-agent workflow (ui/api/brain/adapter/docs
  + synthesis). It caught two traps: (1) server.py resolves api.vault_graph /
  api.vault_note AT IMPORT, so deleting the api functions without the routes would
  have broken the WHOLE server (incl. /api/v1/conversation); (2) test_api_v1.py's
  VAULT_PATH tmp fixture must STAY - the HUD test reaches vault.recent(), and
  without it the suite would read his real leos-brain (personal note titles in
  test output).
- DELETED: ui/src/lib/components/VaultPanel.svelte (235-line force graph),
  ui/src/lib/markdown.js (sole importer was VaultPanel), tests/unit/test_vault_graph.py,
  adapters/vault.py graph()/_WIKILINK/note_by_stem, api.vault_graph/vault_note,
  the 2 vault routes, api.js vaultGraph/readNote, the dashboard's Vault expand card
  (incl. the coupled `class:expanded={showVault || showGesture}` -> showGesture).
- REPLACED WITH: adapters/vault.open_in_obsidian(note="") -> `open obsidian://open?
  vault=<name>[&file=<note>]` (subprocess, no shell, urllib quote; run= late-bound
  so tests can patch it - the import-time default silently ran the REAL `open`
  and made 2 tests fail, caught and fixed). Gated POST /api/v1/vault/open ->
  api.vault_open. HUD "Notes & Reminders" card gained a 44px "Open in Obsidian"
  button + the recent-note chips are now buttons that open THAT note in Obsidian.
- KEPT (the brain is untouched): adapters/vault.py search/append_inbox/recent/
  read_note/_resolve/_is_off_limits, brain/nodes/vault.py, the router's vault
  route, tests/unit/test_vault_allowlist.py (the path-allowlist safety suite),
  settings vault_path/vault_exclude. No eval/scenario run needed - no router,
  prompt or demo-step change.
- VERIFIED LIVE: obsidian:// URL scheme opens leos-brain (proven before building);
  POST /api/v1/vault/open -> "Opening leos-brain in Obsidian, sir."; the brain
  STILL answers from his real notes over /api/v1/conversation; /api/v1/vault/graph
  now 404s; /api/v1/hud still 200s; dashboard screenshot shows the graph card gone
  and the OPEN IN OBSIDIAN button + clickable note chips in place.
- 551 unit + 11 integration green; lint clean; build clean. New tests: 2 adapter
  (URL build, escaping, failure) + 2 endpoint (handoff, 400 on failure).

## Single dashboard — consolidated the 7 tabs into one screen (2026-08-25)
Lohith: "keep everything in a single dashboard." Answered via AskUserQuestion:
chat + card grid, remove the tab bar, vault/gesture as expand-on-demand cards.
- Converted each screen to a reusable panel: cp routes/{hud,today,vault,gesture}/
  +page.svelte -> lib/components/{Hud,Today,Vault,Gesture}Panel.svelte (stripped
  <svelte:head>; VaultPanel.ask() no longer goto("/chat") — chat is on the dash).
  StudioPanel/MetricsPanel/NowPanel already existed.
- routes/+page.svelte REWRITTEN = the single dashboard: left = conversation
  (Log+Composer), right = card grid (NowPanel/StudioPanel/MetricsPanel/TodayPanel
  + full-width HudPanel) + two `{#if show}`-gated expand cards for VaultPanel +
  GesturePanel (heavy graph/camera only mount when expanded — keeps it light).
  Desktop = 2 cols; phone = stacked (conv 46dvh, grid scrolls).
- +layout.svelte: nav tab bar DELETED (masthead + WAKE pill stay). Deleted the 6
  redundant route dirs (hud/today/studio/chat/vault/gesture) — only / remains.
- server.py: PAGES = {"/"}; unknown non-API, non-traversal GETs FALL BACK to
  index.html (SPA) so old deep links (/hud, PWA) show the dashboard; /api or
  ../\0/// paths still 404 (urlsplit eats a leading //, so the guard checks "..").
- test_ui re-pinned (no nav; dashboard composes all panels; vault-graph guard ->
  VaultPanel; build output = index.html only). test_dashboard_server +
  test_voice_server updated: every route serves the one SPA shell now.
- 559 unit + 55 UI green; lint clean; build clean. VERIFIED LIVE: "/" renders the
  masthead (no tabs) + chat composer left + the full card grid right (NOW/Studio/
  Metrics/time/weather/system/snaps/notes/automations); vault+gesture bundled.
- REFINEMENT (Lohith: "make the chat button not the widget and do not make it
  scrollable"; AskUserQuestion -> "a button that opens chat"): moved Log+Composer
  OUT of the dashboard into a header "▸ CHAT" button that opens a right slide-over
  overlay (fly transition + scrim). The dashboard is now the FULL-WIDTH card grid
  filling the screen with overflow:hidden (NOT scrollable) — only becomes scrollable
  when a big view (vault/gesture) is expanded (.grid.expanded). Verified live: CHAT
  button opens the conversation overlay; dashboard is all cards, no scroll.
  test_ui re-pinned (chatOpen + <Log/> + <Composer/> in LAYOUT, Log NOT in dash).

## Gesture G3 — motion gestures + alignment fix (2026-08-20)
Lohith sent a screenshot: the skeleton was OFFSET from his hand, and said start G3.
- ALIGNMENT FIX (the "uneven tracking"): the /gesture feed used object-fit:cover
  (crops the image) while the SVG overlay stretched to the full box -> mismatch.
  Fixed: the <img> now displays at NATURAL aspect (max-w/h, no crop) and the
  overlay covers exactly the image (position:absolute inset:0 on the img-sized
  frame) -> skeleton coord space == displayed image. Verified live (4:3 frame,
  skeleton drawn on it at correct scale). Poll bumped 90->55ms for smoother track.
- G3 MOTION GESTURES (gesture/motion.py, pure/stateful, 4 tests): swipe (open palm
  moving fast horizontally -> switch Space ⌃←/⌃→), zoom (TWO hands apart/together
  -> ⌘+/⌘−), pause (open palm HELD still -> clears the control flag). Velocity
  distinguishes held-palm-pause from moving-palm-swipe (resolves the G2 conflict
  where any palm paused). Cooldown 0.7s debounces; _last_fire=-1e9 so the FIRST
  action fires (bug caught by tests). Fixed a 0.0-is-falsy bug in the still-timer.
- actuator.py gained key()/switch_space()/zoom() via Quartz CGEvent keyboard
  events (needs Accessibility like clicks; all symbols verified). agent.py wires
  Motion into the armed-control loop: pause>swipe/zoom>cursor; _actuate_motion maps
  action->keystroke.
- 563 unit + 55 UI green; lint clean; swiftc clean. New tests: motion swipe/zoom/
  pause/cooldown, actuator shortcut mapping, agent _actuate_motion.
- LOHITH's live test: `uv run python -m gesture.agent`, /gesture, Enable cursor
  control (allow Accessibility). point→cursor, pinch→click, swipe open palm L/R→
  switch Space, two hands apart/together→zoom, hold open palm→pause. Directions/
  thresholds are tunable if backwards. NEXT: G4 (polish + always-on launchd agent).

## Gesture control G2 — cursor + click, camera feed, two hands, full set (2026-08-20)
Lohith ran G1 and said start G2 + additions (answered via AskUserQuestion): show
the live camera feed; cursor control OFF-until-enabled + open-palm pauses; the
POINTING hand drives the cursor; the WHOLE gesture set incl. "sarina's middle
finger"; TWO hands.
- Swift binary: maximumHandCount=2, emits {"hands":[{chirality,landmarks(21)}]} per
  frame; optional argv frame path writes the raw JPEG (live feed). Recompiled clean.
- classifier.py REWRITTEN to the whole set: fist/point/sarina's middle finger/
  pinch/peace/three/four/open_palm/thumbs_up via per-finger extended detection +
  thumb-out heuristic (thumb best-effort in 2D). ~11 classifier tests.
- actuator.py (NEW): Quartz CGEvent — to_screen() pure coord map (mirror-x/flip-y,
  unit-tested), move() = CGWarpMouseCursorPosition (no perm), click() = CGEventPost
  (needs Accessibility). Verified all Quartz symbols present live.
- agent.py: multi-hand frame_state (per-hand classify), pointing_hand (pinch>point),
  Cursor (edge-triggered: move on point/pinch, click once per pinch), open-palm
  clears the arm flag (pause), honors camera_off. Runs binary with the frame path.
- API: gesture_state now {on_air,control,hands[]}; gesture_control POST arms/disarms
  the control flag; GET /api/v1/gesture/frame serves the JPEG no-cache (404 until
  running). server routes + settings (gesture_frame_file/gesture_control_file) added.
- UI /gesture REBUILT: live camera <img> (mirrored, cover) + SVG overlay of BOTH
  hands' skeletons + per-hand gesture tags + Enable-cursor-control toggle (44px) +
  ON-AIR. VERIFIED LIVE: seeded 2 hands (right point/left peace) + placeholder
  frame → screen rendered both skeletons + labels + feed + toggle (screenshot).
- 557 unit + UI green; lint clean; swiftc clean. New tests: classifier whole-set,
  agent multi-hand/pointer/cursor-edge, actuator to_screen, api control+frame.
- LOHITH's live test: `uv run python -m gesture.agent` → open /gesture → see the
  feed + both hands + gestures; click Enable cursor control → allow the macOS
  ACCESSIBILITY prompt → point moves the cursor, pinch clicks, open palm pauses.
  NEXT: G3 (swipe/zoom motion gestures) on his go-ahead.

## Gesture control G1 — live hand projection on /gesture (2026-08-20)
Lohith ran G0 ("it works") and said start G1. Built the projection: the app's new
/gesture screen draws his hand skeleton live, with the recognized gesture + ON-AIR.
NO Mac control yet. Privacy: only joint COORDS are published — raw camera pixels
never leave the Mac.
- Swift binary now emits all 21 joints (was 12) for a full skeleton; recompiled.
- gesture/agent.py — runs the native binary, classifies each frame, atomically
  publishes {landmarks, gesture, ts} to data/gesture/state.json; honors camera_off;
  deletes the file on stop (off-air). state_for_line() is unit-tested. Opt-in,
  manual (`uv run python -m gesture.agent`), no launchd.
- api.gesture_state (gated GET /api/v1/gesture/state): on_air = state <1.5s fresh,
  else off-air + empty. ui/src/lib/api.js gestureState().
- ui/src/routes/gesture/+page.svelte — SVG skeleton (23 bones + joints) from the
  polled landmarks (80ms), mirror-x + flip-y; big gesture label; ON-AIR dot; a
  "start the tracker" hint when off-air. Added /gesture as the 7th nav tab
  (+layout.svelte); server PAGES + test_ui SCREENS updated to 7.
- VERIFIED LIVE: seeded a sample open-hand state → /gesture rendered the full
  skeleton + "OPEN PALM" + ● ON AIR (screenshot). Endpoint returns on_air/gesture/
  21 joints; stale/missing → off-air. Sample removed after.
- 550 unit + UI green; lint clean; swiftc build clean. New tests: agent
  state_for_line (2), api gesture_state fresh/stale (2), + classifier/spike (G0).
- LOHITH's live test: `make gesture` (already built) → `uv run python -m
  gesture.agent` in a terminal → open /gesture → his hand tracks live. NEXT: G2
  (point→cursor, pinch→click) needs Accessibility perm — his call to start.

## Gesture control G0 — Vision hand spike (2026-08-20)
Lohith said "start G0". Built the safe foundation: prove Apple Vision sees his
hand, NO Mac control. Env check: swiftc 6.3.3 present; pyobjc Vision/AVFoundation
NOT installed -> chose a native Swift binary (cleaner than pyobjc framework adds).
- gesture/handpose.swift — AVFoundation camera + Vision VNDetectHumanHandPoseRequest
  (maxHandCount 1) -> 12 key joints as one JSON line/frame on stdout (normalized).
  COMPILES clean (swiftc -O, exit 0, 106KB binary) and RUNS — in the TCC-denied
  shell it printed the honest "gesture: Camera access denied" and exited (proves
  the binary + AVFoundation access path + error handling; live camera is Lohith's).
- gesture/classifier.py — PURE static-gesture logic: {joint:(x,y)} ->
  pinch/point/open_palm/fist/none (scale-normalized by wrist->middle_mcp; fist
  checked before pinch since a fist also has thumb near index). 7 tests.
- gesture/spike.py — runner: pipes the native feed through classify(), prints the
  live gesture on change. gesture_for_line() parse+classify is unit-tested (2).
- make gesture builds the binary; gesture/README.md = run steps + safety (opt-in,
  terminal-run, prints only — no cursor/click). NO launchd agent (opt-in only).
- 544 unit green, lint clean. Motion gestures (swipe/zoom), the /gesture UI feed
  projection (G1), and Mac control (G2-G4) are NOT built — each after the prior
  proves out (docs/archive/GESTURE-CONTROL.md).
- LOHITH's live test: `make gesture` then `uv run python -m gesture.spike` from a
  terminal, allow the Camera prompt, wave his hand -> sees open_palm/point/pinch/
  fist. Then we do G1 (project the feed onto a /gesture screen).

## Spotify playback + vault note viewer (2026-08-20)
Lohith tested: "play songs on Spotify" was RE-OPENING Chrome+Spotify instead of
playing; wanted to SEE vault note content on /vault; asked for the outstanding-
tasks list + local-run answer. Fixed the two issues (his order: fix→test→features).
- SPOTIFY (root cause via Explore agent): "play … spotify" → router `ops` →
  `ops_select` picked `open_apps` because it was the ONLY Spotify-named tool →
  re-ran launch_apps() (full re-open). No playback capability existed. FIX:
  adapters/spotify.py `control(arg, utterance)` via macOS `osascript` (no dep/key/
  OAuth) — play/pause/next/previous/now-playing; `spotify_play` tool (safe) in
  tools.yaml; trimmed `open_apps` description so "Spotify" isn't its lead noun.
  VERIFIED: ops_select now returns `spotify_play` for "play some music on spotify"
  (not open_apps); router eval ≥90% with the new case. `tell … to play` auto-
  launches Spotify, so it plays music, never re-opens Chrome. Play-by-name (needs
  Spotify Web API/OAuth) deliberately NOT built — Lohith chose basic controls.
- VAULT NOTE VIEWER: `adapters/vault.py:read_note` already existed (secure, 4000-
  char cap, all exclusions) but was wired to nothing. Added `note_by_stem(stem)`
  (glob **/{stem}.md, skip _is_off_limits, read_note; safe by construction) +
  `api.vault_note` + gated POST /api/v1/vault/note. UI: `readNote(id)` in api.js;
  tapping a /vault node fetches + renders the note as MARKDOWN in the peek panel
  via a tiny dependency-free ui/src/lib/markdown.js (escapes HTML first, then
  headings/bold/italic/code/fences/lists/links/[[wikilinks]] — zero-external
  holds). VERIFIED LIVE: tapped "sales-engine" → panel rendered 2356 chars as
  h3/h4/p/ul/ol/li/code/strong; traversal "../../.env" → 400.
- 535 unit + 53 UI green; lint clean; router eval ≥90%. New: test_spotify (5),
  vault_note endpoint tests (3). dashboard restarted (new route), voiceworker
  restarted (new tool).
- LOCAL-RUN ANSWER for Lohith: never run from VS Code. UI change → `make ui` +
  reload browser (server reads files per-request). Python change → `launchctl
  kickstart -k gui/$(id -u)/com.jarvis.dashboard` (+ voiceworker for voice code).
  `make dashboard` conflicts with the launchd agent on 8787.
- NEXT (Lohith's pick): Gesture G0 — camera projection + Apple Vision hand
  tracking to a new /gesture screen, NO Mac control yet. Its own session (needs
  his live camera). Also still outstanding: mood engine (brain/mood.py stub),
  speaker verification, + his real-machine steps (camera TCC, n8n activate, wake
  phrase, IG API, Vapi, iPhone, demo).

## Live-test fixes: wake-apps, camera honesty+snaps, voice streaming (2026-08-20)
Lohith tested and reported: apps didn't open on wake, camera "says picture taken
but isn't", wants his own voice, replies slow. Root-caused (3 Explore agents +
audit-DB evidence) and fixed. NO VS Code needed — all launchd agents run on login
(verified killswitch PID live, no terminal); Chrome/Spotify installed under the
exact names.
- APPS: the ONLY reason they didn't open = the first-wake-of-day gate (audit
  showed the brief marker fired at 00:29, so the 09:48 test skipped launch).
  FIX: voice/agent.py now calls launch_apps() on EVERY wake (removed the gate);
  adapters/apps.py checks each `open` returncode + logs (no more silent no-op).
- CAMERA "lies": adapters/camera.py:45 claimed success on rc==0 + file-exists
  only; a TCC-denied camera writes a BLACK jpeg at rc 0 (or rc 1 "access not
  granted"), moondream described the darkness, the persona narrated it. FIX:
  validate the frame (PIL mean-luma < 8 = black -> raise), surface imagesnap
  stderr (was DEVNULL), save each real frame to data/vision/snaps/ (keep 20).
  LIVE-PROVEN from the (TCC-denied) shell: honest reject "camera capture failed
  ... Error: Camera access not granted", no black frame saved.
- SNAPS in the dashboard (Lohith wanted visual CONFIRMATION): api.vision_snaps +
  gated GET /api/v1/vision/snaps[/<id>] (path-contained), a SNAPS tile on /hud
  showing recent captures. Live-verified: endpoints 200 image/jpeg, tile renders
  the frame + timestamp + "N seen".
- LATENCY: (1) greeting speaks FIRST, check-in is a 2nd utterance + now fast=True
  (Haiku, was silently Sonnet). (2) STREAMING the reply to TTS — the big win:
  adapters/llm.think_stream (messages.stream); chat_node streams tokens via
  langgraph get_stream_writer ONLY when the voice agent sets a `stream_tokens`
  config flag (text/tests/scenario use the blocking path untouched); voice
  llm_node consumes astream(stream_mode=["custom","updates"]), yields tokens as
  they arrive, preserves the confirm-gate interrupt (verified the astream
  interrupt shape). STT already at Deepgram's 25ms default — left alone.
- OWN VOICE = DEFERRED (Lohith: any voice for now). Speaker-verification path
  noted for later (openWakeWord custom_verifier_models + enroll script).
- 525 unit + 11 integration + 4 scenario + 51 UI green; lint clean. New tests:
  camera black-frame/snap-saved/stderr, wake-apps failure, api snaps x2, agent
  streaming, graph streaming, llm think_stream. dashboard+voiceworker restarted.
- LOHITH's remaining real-machine step: grant macOS Camera access to the
  launchd-run capture (the error now names it). When he says "what am I holding?"
  under the running system, macOS should prompt for Camera — allow it.

## Wake routine + caring persona + calls scaffold + docs shrink (2026-08-20)
- Lohith's asks (answered via AskUserQuestion, all "recommended"): apps open on
  FIRST wake of day; caring check-in EACH wake; calls = scaffold+document;
  docs = consolidate + archive extras.
- MORNING LAUNCH: adapters/apps.py (subprocess `open` only) opens Spotify +
  Chrome tabs (WAKE_URLS: IG/GitHub/Gmail/cockpit). Fired in voice/agent.py on
  first wake (tied to the EXISTING morning_brief first-wake signal — brief is
  non-None only on first wake, zero new state) AND by the `open_apps` tool
  ("open my apps"). Settings: wake_apps_enabled/wake_launch_spotify/wake_urls.
- CARING CHECK-IN: brain/checkin.py — each wake, ONE warm question rotating
  health/skills/location/activity (rotation = wake-count-today % 4), grounded in
  a recalled fact so it follows up naturally; answer remembered by the normal
  memory_writer. Wired into the agent greeting (brief-or-hello + check-in).
  persona.md gained a "Care & family" section (warmth inside the 3-sentence cap,
  never delays a task/kill). This IS the UI-on-wake answer too: on the Mac the
  wake routine opens the cockpit tab; phone = tap the PWA (can't auto-launch).
- CALLS (PIN-gated, scaffold): adapters/telephony.py refuses until configured,
  dispatches to Vapi once TELEPHONY_* set (urllib, no dep); Twilio+LiveKit left
  as a documented seam. tools.yaml make_call activated (was commented). Needs
  Lohith's provider signup — docs/CALLS.md. Nothing half-working runs.
- ROUTER: vision route already had "see me" etc (prior task); ops route
  REWRITTEN ("DO a concrete action... workflow/calendar/call/apps/weather/
  reminder") because the two new tools exposed calendar/call leaking to chat —
  eval dropped to 88%, the rewrite restored ≥90%. +eval cases (open my apps,
  call the dentist); test_router substring re-pinned.
- DOCS SHRUNK: 15→7 at docs/ root (SETUP, ARCHITECTURE, DEMO-SCRIPT, TESTING,
  EMOTIONS, MOBILE[new], CALLS[new]); 10 moved to docs/archive/ (API, DASHBOARD,
  CONTENT-STUDIO, N8N-SETUP, CALENDAR, GOING-LIVE, COMPETITORS, FEATURES,
  GESTURE-CONTROL, PHONE). SETUP links repointed. README rewritten as a concise
  run-book (the reverted competitor-roadmap version is gone; roadmap lives in
  docs/archive/COMPETITORS.md). docs/MOBILE.md = phone control over Tailscale.
- 517 unit green, lint clean, router eval ≥90%. New tests: test_wake_apps (7),
  test_checkin (4), test_telephony (6).

## Performance investigation + light-touch optimization (2026-08-20)
- Lohith's Mac (16GB, also his work machine) showed Idle 0% in Activity Monitor.
  MEASURED the real consumers (his screenshots were scrolled past them):
  * Jarvis is LEAN — ~694MB RAM total (screenpipe ~470MB @0.2fps, moondream idle
    ~40MB model-not-resident, dashboard 11MB, killswitch) + ~10% of ONE core.
  * The saturation was NOT Jarvis: 12 non-Jarvis Docker containers (a Supabase
    "swamp" stack + Prisma, up 11h–13d, ~2.8GB) + a transient 2.2GB node/MCP
    spike (self-cleared) + WindowServer 32% + his work apps. Jarvis's OWN livekit
    container is 68MB — but its launchd agent is what BOOTS Docker Desktop at
    login (Docker isn't in login items), reviving the other 12 containers.
- Lohith's calls: KEEP voice/Docker always-live (he wants it all the time);
  camera should wake on a natural spoken command; DROP the ⌥⌘J hotkey.
- Changes (all functionality intact, 502 unit green, eval ≥90% held):
  1. Camera natural-wake: router "vision" route gained "see me"/"look at me"/
     "can you see this?"/"look at this" (brain/nodes/router.py + 3 eval cases).
     Verified vs real Haiku: all route to vision; "I need you to check my
     calendar" correctly stays chat (bare "I need you" deliberately NOT added —
     too ambiguous, would false-trigger the camera).
  2. Hotkey dropped: settings.hotkey default "" (blank = pynput global keyboard
     hook never started); killswitch.main() guards on non-empty. HONEST: this
     did NOT cut CPU — my pynput hypothesis was WRONG.
  3. Real killswitch CPU cause FOUND: the DORMANT openWakeWord listener runs 3
     tiny ONNX models on the mic every 80ms to hear "Hey Jarvis" — ~10% of one
     core, inherent to always-on wake (the feature he wants). Thread-capped it
     (OMP/OPENBLAS/VECLIB=1 in the killswitch plist) — only ~1% gain (compute-
     bound, not thread-bound). Kept it (safe, no accuracy change).
  4. killswitch _refresh now skips the NSStatusItem redraw when state unchanged.
- BIGGEST reclaim for his work machine is NOT Jarvis: stop the 12 idle non-Jarvis
  containers (~1.2GB + shrinks the Docker VM). Offered; his call (his projects).
- NOTE: README.md on disk reverted to an OLD competitor-roadmap version — the
  maintained run-book was clobbered (flagged to Lohith; did not auto-revert).

## EYES ARE ON — camera live on Moondream 2 (2026-08-20)
- Camera works end-to-end: `md.vl(endpoint=:2020/v1).query()` (the exact adapter
  path) returns correct answers — probed red/orange/blue → "Red"/"Orange"/"Blue".
  ~8–16s/query on 16GB. Verified through Jarvis's own adapters/camera.py client,
  not just raw HTTP.
- TWO real blockers found + fixed (both live-only, outside the repo):
  1. Moondream Station (DEPRECATED) always boots md3-MLX-Quantized as active
     model and REWRITES config.current_model on every fresh boot → md3 too heavy
     for 16GB, service never answers ("Queue is full" = no model loaded, RSS
     ~30MB). Fix: scripts/moondream_serve.py drives the REPL through a **pty** —
     `models switch moondream-2`, answers the interactive requirements confirm
     (needs a real TTY; piped stdin fell through as "Unknown command: y"), then
     `start 2020`, holds open for KeepAlive. Plist rewired bash-pipe → this
     script (added __HOME__ to install_launchd.sh sed).
  2. Station ships **transformers 5.15**; moondream-2's remote code
     (HfMoondream) predates it → first `all_tied_weights_keys` crash, then after
     a 1-line cache patch, GIBBERISH tokens. Real fix: pinned
     `transformers==4.46.3` in the station venv (station's own code imports no
     transformers, so safe). Documented in docs/SETUP.md §3b with re-pin command.
- 501 unit green, lint clean. Camera adapter endpoint (:2020/v1) unchanged —
  no code edit needed there; the fix was all in how the station is launched.
- FRAGILITY (documented): the transformers pin + pty-switch live in
  ~/.moondream-station (not the repo). A station reinstall/auto-update reverts
  them → SETUP §3b is the recovery. HF token stays wired for a future md3 upgrade
  if the Mac ever grows past 16GB.

## Obsidian vault graph — VISIBLE in the UI (2026-08-19)
- CLARIFIED for Lohith: the vault is ALREADY Jarvis's memory (adapters/vault.py
  reads leos-brain live — 906 md notes; better than "training": always current,
  private, free). What was missing = SEEING it.
- adapters/vault.graph(): scans .md, [[wikilinks]] -> edges, off-limits/hidden
  skipped, capped to top-N by degree. /api/v1/vault/graph endpoint. New /vault
  route (6th nav tab) renders a dependency-free force layout (no d3); tap a node
  -> asks Jarvis about that note -> /chat. Verified live: 725 linked notes, 80
  shown, 278 links, top node degree 65; SVG renders 80 circles + 278 edges.
- 488 unit green (5 graph tests vs a TEMP vault — real titles never touch tests
  or logs), lint green. SECURITY: Lohith's IG password appeared in a shared
  screenshot -> told him to rotate it; never stored anywhere.
- Vault graph is now MOTION-CONTROLLED (2026-08-19): drag to pan, wheel + pinch
  to zoom (scale-based viewBox, fixed 1000:700 aspect — no getBoundingClientRect
  NaN), +/-/reset buttons, labels reveal as you zoom in, tap a node -> peek panel
  (linked-note count + Ask Jarvis). Verified live: zoom viewBox transforms clean
  and all-numeric, real note labels render. test_ui guards onwheel/onpointerdown/
  viewBox/touch-action. 489 unit + lint green.

## Log rotation (2026-08-19)
- scripts/rotate_logs.py (TDD, 5 tests): copytruncate — over-10MB *.log gzip
  to <stem>.<stamp>.log.gz then TRUNCATE IN PLACE (launchd holds the fd in
  append mode across restarts — a rename would orphan it, confirmed by logs
  accumulating over kickstart). Prunes *.log.gz older than 7 days. 8th launchd
  agent com.jarvis.logrotate (hourly StartInterval, no KeepAlive — a sweep).
- LIVE-PROVEN: first run rotated 2 already-fat logs (screenpipe, moondream);
  forged 11MB probe -> original 0 bytes, contents intact in the .gz. 497 unit
  green; test_launchd metrics/logrotate share the hourly-timer assertion.

## HUD dashboard — glance screen (2026-08-20, Lohith's ask)
- New /hud (7th tab, chat stays home): single-screen, no buttons except tap-a-
  run. Live clock (client tick), Weather (°F now — adapters/weather.conditions),
  System vitals (adapters/system.py psutil: cpu/ram/disk/uptime), Notes &
  Reminders (spoken store integrations/reminders.py + calendar + recent vault
  notes), Automations (integrations/automations.py n8n executions: today counts
  + recent runs, tap -> /automations/detail data preview), Systems chips.
  Aggregated by api.hud(); auto-refresh 6s. Weather flipped C->F + mph.
- macOS Reminders (EKEntityTypeReminder) DROPPED: requestFullAccessToReminders
  from a non-bundled Python proc throws an UNCATCHABLE ObjC NSException (no
  Info.plist usage-desc) that aborts the server — 3 of 4 reminder sources live.
- New `reminder` tool ("remind me to ..." -> spoken store, risk safe). Router
  prompt unchanged wording-wise (weather already ops); no eval regression run
  needed but tools grew. 505 unit green; lint green; verified live in-browser:
  63°F Farmington Hills, cpu/ram/disk bars, real vault-note chips, pin chip ✓.

## HUD/UI declutter — voice-first, human-readable (2026-08-20, Lohith's 6 asks)
- (1)(4) Removed BOTH systems-chip surfaces: the HUD Systems card AND the global
  Chips strip under the masthead (deleted Chips.svelte). (2) HUD relaid: left
  column = compact Time / Weather / System rectangles; right = Notes&Reminders +
  Automations. (3) Voice is wake-word only now: deleted the /voice route + tab
  (6 tabs) and the composer Voice button (Composer.svelte trimmed). voice.js +
  /api/v1/voice/session KEPT (capability preserved, UI entry points gone).
  (5)(6) Humanized the audit log: api._humanize maps codes -> plain English
  ("wake/wake_phrase" -> "Woke up — you said the wake phrase", daemon states ->
  "resting — say Hey Jarvis"); Today + NowPanel show a.label. activity entries
  gained a "label" field.
- test laws re-pinned to 6 screens; test_voice_server now asserts /voice 404s;
  safety-contract test points at the WAKE pill not the removed voice button.
  501 unit green; lint green; verified live: cockpit has no voice button, 6
  tabs, no chip strip; HUD left-column layout renders.

## HF token wired — camera unblocked + README-per-task rule (2026-08-20)
- HuggingFace read token saved to ~/.cache/huggingface/token (0600, NEVER in
  repo/.env/snapshots). Station switched back to Moondream 3 (md3p gated) —
  token authenticates, weights downloading (5.4G, gated error gone). Watcher
  confirms when the model answers; then "what am I holding?" works.
- STANDING INSTRUCTION (Lohith): update README.md after EVERY completed task —
  saved to agent memory (update-readme-after-each-task), CONVENTIONS.md, and a
  live-run-book banner in README itself. README status/checklist refreshed:
  PIN done, camera token wired, HUD live, weather °F, log rotation, voice tab
  removed (6 screens).

## Camera on Moondream 2 + gesture plan (2026-08-20)
- Moondream 3 (12GB) confirmed too heavy for 16GB — queue jams / request
  timeout even after 3-min warm-up. Fell back to Moondream 2 (Lohith's call);
  config current_model=moondream-2, auto_start=false, plist `start 2020`. HF
  token retained in ~/.cache/huggingface/token for future.
- Gesture control SPEC written (docs/GESTURE-CONTROL.md), NOT built — Lohith's
  decisions: Full Mac control, Apple Vision, gestures = pinch-zoom, swipe L/R
  (tab/desktop), pinch-click, point-cursor, open-palm stop/wake. Architecture:
  native com.jarvis.gesture agent (AVFoundation + Vision VNDetectHumanHandPose
  -> CGEvent), MJPEG feed to a /gesture UI screen, opt-in continuous camera w/
  ON-AIR + open-palm/camera-off/menu-bar kills + Accessibility. Build seq
  G0(spike)->G1(projection)->G2(cursor/click)->G3(swipe/zoom)->G4(safety).
  Classifier/action-map/UI unit-testable; camera+Accessibility live-only (his).
  Awaiting his "start G0/G1".

## Jobs command center v1 (2026-09-28)
- New: integrations/jobs.py (read, mtime-cached), jobs_actions.py (atomic
  decisions/answers + open-file allowlist, audited), jobs_api.py (/api/v1/jobs/*
  merged into server GET/POST tables); settings jobs_dir + jobs_tracker_note.
- UI: /jobs route (JobRow component, filters, batch picker, 5s visible-only
  polling via lib/jobs.js) + read-only JobsPanel card on the cockpit.
- DECISION (Lohith): /jobs is the only button surface; test_ui scopes the
  button-free law to everything outside JOBS_SCOPE and adds a jobs a11y test.
- tests/unit/test_jobs.py (13 cases). Full unit suite: 576 passed; ruff clean.
- Found + fixed: repo moved to ~/friday this morning but launchd agents still
  pointed at "~/Jarvis Life OS" -> dashboard crash-looped (ModuleNotFoundError).
  Re-rendered ONLY com.jarvis.dashboard (backup in ~/jarvis-snapshots). The
  other repo-path agents (killswitch, voiceworker, metrics, logrotate,
  moondream) are still on the old path: `make install-launchd` fixes all.
- ui/build was missing (dashboard served "UI not built"); rebuilt via make ui.
- .venv console scripts carry the old path (uv run pytest fails); use
  `uv run python -m pytest` or `uv sync --reinstall`.
- Pending: macOS must allow the dashboard's Python to read ~/Downloads
  (Privacy & Security -> Files and Folders); until then /jobs data calls hang.
