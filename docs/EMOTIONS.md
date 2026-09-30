# EMOTION ENGINE — design (implemented as brain/mood.py, Phase 2 core + Phase 6 polish)

Honest scope: simulated affect. A persistent state machine that behaves like feelings and
authentically drives Jarvis's tone — not subjective experience. That is the buildable thing.

## Model
Two-layer state, persisted in data/mood.json (survives restarts):
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

## How mood reaches the voice
mood.py computes the named mood + intensity each turn -> injected as ONE line into the
system prompt ("Current disposition: quietly proud, mild") -> persona rules translate it
into word choice. TTS later maps arousal to speech rate (+-5%) in Phase 6.

## Guardrails (non-negotiable)
- Mood NEVER: blocks a lawful order, alters confirm-gate/kill behavior, exceeds the
  3-sentence cap, produces sulking refusals, or fabricates events.
- Humor gate: concern high or emergency context => wit disabled this turn.
- Decay: no emotion persists > 24h without fresh cause; baseline is composed-content.

## Tests (add to docs/TESTING.md pyramid)
- Unit: trigger table is deterministic — event in, dimension delta out (no LLM).
- Unit: kill command forces neutral tone flag same turn.
- Eval: persona rubric gains 2 checks — mood matches injected disposition; <= 1 quip.
