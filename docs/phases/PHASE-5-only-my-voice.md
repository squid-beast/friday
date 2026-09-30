# Phase 5 — "Only my voice" access (owner-voice verification)

> **Goal:** only *your* voice is accepted — at wake **and** during conversation — layered on top of
> the access key and (Phase 6) Cloudflare Access. Uses your recordings. **Must land before the
> system goes public.**

## Why it's close
The verifier is already scaffolded — `wake_verifier_path`, `wake_verifier_threshold` (0.18),
`wake_require_verifier` (fail-closed) in settings, and `adapters/wakeword.py`. Today it's
**wake-only and untrained**. This phase trains it and extends it to every spoken turn.

## Build
1. **Train the wake model** ("Hey Friday") from your positives/negatives → set `WAKE_MODEL_PATH`
   (replaces the "Hey Jarvis" fallback).
2. **Train the owner-voice verifier** from your enrollment recordings (speaker-embedding model,
   e.g. ECAPA / Resemblyzer → a `.joblib` threshold classifier). Set `WAKE_VERIFIER_PATH` and
   `WAKE_REQUIRE_VERIFIER=true` (fail closed).
3. **Per-utterance verification (the new bit):** extend verification from the wake frame to
   *conversation turns* in the `voice/` layer — each turn's speaker embedding is checked against your
   enrolled voiceprint; a non-match gets a polite refusal, not execution. (README currently calls
   this a "future feature"; this phase delivers it.) Keep it a `voice/` concern — **no graph edit**.
4. **Layering (never voice-only on the public net):** Cloudflare Access (identity, Phase 6) →
   `APP_ACCESS_KEY` (device) → owner-voice (biometric factor) → PIN (destructive). Anti-replay:
   short session windows; destructive actions always re-gate with the spoken PIN even for your voice.

## Recording spec
| Purpose | What | How much |
|---|---|---|
| Wake model — "Hey Friday" | you saying "Hey Friday" | ~50 clips: near/far, quiet/loud, rooms |
| Wake negatives | you talking, NOT the phrase | ~25 clips |
| Verifier enrollment | you speaking varied sentences (reuse wake positives + a 2–5 min read) | 2–5 min |
`scripts/record_wakeword.py` guides the wake capture. Mono WAV/MP3, low noise.

## [LOHITH INPUT]
The recordings above; choose `WAKE_VERIFIER_THRESHOLD` after testing (start 0.18); decide
fail-closed vs fail-open if the verifier is unavailable (recommend closed).

## Tests (TDD — safety code, test first)
A non-owner sample is rejected at wake AND mid-conversation; your sample is accepted;
verifier-unavailable behaves per the fail-closed setting; the offline kill path is unaffected
(import-isolation test still passes).

## Acceptance
Someone else says the wake phrase → refused; you → accepted; a stranger speaking mid-session →
refused; destructive action still needs the PIN. Then `/wrap` + snapshot.
