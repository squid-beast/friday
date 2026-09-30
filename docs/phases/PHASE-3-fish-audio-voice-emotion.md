# Phase 3 — Fish Audio voice + real emotion (the "not a robot" phase)

> **Goal:** Friday speaks in your chosen **cloned target voice** via Fish Audio, and its existing
> **mood engine actually reaches the voice** — audible warmth, worry, dry wit — using S1's inline
> emotion tags. Cartesia stays as an instant fallback. **Adapter + persona change — no graph edit.**

## Why it's clean
Fish ships an official LiveKit plugin — `livekit-plugins-fishaudio`
(`from livekit.plugins import fishaudio; tts = fishaudio.TTS()`, reads `FISH_API_KEY`) — which drops
into your `adapters/tts.py` seam exactly like Cartesia. And you **already have a mood engine**
(`docs/EMOTIONS.md`, wired into `config/persona.md`, `mood_path` in settings) — this phase gives that
mood a *voice*.

## Build
1. **Clone the target voice (one-time, in Fish Audio):** upload a clean **15–60s** sample of the
   voice you want Friday to have (S1 clones from ~15s). Fish returns a voice/model id →
   `FISH_MODEL_ID`.
2. **`config/settings.py`:** `tts_provider: str = "cartesia"`, `fish_api_key`, `fish_model_id`,
   `fish_emotion_enabled: bool = True`. Add them to `.env.example`.
3. **`adapters/tts.py`:** branch `get_tts()` on `tts_provider` → `fishaudio.TTS(model=fish_model_id)`
   when `fishaudio`, else Cartesia. Same factory contract — nothing else changes.
4. **Emotion → voice.** S1 understands inline tags like `(happy) (worried) (whisper) (chuckling)`
   (50+). Pick one safe path:
   - **Persona-driven (simplest):** add a short block to `config/persona.md` telling Friday to emit
     ONE fitting emotion tag at the start of a reply, **only** when the mood engine says so, and
     **never** during kill/emergency/stress. Cartesia strips tags; Fish renders them.
   - **Adapter filter (most control):** a tiny pre-synthesis helper maps current mood → one tag,
     prepended before Fish synthesis. Keep it in the tts/voice layer, not the graph.
5. **Safety gate (TDD — test first):** tags are suppressed on safety/kill/confirmation lines and
   when mood = stressed/emergency. The 3-sentence cap and all confirmation rules are unchanged
   (mirrors persona's "no humor during emergencies").

## [LOHITH INPUT]
`FISH_API_KEY`; the **target-voice sample** (the voice Friday should have, not your own);
confirm `TTS_PROVIDER=fishaudio`.

## Tests (same session)
Tag-injection respects the safety gate (no tags on kill/emergency lines); Cartesia fallback strips
tags cleanly; missing `FISH_API_KEY` raises in the adapter.

## Acceptance
`make voice` → Friday answers in the cloned voice; good news sounds pleased, "you skipped sleep,
sir" sounds concerned; a kill/confirm line is flat and tag-free; `TTS_PROVIDER=cartesia` still
talks. Then `/wrap` + snapshot.

> **Note:** Fish is TTS, not a chat brain — conversation reasoning stays with the Phase 2 LLMs; Fish
> gives those words a human, emotional *voice*. A future HF Inference Endpoint for self-hosted
> fish-speech swaps in behind this same `adapters/tts.py` seam.
