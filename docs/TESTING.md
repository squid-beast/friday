# TESTING RULES — mandatory, non-negotiable

Why this exists: agents fail in production for reasons normal apps don't — non-deterministic
LLM output, silent tool failures, drifting prompts. Industry consensus (agent testing pyramid):
most failures are caught by DETERMINISTIC tests on your own logic, not by testing the LLM.

## The Friday Testing Pyramid (bottom = most tests, run always)

### L1 — Unit tests (deterministic, no network, run on every change)
- EVERY adapter has unit tests with the vendor SDK mocked. Test: happy path, timeout,
  malformed response, auth failure.
- EVERY graph node tested with fakes from tests/fakes.py. LLM calls are faked with fixed
  outputs — we test OUR routing/state logic, not the model.
- Safety-critical units get exhaustive cases: local_intents matcher (every kill phrase +
  near-misses that must NOT trigger), confirm-gate (no "yes" => no execution), vault path
  allowlist (escape attempts must fail), tools.yaml risk parsing.
- Target: < 5s total. Command: make test-unit.

### L2 — Integration tests (real local services, no LLM)
- Graph + real SQLite checkpointer + real Chroma (docker) + fake LLM: state survives restart.
- n8n adapter against a mock HTTP server: secret header present, retry-once, timeout handling.
- screenpipe/camera adapters against recorded fixtures.
- Command: make test-integration (runs before ending any phase).

### L3 — Evals (LLM behavior, scored not asserted)
- Router eval: canned utterance set (grows every phase, min 30 by Phase 6). PASS >= 90%.
- Persona eval: 10 canned exchanges scored for: stays in character, <= 3 sentences, no
  secrets leaked. LLM-as-judge with a fixed rubric.
- Command: make eval. Run after any prompt/persona/router change — a prompt edit IS a
  code change and can regress silently.

### L4 — Scenario tests (end-to-end, scripted)
- Each DEMO-SCRIPT.md step has a scripted scenario test (text-in/text-out through the real
  graph, fake voice I/O). The demo is rehearsed by machine before it is rehearsed by you.
- Kill-path scenario runs with network DISABLED to prove offline guarantee.

## Hard rules (enforced by CLAUDE.md)
1. NO feature is "done" without: unit tests + updated eval set entry if it touches
   routing/prompts. Phase acceptance includes its tests passing.
2. Tests are written IN THE SAME session as the code, never "later".
3. A bug found by you = first write the failing test that reproduces it, then fix.
4. Never delete/skip a failing test to make a phase pass. Fix or explicitly log the
   decision in memory-bank/DECISIONS.md.
5. Safety code (kill switches, confirm gate, path allowlists) requires tests BEFORE
   implementation (TDD) — these are the ones that must never regress.
6. make test-unit green before /wrap. make test-integration + make eval green before
   declaring a phase complete.

## Avoiding "deployment" failures (here: daily-driver failures)
- Healthcheck-first startup: launchd starts nothing user-facing until healthcheck passes.
- Every adapter call has a timeout + a spoken fallback line ("I can't reach n8n, sir").
  A dead service must degrade to an apology, never a hang or crash.
- Audit log is the black box: every failure investigation starts there.
- Snapshot before every phase (make snapshot) = instant rollback without git.
- Weekly: run make eval + full scenario suite once, log results in PROGRESS.md.

## Coverage policy (Phase 7 audit: 93% total, all logic branches covered)
Run: uv run pytest tests/unit tests/integration tests/scenario --cov=. 
EVERY routing/gate/fallback branch is unit-covered. The ONLY sanctioned
exclusions are thin OS/vendor glue that requires live hardware or a GUI run
loop — each is exercised by daily use and fails loudly, never silently:
- adapters/calendar.py objc internals (_get_store/_events_between/_create — EventKit)
- adapters/camera.py _describe (Moondream client) — capture logic IS covered
- client/killswitch.py rumps callbacks + pynput hookup (menu bar; logic is 6 lines)
- voice/agent.py entrypoint (LiveKit runtime wiring; llm_node IS covered)
- __main__ blocks and serve_forever loops
Adding logic to any of these files means extracting it to a testable function
FIRST. New failure branches anywhere else must land with a test (see
tests/unit/test_fallbacks.py for the pattern).

## File layout
tests/
├── fakes.py            # FakeLLM, FakeVault, FakeMemory, FakeN8n, FakeScreenpipe
├── unit/               # test_<module>.py mirrors source tree
├── integration/        # test_checkpointing.py, test_n8n_contract.py, ...
└── evals/              # router_cases.yaml, persona_rubric.md, test_router_eval.py
