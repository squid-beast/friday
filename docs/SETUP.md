# FRIDAY SETUP — every key, every integration, in order

The one document that takes the system from "code complete" to "demo ready".
Do the stages in order; each ends with a verification command. Total hands-on
time: ~1 hour + the 30-minute wake-phrase recording.

All secrets go in ONE place: `.env` at the repo root. Never anywhere else.

```bash
cd "/Users/lohithkumar/Friday"
cp .env.example .env && open -e .env
```

---

## Ways to run it

Five surfaces, smallest to largest. Each lists what it needs, so you can run
what's unlocked *today* while later stages are pending.

| Mode | Command | What you get | Needs |
|---|---|---|---|
| **Typed chat + app** | `make dashboard` → http://127.0.0.1:8787 | Board / Chat / Studio / Today in the browser; typed chat talks to the full brain (vault, memory, gates, audit) | Anthropic key only — **works now** |
| **Talk (console)** | `make voice` | Full voice conversation on the Mac's mic/speakers with barge-in. No Docker, no wake phrase — press Ctrl-C to stop. The Phase 2 acceptance path | All 3 Stage 1 keys + mic permission |
| **Hands-free (menu bar)** | `uv run python -m client.killswitch` | 😴 in the menu bar; the bundled fallback is "Hey Jarvis" until you train Friday, then "Hey Friday" wakes him. "Stand Down" / ⌥⌘J kills. This is daily-driver mode, started by hand | Same as voice |
| **Everything, on login** | `make install-launchd` → reboot | All six agents forever: dashboard, killswitch, voiceworker, livekit (Docker), hourly metrics, hourly logrotate. Zero terminals | Stage 2; Docker Desktop set to start at login |
| **Phone** | Stage 5 (`tailscale serve`) → PWA on the iPhone | Board/Chat/Studio/Today from anywhere on the tailnet; the Voice tab additionally needs `make run` on the Mac | Stage 5 |

Utility surfaces: `make doctor` (health), `make eval` (router accuracy vs the
real model), `make test` / `test-integration` / `test-scenario` (no network),
`make collect` (metrics pull now), `make snapshot` (safety net).

---

## Stage 1 — The three API keys (~10 min) → unlocks voice, vault, memory, audit

### 1a. Anthropic (the brain — Sonnet answers, Haiku routes) — ✅ KEY OBTAINED 2026-08-11

You have the `sk-ant-...` key. One step remains: paste it into `.env` as
`ANTHROPIC_API_KEY=sk-ant-...` (until then `make doctor` still warns).
If billing isn't set yet: console.anthropic.com → Settings → Billing →
prepaid credits ($5 is plenty to start). Cost expectations and the built-in
call optimizations are in the **Cost & call budget** section at the bottom.

### 1b. Deepgram (ears — speech-to-text) — ✅ DONE 2026-08-11

Key obtained and in `.env`; `make doctor` passes deepgram. (New accounts get
free credit — historically ~$200, months of personal use.)

### 1c. Cartesia (mouth — text-to-speech) + the Friday voice

1. Go to **play.cartesia.ai** → sign up (free tier exists; paid is cheap for
   personal volume).
2. **API Keys** (in the console/settings) → create one. `.env`: `CARTESIA_API_KEY=...`
3. **Pick the voice**: open the **Voices** library, audition until you find a
   composed British male that fits the persona. Click the voice → copy its
   **Voice ID** (a UUID). `.env`: `TTS_VOICE_ID=...`
   (Leave blank to use Cartesia's default while you decide.)

### 1d. The two local secrets (1 min)

```bash
openssl rand -hex 32   # run twice; use one for each below
```
- `.env`: `LIVEKIT_API_SECRET=<first value>`
- `.env`: `FRIDAY_PIN=<a 4-digit number you'll SAY out loud>` — this locks the
  highest-risk tools; unset = they refuse entirely.

### ✅ Verify Stage 1

```bash
make doctor
```
`anthropic / deepgram / cartesia` must say pass (screenpipe/moondream/n8n may
still fail — later stages). Then the first real conversation:

```bash
make voice
```
macOS will ask for **Microphone** access — allow. Say hello; interrupt him
mid-sentence to prove barge-in. Ask a vault question ("what did I quote the
Receivly client?"), tell him to remember something, restart, ask it back.
That's Phase 2 acceptance done.

---

## Stage 2 — Auto-start + kill surfaces (2 min)

```bash
make install-launchd
```

Installs six `com.friday.*` launch agents: dashboard, killswitch (menu bar
😴/🎙), voiceworker (phone voice), livekit (docker), hourly metrics, hourly
logrotate. Screenpipe + moondream agents were removed 2026-09-29 (doctor
reports them "dark by design"). If you set `HOTKEY`, macOS will prompt for
**Accessibility** — allow. Docker Desktop itself must be
set to start at login: Docker Desktop → Settings → General → "Start Docker
Desktop when you sign in".

✅ Verify: menu bar shows 😴. Say the active wake phrase shown in the dashboard
header. Before training that is "Hey Jarvis"; after training it becomes
"Hey Friday" → chime, 🎙, "At your service, sir." Say "Stand Down."

---

## Stage 3 — Eyes: screenpipe + Moondream (~10 min)

### 3a. screenpipe (screen recall) — already brew-installed

1. Run `screenpipe` once in a terminal → macOS prompts for **Screen
   Recording** → allow → restart it (the launchd agent keeps it alive after).
2. Privacy: `.env` → `SCREENPIPE_EXCLUDE=` comma-separated app names that must
   NEVER appear in recall — suggested: your banking apps, WhatsApp.

### 3b. Moondream Station (camera description, fully local) — WORKING 2026-08-20

Installed and serving **Moondream 2** on `http://127.0.0.1:2020/v1` (matches
`.env` `MOONDREAM_ENDPOINT`). Two non-obvious things make it work on a 16GB Mac —
both are one-time setup already done; documented here so a station update
doesn't silently break the eyes:

1. **Runs moondream-2, not moondream-3.** Moondream Station is deprecated and its
   REPL defaults to *Moondream 3 MLX Quantized* on every boot — too heavy for
   16GB, its service never answers. The launchd agent runs
   `scripts/moondream_serve.py`, which drives the REPL through a pty:
   `models switch moondream-2`, answers the interactive requirements confirm,
   then `start 2020`, and holds it open (KeepAlive restarts on death).
2. **transformers is pinned to 4.46.3** in the station venv
   (`~/.moondream-station/venv`). Station ships transformers 5.x, under which
   moondream-2 emits gibberish tokens. If the camera ever starts returning
   nonsense, re-pin:
   ```bash
   ~/.moondream-station/venv/bin/pip install "transformers==4.46.3"
   launchctl kickstart -k gui/$(id -u)/com.friday.moondream
   ```

First camera use triggers the macOS **Camera** permission — allow. Inference is
~8–16s/query on 16GB (CPU/MPS); functional, not fast. The HF token stays wired
for a future Moondream 3 upgrade if the machine ever grows.

### 3c. Calendar (one click)

Say "what's on my calendar today?" (or run `make collect`) → macOS prompts for
**Calendar** access → allow Full Access. Google events come along free if your
Google account is added in Calendar.app (docs/archive/CALENDAR.md).

### ✅ Verify Stage 3

```bash
make doctor          # screenpipe + moondream now pass
make voice           # "what am I holding?" → camera light blinks, he answers
                     # "what was on my screen an hour ago?" → recall answers
```

---

## Stage 4 — Hands: n8n on Hostinger (~20 min, mostly in n8n's UI)

Full walkthrough: **docs/archive/N8N-SETUP.md**. Summary:

1. `openssl rand -hex 32` → `.env`: `N8N_WEBHOOK_SECRET=...` and
   `.env`: `N8N_BASE_URL=https://<your-n8n-domain>`
2. In n8n, create ONE header-auth credential: name `X-Friday-Secret`, value =
   that same hex. Reuse it on every webhook below.
3. Build your five action workflows (Webhook trigger, POST, header auth →
   your logic → respond). Then register them in **config/tools.yaml** —
   uncomment the template block, set each `webhook_path` and risk
   (`safe` runs instantly, `confirm` asks "Shall I proceed, sir?",
   `pin` demands your spoken PIN, `blocked` refuses).
   Suggested five: content_pipeline, review_request, lead_followup,
   booking_reminders (all `confirm`), morning_report (`safe`).
   Assistant set (added 2026-08-11): job_search, lead_finder, draft_replies
   (all `safe` — they only read and draft), send_outreach (`confirm`),
   make_call (`pin` — an AI voice speaking as you is the highest-risk tool;
   wire Twilio/Vapi/Retell inside n8n, creds never touch the Mac).
4. Tip: workflows receive `{"utterance": "<what you said>"}` as the body —
   parse client names, dates, etc. from it in n8n.

### Metrics for the Mission Board (docs/archive/DASHBOARD.md)

Four more small n8n workflows that RETURN JSON arrays of numbers
(instagram, bookyourslot, leads, n8n-health) → uncomment their paths in
**config/metrics.yaml** → `make collect` → the board fills.

### Content Studio (docs/archive/CONTENT-STUDIO.md) — the Instagram section

Two workflows:
- **Trending** (`/webhook/content-trending`): pulls trending reels/hooks in
  your niche (IG hashtag search, TikTok Creative Center, an LLM ranking step —
  your choice) → responds with the items array.
- **Publish** (`/webhook/content-publish`): receives `{id,title,url,caption}`
  → posts to Instagram. For the IG connection inside n8n you need a **Meta
  developer app**: developers.facebook.com → Create App (Business) → add
  Instagram Graph API → link your IG **Professional** account (it must be
  connected to a Facebook Page) → generate a long-lived access token with
  `instagram_content_publish` permission → use n8n's Facebook Graph API node.
  Note: the Graph API needs media at a public URL; for reels it's often easier
  to have this workflow push into your scheduler (Metricool/Buffer/Meta
  Business Suite) instead — the Studio doesn't care which.
- `.env`: `CONTENT_TRENDING_WEBHOOK=` and `CONTENT_PUBLISH_WEBHOOK=`

### ✅ Verify Stage 4

```bash
curl -s -X POST "$N8N_BASE_URL/webhook/<path>" -H "X-Friday-Secret: <hex>" -d '{}'
make voice   # "run my content pipeline" → "Shall I proceed, sir?" → "yes"
             # then: "what did you do today?" → he reads it back
```
Studio screen → PULL TRENDS → cards appear. That's Phase 4 + Studio acceptance.

---

## Stage 5 — Phone (~5 min) — docs/MOBILE.md — ⚙️ SERVE DONE 2026-08-11

Done on the Mac side (all three listeners live + `.env` voice lines written):
```
https://lohiths-macbook-pro.tail8d7575.ts.net       -> 127.0.0.1:8787  (app)
http://lohiths-macbook-pro.tail8d7575.ts.net        -> 127.0.0.1:8787  (app, no-TLS fallback)
https://lohiths-macbook-pro.tail8d7575.ts.net:8443  -> 127.0.0.1:7880  (voice signalling)
LIVEKIT_BIND_IP=100.118.41.0  LIVEKIT_NODE_IP=100.118.41.0
VOICE_WS_URL=wss://lohiths-macbook-pro.tail8d7575.ts.net:8443
```

✅ **Cert RESOLVED 2026-08-11**: the earlier "acme order status: invalid"
failures were the tailnet's HTTPS Certificates toggle — Lohith enabled it,
the cert minted on the next try, and **https:// is verified working (200)**
over the tailnet. Funnel (public URL, same hostname) started the same day.

Your half, on the iPhone: Tailscale app ON (it's been off 2 weeks) → Safari →
`http://lohiths-macbook-pro.tail8d7575.ts.net/chat` (https once certs mint) →
Share → **Add to Home Screen**. Voice tab → CONNECT → allow mic; `make run`
must be active on the Mac for voice.

### Access gate + open world (added 2026-08-11, Lohith's call)

The app now carries its own lock: **APP_ACCESS_KEY** in `.env` (set, 32 hex).
Every request without it gets 401 — required before any public exposure.
First visit on a new device: append `?key=<the key from .env>` to the URL
once; the server swaps it for a year-long cookie and cleans the URL. APIs can
send `Authorization: Bearer <key>` instead. Unset the var to return to the
open localhost/tailnet behavior.

Public access (beyond the tailnet) rides **Tailscale Funnel** on the same
hostname — requires the HTTPS cert (see the known issue above) and the
funnel node attribute (admin console prompts on first `tailscale funnel`).
The Voice tab stays tailnet-only regardless: WebRTC media doesn't traverse
funnel.

---

## Stage 6 — Your voice (~30 min recording + ~1 h Colab)

```bash
uv run python -m scripts.record_wakeword                    # "Hey Friday"
uv run python -m scripts.record_wakeword --phrase standdown # the offline kill
```
Then train per **voice/wakeword/README.md** (openWakeWord's Colab, free tier),
drop the two `.onnx` files into `voice/wakeword/`, and `.env`:
```
WAKE_MODEL_PATH=voice/wakeword/wake.onnx
KILL_MODEL_PATH=voice/wakeword/standdown.onnx
```
Tune `WAKE_THRESHOLD` (up if false wakes, down if he misses you across the
room). This arms the REAL wake phrase and the spoken offline "stand down".

---

## Stage 7 — The demo

```bash
make eval            # router >= 90% (33 cases) — first real-model run
make test-scenario   # the machine already rehearses your exact script
```

Then **docs/DEMO-SCRIPT.md**: one continuous take, 8 steps, no keyboard.
Three clean runs in a row = v1 COMPLETE. Log failed attempts in its table.

---

## Key reference card

| .env variable | Where it comes from | Stage |
|---|---|---|
| ANTHROPIC_API_KEY | console.anthropic.com → API Keys | 1 |
| DEEPGRAM_API_KEY | console.deepgram.com → API Keys | 1 |
| CARTESIA_API_KEY / TTS_VOICE_ID | play.cartesia.ai → API Keys / Voices | 1 |
| LIVEKIT_API_SECRET | `openssl rand -hex 32` | 1 |
| FRIDAY_PIN | you pick 4 digits | 1 |
| SCREENPIPE_EXCLUDE | you list apps | 3 |
| N8N_BASE_URL / N8N_WEBHOOK_SECRET | your Hostinger n8n / openssl | 4 |
| CONTENT_TRENDING_WEBHOOK / CONTENT_PUBLISH_WEBHOOK | your n8n workflows | 4 |
| LIVEKIT_BIND_IP / LIVEKIT_NODE_IP / VOICE_WS_URL | `tailscale ip -4` / serve | 5 |
| APP_ACCESS_KEY | `openssl rand -hex 16` (set 2026-08-11) — the app's lock | 5 |
| WAKE_MODEL_PATH / KILL_MODEL_PATH | your trained models | 6 |

Permissions macOS will ask for, once each: Microphone (voice), Accessibility
(hotkey), Screen Recording (screenpipe), Camera (sight), Calendars (calendar).

Sanity check after ANY stage: `make doctor`. It never lies, sir.

---

## Cost & call budget (optimized 2026-08-11)

What one spoken turn costs. Every LLM call goes through one chokepoint
(`adapters/llm.py think()`), so this table is the whole story:

| Call | Model | When it fires | ~Cost |
|---|---|---|---|
| Route | Haiku ($1/$5 per MTok) | every turn, output capped at 16 tokens | ~$0.0006 |
| Reply | Sonnet ($3/$15; intro $2/$10 to 2026-08-31) | every turn | ~$0.004 |
| Fact extraction | Haiku | ONLY turns that hint at a fact (see below) | ~$0.0005 |
| Ops select / vision classify / calendar parse | Haiku | only on those routes | ~$0.0005 |
| Morning brief | Sonnet | once per day | ~$0.004 |

Typical turn ≈ **half a cent**. At a heavy 100 turns/day that's ~$12–15/mo —
comfortably inside the $30/mo budget.

Built-in optimizations (no knobs to turn):
- **Extraction gate**: "what's the weather?" used to fire a Haiku
  fact-extraction call anyway. Now a fact-hint check (digits, "remember",
  "my X is", "i like/never/always"...) skips the call entirely on fact-free
  turns — that's most of them. Permissive by design: a wasted cheap call
  beats a lost memory.
- **Output caps**: replies are ≤3 spoken sentences, so `max_tokens` is 512
  everywhere and 16 on the router (its answer is one word). Runaway output
  can't run up the bill.
- **Metrics report** speaks from a deterministic digest — zero LLM calls.
- **History cap**: the chat prompt carries recent turns only, not the whole
  session.

Deliberately NOT done (so nobody "adds" them later):
- **Prompt caching**: the persona is ~450 tokens; Anthropic only caches
  prefixes ≥1024 tokens on Sonnet (≥4096 on Haiku), below that
  `cache_control` silently does nothing. Revisit only if the system prompt
  ever grows past ~4KB.
- **A regex pre-router**: would save ~$1.50/mo and add a second routing
  brain to maintain. Not worth it.

If cost ever spikes: `make doctor` won't show it — check
console.anthropic.com → Usage. The knobs are `MODEL_SMART` / `MODEL_FAST`
in `.env` (dropping MODEL_SMART to `claude-haiku-4-5` cuts ~80% of spend at
the price of a duller Friday).
