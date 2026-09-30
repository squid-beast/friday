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

## Event -> emotion triggers (rules, not LLM guesses) — as implemented (brain/mood.py)
| Signal (source) | Effect |
|---|---|
| Tool run succeeded (audit `tool` row) | confidence +0.08, valence +0.06 |
| Tool failed — Friday's own failure (`result` starts "failed") | confidence −0.15, valence −0.05 |
| Sir declined a gate ("aborted": no yes / wrong PIN) | nothing — not Friday's failure |
| Real kill: spoken "stand down" (`kill_command`) or daemon `spoken_kill` / `external_kill` | dimensions reset to 0.5, **warmth kept** (never resentful) |
| Session ended by silence / agent exit (`stand_down` other reasons) | nothing — the feeling just decays |
| Recent fact (≤ 48h) about poor sleep | concern +0.2, warmth +0.05 |
| Recent fact about a deadline | arousal +0.12, concern +0.15 |
| Recent fact about a win (shipped, got the offer, closed a deal…) | valence +0.15, warmth +0.05 |
| ≥ 5 calendar events today | arousal +0.1 |
| First wake between 00:00 and 05:00 | concern +0.15, arousal −0.1 |
| Back after ≥ 48h away | warmth +0.15 |

Planned, NOT implemented: interrupted/ignored mid-reply → warmth−; deadline signals from
calendar titles or n8n; "apology once" bookkeeping; routine tracking (gym/food).
Fact patterns are word-bounded ("won't" is not a win, "retired" is not tiredness) and
context signals apply at most once per day.

## Where the signals come from (brain/mood_sense.py)
- Every turn (voice + phone/API text): audit rows since the last look — tool success /
  failure and REAL kills only (see the table). One sqlite read.
- Once per day, at the first wake: facts remembered in the LAST 48 HOURS matching sleep /
  deadline / win patterns (facts are timestamped; older ones never fire), today's calendar
  load (>=5 events = busy day), late-night hour (00-05), and absence >= 48h (warmth+).
  Once-a-day so repeated wakes can't ratchet a feeling.
- Decay: half-life 6h toward 0.5 — nothing persists a day without fresh cause.

## How mood reaches the words and the voice
- Words: `persona()` appends ONE line — "Current disposition: noticeably proud. Let it
  color word choice only — never the 3-sentence cap, confirmations, or safety."
- Voice (voice/emotion.py + voice/styling.py): SAFETY GATE first — kill/stand-down,
  cuts, confirmations, PIN requests, refusals and apologies are ALWAYS flat, and so is
  everything while concern >= 0.7. Otherwise: Fish Audio S1 gets one inline tag on the
  first chunk ("(worried) You skipped sleep, sir."), OpenAI gpt-4o-mini-tts gets tone
  instructions for that line (a shared option: after any flat line, tone stays neutral
  until the session is back to listening), Cartesia never sees a tag (stray tags stripped).
  Dynamic tool-failure apologies ("I couldn't run X, sir.") are gated too.
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
