# Phase 4 — Buddy behaviors + real actions

> **Goal:** Friday *does things* and *feels like a companion*, not a demo. Much of this is already
> scaffolded — this phase turns it on. **n8n-first: capabilities are workflows + `tools.yaml`, never
> new graph routing.**

## Actions (n8n-first — `CLAUDE.md` rule)
`config/tools.yaml` already lists real capabilities (`job_search`, `review_draft`, `lead_intake`,
plus commented `send_outreach` = confirm, `make_call` = pin). To make actions real:
1. **Activate each workflow in the n8n editor** and fill its real `webhook_path` in `tools.yaml`
   (this clears the Phase 1 `TODO` placeholders).
2. Keep the risk policy: read/find/draft = `safe`; anything that **sends/posts** = `confirm`; calls
   in your name = `pin`. The ops node discovers tools from YAML — **no graph edit**.
3. Add each new buddy action as **one n8n workflow + one YAML line** (e.g., "text my mum I'll call
   later" = confirm, "add to today's plan" = safe).

## Buddy / companion layer (mostly built — verify + enrich)
- **Proactive check-ins:** `integrations/reminders.py` + the morning brief + the caring wake
  question already exist. Confirm they fire on schedule (launchd) and write answers to runtime
  memory (mem0 + vault inbox).
- **Continuity = care:** persona already carries the thread across days ("the Rust project on
  Tuesday, sir…"). Ensure `memory_writer` persists those facts so callbacks are real, not invented.
- **Emotional memory:** let the mood engine read recent context (sleep, deadlines, wins) so warmth
  and worry are grounded in what actually happened.

## [LOHITH INPUT]
Activate the 3–5 n8n workflows and paste their webhook paths into `tools.yaml`; list any new actions
you want Friday to have as a buddy.

## Tests (same session)
A fake n8n adapter proves: `safe` runs immediately; `confirm` parks on the interrupt gate and
resumes only on a spoken yes; `pin` demands the PIN. Audit rows are written for each.

## Acceptance
A `safe` action runs by voice end-to-end; a `confirm` action asks "Shall I proceed, sir?" and obeys
a spoken yes; `make_call` demands the PIN; "what did you do today, sir?" reads the audit log; a
proactive check-in fires unprompted. Then `/wrap` + snapshot.
