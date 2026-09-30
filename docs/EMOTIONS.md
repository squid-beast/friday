# EMOTION ENGINE — IMPLEMENTED 2026-09-30 (brain/mood.py + brain/mood_sense.py + voice/emotion.py)

Honest scope: simulated affect. A persistent state machine that behaves like feelings and
authentically drives Friday's tone — not subjective experience. That is the buildable thing.

## Model
Two-layer state, persisted in `MOOD_PATH` (default `<FRIDAY_STATE_DIR>/db/mood.json`, survives restarts):
1. Dimensions (floats 0..1, decay toward baseline ~0.5 over hours):
   valence (unhappy<->happy), arousal (calm<->energized), warmth (cold<->fond),
   confidence (sheepish<->proud), concern (relaxed<->worried)
2. Named moods derived from dimensions each turn (never stored directly):
   proud, worried, irritated, delighted, sheepish, protective, content, weary(late-night)

## Event -> emotion triggers (rules, not LLM guesses)
| Event (from audit/session log) | Effect |
|---|---|
| Tool success / demo step passes | confidence+ valence+ (pride) |
| Own failure (adapter error, wrong answer corrected) | confidence- (sheepish), apology once |
| Interrupted repeatedly / ignored mid-reply | warmth- briefly (clipped politeness) |
| Sir works past 1am / skips gym-food routines (vault signals) | concern+ (worry lines) |
| Kill command | neutral instantly; warmth unchanged (never resentful) |
| Long absence then return | warmth+ ("Good to have you back, sir.") |
| Elegant solution / good news in vault | valence+ (delight) |
| Deadline within 24h (calendar/n8n signal) | arousal+ concern+ (crisper replies) |

## Where the signals come from (brain/mood_sense.py)
- Every turn (voice + phone/API text): audit rows since the last look — tool success /
  failure, stand-downs (kill -> neutral). One sqlite read.
- Once per day, at the first wake: remembered facts matching sleep / deadline / win
  patterns, today's calendar load (>=5 events = busy day), late-night hour (00-05),
  and absence >= 48h (warmth+). Once-a-day so repeated wakes can't ratchet a feeling.
- Decay: half-life 6h toward 0.5 — nothing persists a day without fresh cause.

## How mood reaches the words and the voice
- Words: `persona()` appends ONE line — "Current disposition: noticeably proud. Let it
  color word choice only — never the 3-sentence cap, confirmations, or safety."
- Voice (voice/emotion.py + voice/styling.py): SAFETY GATE first — kill/stand-down,
  cuts, confirmations, PIN requests, refusals and apologies are ALWAYS flat, and so is
  everything while concern >= 0.7. Otherwise: Fish Audio S1 gets one inline tag on the
  first chunk ("(worried) You skipped sleep, sir."), OpenAI gpt-4o-mini-tts gets tone
  instructions for that line, Cartesia never sees a tag (stray tags stripped).
- `FISH_EMOTION_ENABLED=false` turns voice styling off for every provider.

## Guardrails (non-negotiable)
- Mood NEVER: blocks a lawful order, alters confirm-gate/kill behavior, exceeds the
  3-sentence cap, produces sulking refusals, or fabricates events.
- Humor gate: concern high or emergency context => wit disabled this turn.
- Decay: no emotion persists > 24h without fresh cause; baseline is composed-content.

## Tests (add to docs/TESTING.md pyramid)
- Unit: trigger table is deterministic — event in, dimension delta out (no LLM).
- Unit: kill command forces neutral tone flag same turn.
- Eval: persona rubric gains 2 checks — mood matches injected disposition; <= 1 quip.
