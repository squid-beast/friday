"""friday · brain/mood.py

Purpose: Emotion engine — persistent affect dimensions, event triggers from the
audit/session log, a per-turn mood line injected into the system prompt.
Design: docs/EMOTIONS.md.
Filled in: Phase 2 (core state + triggers), Phase 6 (TTS rate mapping, weary/late-night)
Contains when implemented: MoodState (pydantic), update(event),
current_disposition() -> str, decay logic, data/mood.json persistence.

DO NOT add code outside the assigned phase. See PLAN.md.
"""
