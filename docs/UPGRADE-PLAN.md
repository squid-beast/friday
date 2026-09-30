# Friday — v2 Upgrade Plan (Models · Emotion · Buddy · Public Deploy · Voice-Only-Me)

> **Status:** plan only — **no code was changed to write this.** Work ONE phase per session; end
> every session with `/wrap`. Every guardrail in `CLAUDE.md` / `CONVENTIONS.md` still holds
> (adapter-only changes, `tools.yaml` for capabilities, offline kill path untouched, files ≤200
> lines, tests in the same session, `make lint && make test` before done, `make snapshot`).
>
> **📁 Now split into one file per phase under `docs/phases/`** (index: `docs/phases/README.md`).
> New numbering — **Phase 1 = code cleanup + integrations**, then 2 = models · 3 = Fish voice +
> emotion · 4 = buddy/actions · 5 = only-my-voice · 6 = public deploy. **The `docs/phases/` files are
> the canonical execution briefs.** This file stays the overview: decisions (§0), the two honest
> flags (§1), the seams map (§2), and the security model (§4). The detailed "PHASE 8–12" sections
> further below are retained for reference only — they map to the new files 2/3/4/6/5 respectively.

---

## 0. Your locked decisions (from this session)

| Question | Decision |
|---|---|
| Public reach | **Cloudflare Tunnel → `friday.paypilotlabs.com`** (Mac stays the brain) |
| Auth | **Voice + passkey/key (layered)**; destructive stays PIN; kill stays offline |
| Fish Audio | **Fish Audio cloud API** (TTS + voice clone) |
| Recordings feed | **Wake model (Hey Friday)** + **Owner-voice verifier** + **clone a *different* target voice** for Friday |

---

## 1. Read this first — two honest flags

**A. The "secret / no-git / local-only" rule is already broken and you're now reversing it on purpose.**
`PLAN.md §0` and `CLAUDE.md` say *no git, nothing leaves the Mac*. But the repo already has a
remote: `origin → github.com/squid-beast/friday.git`. You're now asking for GitHub + a public
subdomain, which is a deliberate reversal. That's fine — but decide it explicitly:
- **Make the GitHub repo PRIVATE.** This repo references your vault path, your persona, your n8n
  tool map, and your automation surface. `.gitignore` already excludes `.env`, `data/`, and build
  output (good), so **no secrets are committed** — but the *shape* of your life-OS is sensitive.
  Private repo, and rotate any key that ever sat in a commit.
- Update `CLAUDE.md`/`PLAN.md §0` to say "private GitHub remote allowed; secrets never committed"
  so future sessions stop treating git as forbidden and fighting themselves.

**B. You are about to put an action-taking agent — with your vault, n8n, browser, and Mac
control — on the public internet.** Voice can be **replayed or spoofed**. That's why you chose
layered auth, and the plan keeps it strict:
- Public URL sits **behind Cloudflare Access** (email OTP / passkey) — a stranger never reaches the
  app at all.
- The existing **`APP_ACCESS_KEY` cookie** stays as a second layer.
- **Owner-voice verification** is a *factor*, never the sole gate (Phase 12).
- **Destructive tools stay PIN-gated**; **kill phrases stay 100% offline** (unchanged).
- The **vault, screen recall, and camera never leave the Mac** — the tunnel exposes the app
  surface, not the filesystem.

Order matters: **do the auth phases (12) before you flip the tunnel public (11).**

---

## 2. Where each change lands (the seams — no graph edits)

Everything below is an **adapter + config + `tools.yaml` + tests** change. `brain/graph.py` routing
is never touched (CONVENTIONS rule). This is why the system can absorb all of it safely.

| Goal | File(s) that change | Untouched |
|---|---|---|
| Call other models | `adapters/llm.py`, `config/settings.py`, `.env.example` | graph, nodes |
| Fish Audio voice + emotion | `adapters/tts.py`, `config/persona.md`, `config/settings.py` | graph, nodes |
| More real actions | `config/tools.yaml` (+ n8n workflows) | graph, adapters (reuse `n8n.py`) |
| Public deploy | new `launchd/com.friday.tunnel.plist`, `docs/DEPLOY.md`, Cloudflare dashboard | app code |
| Only-my-voice | `adapters/wakeword.py` (verifier), `config/settings.py`, `voice/` turn-gate | kill path |

---

## PHASE 8 — Call other models (multi-provider LLM)

**Goal:** Friday can use Anthropic *and* OpenAI, Gemini, OpenRouter, or a local/OpenAI-compatible
endpoint — chosen by env, optionally per-task by the router. Anthropic stays the default.

**Why it's clean:** `adapters/llm.py` already has exactly two seams — `get_llm()` (the LiveKit
voice-pipeline component) and `think()` (the one-shot brain helper). Both are provider-swappable in
one file, which is the whole point of the adapter pattern.

**Build:**
1. `config/settings.py`: add `llm_provider: str = "anthropic"`, `openai_api_key`, `google_api_key`,
   `openrouter_api_key`, `llm_base_url: str = ""` (for OpenRouter/local). Keep `model_smart` /
   `model_fast`.
2. `adapters/llm.py`:
   - `think()` → branch on `llm_provider`. Anthropic stays as-is. For OpenAI-compatible providers
     (OpenAI, OpenRouter, Groq, local vLLM/Ollama) use one `AsyncOpenAI(base_url=…, api_key=…)`
     path — a single branch covers all of them. Gemini via its SDK or its OpenAI-compat endpoint.
     *(Optional: back `think()` with LiteLLM to collapse all providers into one call — but a hand
     branch keeps deps minimal; your call.)*
   - `get_llm()` (voice pipeline) → for non-Anthropic, return LiveKit's **OpenAI plugin with a
     custom `base_url`/`api_key`** (`livekit.plugins.openai`), which is the supported way to point
     the realtime pipeline at other providers. Anthropic keeps its native plugin.
3. **Per-task model (optional, powerful):** let the router pick — cheap/fast model for routing &
   classification, smart model for reasoning, a specific model for coding answers. This stays inside
   `think(..., model=…)`; **no graph change** (the router already exists).

**[LOHITH INPUT]:** the API keys for whichever providers you want (`OPENAI_API_KEY`,
`GOOGLE_API_KEY`, `OPENROUTER_API_KEY`), and which model is `MODEL_SMART` / `MODEL_FAST`.

**Tests (same session):** `tests/unit` — fake each provider client; assert `think()` returns text
and honors `llm_provider`; assert missing-key raises `ValueError` (settings never raises, adapters
do). No network.

**Accept:** flip `LLM_PROVIDER=openai` (or `openrouter`) in `.env`, `make voice` — a spoken turn
answers; `make doctor` pings the active provider; `make lint && make test` green.

---

## PHASE 9 — Fish Audio voice + real emotion (the "not a robot" phase)

**Goal:** Friday speaks in your chosen **cloned target voice** via Fish Audio, and its **existing
mood engine actually reaches the voice** — audible warmth, worry, dryness — using S1's inline
emotion tags. Cartesia stays as an instant fallback.

**Why it's clean:** Fish ships an official LiveKit plugin — `livekit-plugins-fishaudio`
(`from livekit.plugins import fishaudio; tts = fishaudio.TTS()`, reads `FISH_API_KEY`). It drops
straight into your `adapters/tts.py` seam exactly like Cartesia. And you **already have a mood
engine** (`docs/EMOTIONS.md`, wired into `persona.md`) — this phase gives that mood a *voice*.

**Build:**
1. **Clone the target voice (one-time, in Fish Audio):** upload a clean **15–60s** sample of the
   voice you want Friday to have (S1 clones from ~15s). Fish returns a **voice/model id** →
   `FISH_MODEL_ID`.
2. `config/settings.py`: `tts_provider: str = "cartesia"`, `fish_api_key`, `fish_model_id`,
   `fish_emotion_enabled: bool = True`.
3. `adapters/tts.py`: branch `get_tts()` on `tts_provider` → `fishaudio.TTS(model=fish_model_id)`
   when `fishaudio`, else Cartesia. Same factory contract — nothing else changes.
4. **Emotion → voice.** S1 understands inline tags like `(happy) (worried) (whisper) (chuckling)`
   (50+). Two safe ways to drive them, pick one:
   - **Persona-driven (simplest):** add a short block to `config/persona.md` telling Friday to emit
     ONE fitting emotion tag at the start of a reply, *only* when the mood engine says so, and
     **never** during kill/emergency/stress. Cartesia path strips tags; Fish path renders them.
   - **Adapter filter (most control):** a tiny pre-synthesis helper maps the current mood state →
     one tag, prepended before Fish synthesis. Keep it in the tts/voice layer, not the graph.
5. **Safety gate (TDD — write the test first):** emotion tags are suppressed when the reply is a
   safety/kill/confirmation line or when mood = stressed/emergency. The 3-sentence cap and all
   confirmation rules are unchanged. This mirrors the persona rule "no humor during emergencies."

**[LOHITH INPUT]:** `FISH_API_KEY`; the **target-voice sample** (the voice Friday should have);
confirm `TTS_PROVIDER=fishaudio`.

**Tests (same session):** tag-injection respects the safety gate (no tags on kill/emergency lines);
Cartesia fallback strips tags cleanly; missing `FISH_API_KEY` raises in the adapter.

**Accept:** `make voice` — Friday answers in the cloned voice; a good-news turn sounds pleased, a
"you skipped sleep, sir" turn sounds concerned; a kill/confirm line is flat and tag-free; drop
`TTS_PROVIDER=cartesia` and it still talks.

**Note on "general conversations via Fish on Hugging Face":** Fish is a **TTS/voice** model, not a
chat brain. Conversation reasoning stays with Phase 8's LLMs; Fish gives those words a human,
emotional *voice*. (If you truly want to self-host fish-speech on an HF Inference Endpoint later, it
swaps in behind the same `adapters/tts.py` seam — but cloud API is the right start for a 16GB Mac.)

---

## PHASE 10 — Buddy behaviors + real actions

**Goal:** Friday *does things* and *feels like a companion*, not a demo. Most of this already
exists as scaffolding — this phase turns it on.

**Actions (n8n-first — CLAUDE.md rule):** your `config/tools.yaml` already lists real capabilities
(`job_search`, `review_draft`, `lead_intake`, plus the commented `send_outreach` = confirm,
`make_call` = pin). To make actions real:
1. **Activate each workflow in the n8n editor** and fill its real `webhook_path` in `tools.yaml`.
2. Keep the risk policy: read/find/draft = `safe`; anything that **sends/posts** = `confirm`;
   calls in your name = `pin`. No graph edits — the ops node discovers tools from YAML.
3. Add new actions the buddy should have as **one n8n workflow + one YAML line** each (e.g.,
   "text my mum I'll call later" = confirm, "add to today's plan" = safe).

**Buddy / companion layer (mostly built — verify + enrich):**
- **Proactive check-ins:** `integrations/reminders.py` + the morning brief + the caring wake
  question already exist. Confirm they fire on schedule (launchd) and that answers are written to
  runtime memory (mem0 + vault inbox).
- **Continuity = care:** persona already carries the thread across days ("the Rust project on
  Tuesday, sir…"). Ensure `memory_writer` is persisting those facts so callbacks are real, not
  invented.
- **Emotional memory:** let the mood engine read recent context (sleep, deadlines, wins) so warmth
  and worry are grounded in what actually happened.

**[LOHITH INPUT]:** activate the 3–5 n8n workflows and paste their webhook paths into `tools.yaml`;
list any new actions you want as a buddy.

**Accept:** a `safe` action runs by voice end-to-end; a `confirm` action asks "Shall I proceed,
sir?" and obeys a spoken yes; `make_call` demands the PIN; "what did you do today, sir?" reads the
audit log; a proactive check-in fires unprompted.

---

## PHASE 11 — Public deploy: `friday.paypilotlabs.com` via Cloudflare Tunnel

**Goal:** reach Friday from anywhere (no Tailscale needed), on your own subdomain, behind strong
auth. **The Mac stays the brain** — the tunnel is a secure front door, not a re-host.

**Do this phase LAST, after Phase 12 auth is armed.**

**Build:**
1. **GitHub:** confirm the `squid-beast/friday` repo is **private**; confirm `.env` and `data/` are
   gitignored (they are). Commit code + docs only. GitHub is version control / backup / deploy
   config — **not** where Friday runs.
2. **Add `paypilotlabs.com` to Cloudflare** (nameservers or a subdomain zone). *(paypilotlabs.com
   currently resolves elsewhere — moving DNS or delegating the subdomain to Cloudflare is the
   [LOHITH INPUT] step.)*
3. **cloudflared on the Mac:** `brew install cloudflared`; `cloudflared tunnel login`;
   `cloudflared tunnel create friday`; config maps `friday.paypilotlabs.com → http://127.0.0.1:8787`
   (your existing dashboard port); `cloudflared tunnel route dns friday friday.paypilotlabs.com`.
4. **launchd:** add `com.friday.tunnel.plist` (mirror the other 8 agents) so the tunnel auto-starts
   and crash-restarts. Document install in `docs/DEPLOY.md`.
5. **Cloudflare Access (Zero Trust):** put an Access policy on `friday.paypilotlabs.com` = your email
   OTP / passkey. This is the "passkey/key" layer — a stranger is stopped at Cloudflare, before the
   app. Keep the `APP_ACCESS_KEY` cookie behind it as layer 2.

**[LOHITH INPUT]:** Cloudflare account + `paypilotlabs.com` on Cloudflare; run the four cloudflared
commands; set the Access policy to your identity.

**Accept:** from your phone on **cellular, Tailscale OFF**: `friday.paypilotlabs.com` prompts
Cloudflare Access → app loads → a chat turn answers → "stand down" typed on the phone still cuts a
home session. A logged-out stranger never gets past Access.

**Keep Tailscale too** — it's the safe internal path and a fallback if you ever disable the public
tunnel.

---

## PHASE 12 — "Only my voice" access (owner-voice verification)

**Goal:** only *your* voice is accepted — at wake **and** during conversation — layered on top of
Access + the app key. Uses your recordings.

**Why it's close:** the verifier is already scaffolded — `wake_verifier_path`,
`wake_verifier_threshold` (0.18), `wake_require_verifier` (fail-closed) in settings, and
`adapters/wakeword.py`. Today it's **wake-only and untrained**. This phase trains it and extends it
to every spoken turn.

**Build:**
1. **Train the wake model** ("Hey Friday") from your positives/negatives → set `WAKE_MODEL_PATH`
   (replaces the "Hey Jarvis" fallback).
2. **Train the owner-voice verifier** from your enrollment recordings (speaker-embedding model, e.g.
   ECAPA/Resemblyzer → a `.joblib` threshold classifier). Set `WAKE_VERIFIER_PATH` and
   `WAKE_REQUIRE_VERIFIER=true` (fail closed).
3. **Per-utterance verification (the new bit):** extend verification from the wake frame to
   *conversation turns* in the `voice/` layer — each incoming turn's speaker embedding is checked
   against your enrolled voiceprint; a non-match gets a polite refusal, not execution. README
   currently calls this a "future feature"; this phase delivers it. Keep it a `voice/` concern, not
   a graph edit.
4. **Layering (never voice-only on the public net):** Cloudflare Access (identity) → `APP_ACCESS_KEY`
   (device) → owner-voice (biometric factor) → PIN (destructive). Anti-replay: short session
   windows, and destructive actions always re-gate with the spoken PIN even for your voice.

**[LOHITH INPUT]:** the recordings (spec in §3); choose `WAKE_VERIFIER_THRESHOLD` after testing
(start 0.18); decide fail-closed vs fail-open if the verifier is unavailable (recommend closed).

**Tests (TDD — safety code):** a non-owner sample is rejected at wake AND mid-conversation; your
sample is accepted; verifier-unavailable behaves per the fail-closed setting; offline kill path is
unaffected (import-isolation test still passes).

**Accept:** someone else says the wake phrase → refused; you → accepted; a stranger speaking
mid-session → refused; destructive action still needs the PIN.

---

## 3. Recording spec (what to send me / record with `scripts/record_wakeword.py`)

| Purpose | What to record | How much |
|---|---|---|
| **Wake model — "Hey Friday"** | You saying "Hey Friday" | ~50 clips across near/far, quiet/loud, different rooms |
| **Wake negatives** | You talking normally, NOT saying the phrase | ~25 clips |
| **Owner-voice verifier (enrollment)** | You speaking varied sentences (can reuse wake positives + a 2–5 min natural read) | 2–5 min total |
| **Target voice clone (Friday's voice)** | A clean **15–60s** sample of the *voice you want Friday to speak in* (NOT your own) | 1 clip, low noise |

Formats: mono WAV/MP3, minimal background noise. `scripts/record_wakeword.py` already guides the
wake capture. The target-voice sample goes to Fish Audio to mint `FISH_MODEL_ID`.

---

## 4. Security model (the layered picture)

```
Internet
   │
   ▼
Cloudflare Access  ──► identity gate (email OTP / passkey)   [stranger stops here]
   │
   ▼
Cloudflare Tunnel ──► friday.paypilotlabs.com → 127.0.0.1:8787 (your Mac)
   │
   ▼
APP_ACCESS_KEY cookie ──► device gate
   │
   ▼
Owner-voice verify ──► biometric factor (wake + per-turn)
   │
   ├─ safe action      → runs
   ├─ confirm action   → "Shall I proceed, sir?" (spoken yes)
   └─ destructive/call → spoken 4-digit PIN
   
Always local, never exposed: leos-brain vault · screen recall · camera · gestures
Always offline: "Stand Down", camera off, menu-bar kill, hotkey
```

Extra hardening worth doing: rotate any key ever committed; keep destructive tools PIN-gated even
for your own voice; consider a **read-only "away" mode** (when off home Wi-Fi, disable
`confirm`/`pin` tools entirely, allow chat + read-only); audit every tool call (already enforced via
`audit/log.py`).

---

## 5. Recommended order (security-first)

1. **Phase 8 — models** (low risk, immediate flexibility).
2. **Phase 9 — Fish voice + emotion** (the biggest "buddy feel" jump; self-contained).
3. **Phase 10 — actions + buddy** (activate n8n, proactivity).
4. **Phase 12 — only-my-voice** (train wake + verifier; must precede public exposure).
5. **Phase 11 — public deploy** (flip the tunnel **only after** auth is armed).

Each phase is shippable on its own and ends with `/wrap` + `make snapshot`.

---

## 6. [LOHITH INPUT] master checklist

| Phase | You provide |
|---|---|
| 8 | `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `OPENROUTER_API_KEY` (whichever) · pick `MODEL_SMART`/`FAST` |
| 9 | `FISH_API_KEY` · the target-voice sample (15–60s) · confirm `TTS_PROVIDER=fishaudio` |
| 10 | Activate 3–5 n8n workflows · paste webhook paths into `tools.yaml` · list new buddy actions |
| 11 | `paypilotlabs.com` on Cloudflare · run the 4 cloudflared commands · set the Access policy · confirm GitHub repo private |
| 12 | Wake + negative + enrollment recordings · verifier threshold · fail-closed choice |

---

## 7. Guardrails that do NOT change (from CLAUDE.md / CONVENTIONS.md)

- New capability = `tools.yaml` entry + one adapter. **`graph.py` routing is never edited.**
- Vendor SDKs only in `adapters/` and `integrations/`. Brain imports interfaces.
- Files ≤200 lines. `make lint && make test` before finishing. Tests in the same session; safety
  code is TDD (failing test first).
- n8n-first: if it can be an n8n workflow, it is one. Core code is only voice/brain/memory/vision/
  safety.
- Secrets only via `config/settings.py` (`.env`), never committed, never logged.
- Every tool call goes through `audit/log.py`. Kill phrases stay offline. `make snapshot` is the
  undo. End every session with `/wrap`.
