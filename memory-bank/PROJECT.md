# PROJECT — What Jarvis Life OS Is

> **Current state & decisions (2026-09-28):** read `docs/SYSTEM-REVIEW.md` first — what runs, what is broken, keep/pause/remove, open decisions.

## Vision
An always-available, voice-first personal OS for Lohith's life and business. Wake it with
"Wake up, Daddy's home", talk naturally, and it answers from his real knowledge (leos-brain
vault), remembers everything it's told (mem0), runs his business automations (n8n on
Hostinger), recalls anything he's seen on screen (screenpipe), sees through the camera on
demand (moondream), and operates the web (browser-use). Full Jarvis persona: "sir", dry
British wit, replies <= 3 spoken sentences.

## Non-negotiables
- 100% local brain (MacBook, Apple Silicon 16GB). Cloud only for LLM/STT/TTS API calls.
- Secret: no git, no remotes, no telemetry beyond LLM APIs. Snapshots to ~/jarvis-snapshots/.
- Kill controls work OFFLINE: "stand down", "camera off", menu-bar toggle, hotkey ⌥⌘J.
- Destructive actions require spoken confirmation ("Shall I proceed, sir?").

## Feature List (complete system)
1. Wake-phrase activation + continuous ACTIVE session, DORMANT = nothing streams
2. Natural interruptible voice conversation (LiveKit + Deepgram + Cartesia)
3. Vault brain: answers from leos-brain; appends notes to vault inbox by voice
4. Long-term fact memory: "remember X" survives restarts (mem0 + Chroma)
5. Ops by voice: top-5 n8n workflows with risk-gated confirmation
6. Screen recall: "what was that page I saw yesterday?" (screenpipe, fully local)
7. Camera sight on demand: "what am I holding?" (single frame, moondream, auto-release)
8. Web hands: browser-use tasks in a dedicated Chrome profile
9. Audit trail: "what did you do today, sir?"
10. Morning brief spoken on first wake of the day
11. Spoken PIN for highest-risk actions
12. Auto-start on login, crash-restart (launchd)

## End Goal — "The Demo" (definition of DONE)
One continuous take, no cuts, defined in docs/DEMO-SCRIPT.md:
wake -> vault question -> remember a fact -> run an n8n workflow with spoken confirm ->
screen recall -> camera question -> "stand down". When that demo runs clean 3 times in a
row, v1 is complete.
