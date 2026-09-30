# GOING LIVE — autonomy, risk, and the payoff

What "deployed" means for Jarvis, what he may do without asking, exactly when
he asks, how risky each surface is, and the gate to run before trusting him.
Facts below verified 2026-08-15 (all four test levels + doctor green).

## 1 · The permission story — why prompts happen, and when they stop

Two different kinds of "asking" exist. Don't confuse them:

**macOS permission prompts (one-time each, then never again):**

| Prompt | For | State |
|---|---|---|
| Microphone | voice conversation | ✅ granted |
| Accessibility | ⌥⌘J kill hotkey | ✅ granted |
| Screen Recording | screenpipe recall | ✅ granted |
| Calendars | calendar tool | ✅ granted (Terminal context) |
| Camera | single-frame sight | prompts on first look |

If a prompt ever repeats, something is crash-looping and respawning — that is
a bug, not policy (the one real case: screenpipe's audio pipeline; fixed by
running `--disable-audio`, which recall never needed). `make doctor` after any
prompt storm.

**Jarvis's own confirmations (deliberate, per-action, forever):**
these are the product's safety design, not friction. The risk ladder in
`config/tools.yaml` decides:

| Risk | Behavior | Today's tools |
|---|---|---|
| `safe` | runs instantly, audited | calendar read, metrics, review_draft, vendor_report |
| `confirm` | "Shall I proceed, sir?" → spoken/typed yes | calendar booking, job_search, lead_intake, maintenance_request, browser tasks |
| `pin` | your spoken 4-digit PIN | (reserved: make_call) |
| `blocked` | refuses | anything you park |

**The knob is yours**: edit `risk:` per tool. Moving a tool to `safe` removes
its ask — do that only for actions you'd let run while you sleep. The asks are
what make "control my system" safe to grant.

## 2 · What runs fully unattended today

- 7 launchd agents (dashboard/API, killswitch, voice worker, LiveKit,
  screenpipe, moondream, hourly metrics) — reboot-proof, crash-restarting.
- The public URL behind APP_ACCESS_KEY; tailnet app + voice.
- Hourly metrics collection; morning brief on first wake.
- Every `safe` tool, every vault/memory/chat/recall answer.

What NEVER runs unattended: sends/posts/bookings (`confirm`), calls (`pin`),
Instagram publishing (two deliberate taps in Studio), browser actions
(`confirm`), anything with an unset secret (fails closed).

## 3 · Risk register — honest, with mitigations

| # | Risk | Blast radius | Mitigation in place | Residual |
|---|---|---|---|---|
| 1 | APP_ACCESS_KEY leaks (public URL) | full brain: chat, vault answers, confirm-TAP of n8n tools, audit read | 401 wall, HttpOnly cookie, constant-time compare; rotate = one openssl + restart; `tailscale funnel --https=443 off` kills the public door in seconds | MEDIUM — treat the key like a house key |
| 2 | Voice impersonation triggers actions | business workflows fire | confirm gates need an explicit yes; PIN for the worst; negations veto; eager "yes" ≠ PIN | LOW |
| 3 | n8n tool does real-world damage | emails/SMS to real people | all sends are `confirm`; workflows inactive until you activate each; n8n creds never on the Mac | MEDIUM — review each workflow before activating |
| 4 | Camera/screen privacy | what the lens/screen sees | offline cuts ("camera off"/"screen off", control files, checked inside adapters), SCREENPIPE_EXCLUDE, single-frame camera by construction | LOW |
| 5 | API spend runaway | money | max_tokens caps (512/16), extraction gate, no per-turn waste; ~$12–15/mo at 100 turns/day; console.anthropic.com → Usage | LOW |
| 6 | Prompt injection via content (trending items, web pages) | wrong drafts/posts | Studio requires your two taps to publish; browser tasks confirm-gated, 15-step cap; nothing auto-publishes | LOW-MEDIUM |
| 7 | Mac is a single point of failure | everything | snapshots to ~/jarvis-snapshots (every change), launchd self-heal; secrets only in .env | accepted by design |
| 8 | Kill path fails when internet is down | can't stop him | kill phrases are LOCAL (no network imports — subprocess-proven), hotkey, menu bar; daemon state truthful | LOW |

Rollback for anything: `make snapshot` history + `tailscale funnel off` +
unset APP_ACCESS_KEY/rotate + `launchctl unload` per agent.

## 4 · The payoff — what you get for that risk

- One assistant, five mouths: mic, menu bar, phone PWA, public URL, raw API
  (`POST /api/ask` from anything you build next).
- Business hands: jobs searched, leads answered in seconds, drafts waiting,
  reports on demand — each a spoken sentence away, each audited.
- Total recall: screen history, long-term facts, your vault, calendar.
- A dashboard that tells the truth (chips read real config, not hope).
- All of it on your hardware, your tailnet, your keys — subscription-free.

## 5 · The pre-live gate — run before trusting any change

```bash
make lint && make test-unit && make test-integration && make test-scenario
export ANTHROPIC_API_KEY=$(grep '^ANTHROPIC_API_KEY=' .env | cut -d= -f2) && make eval
make doctor
```

| Level | Proves | 2026-08-15 result |
|---|---|---|
| lint | style + smells | ✅ |
| L1 unit (440) | every branch incl. gates, kill paths, UI rules | ✅ |
| L2 integration (11) | real sqlite/chroma wiring | ✅ |
| L4 scenario (4) | the demo, rehearsed end-to-end incl. confirm gate | ✅ (caught a real drift this run — fixed) |
| L3 eval (33 vs real Haiku) | router ≥90% accuracy | ✅ |
| doctor | every live service answers | ✅ all clear |

The gate caught two issues on this very run (a leaked env var in the test
harness and a stale demo rehearsal) — that is what it is for. Never skip it,
never ship red.

## 6 · Live-fire checklist before "v1 done"

1. Activate the 5 n8n workflows in the editor; say "run the vendor report".
2. HuggingFace token → camera model loads → "what am I holding?"
3. A spoken session: wake → vault → remember → restart → recall.
4. docs/DEMO-SCRIPT.md — one take, 8 steps, three times clean.
