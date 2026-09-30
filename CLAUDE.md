# Friday
Personal voice-first AI assistant ("Friday") for Lohith. SECRET project — private GitHub remote only (squid-beast/friday), secrets never committed, never reference it outside this folder.

@memory-bank/PROJECT.md
@memory-bank/PROGRESS.md
@memory-bank/CONVENTIONS.md
@memory-bank/DECISIONS.md

## Rules
- Read PLAN.md before any work. Implement only the phase asked.
- Python 3.12, uv, ruff, type hints, pydantic at boundaries.
- Vendor SDKs only inside adapters/. Brain imports interfaces only.
- reference/langgraph-src/ is READ-ONLY upstream source for study. Never import from it; always pip-install langgraph.
- Secrets only via config/settings.py (.env). Never hardcode or log them.
- Every tool execution goes through audit/log.py.
- New capability = tools.yaml entry + one adapter. Never edit graph routing for it.
- n8n-FIRST RULE: if a capability can be an n8n workflow, build it in n8n and register it in tools.yaml — core code is ONLY for voice, brain, memory, vision, safety. Post-v1 backlog lives in README.md (routes: CORE/N8N/HYBRID).
- Files <= 200 lines. make lint && make test must pass before finishing.
- TESTS ARE PART OF THE FEATURE (docs/TESTING.md): unit tests in the same session as the code; safety code (kill switches, confirm gate, path allowlists) is TDD — failing test first; router/prompt changes require updating the eval set; never skip/delete a failing test to pass a phase.
- Git: private remote allowed; commit/push only when Lohith asks; never commit .env*, data/, keys. Safety net = make snapshot.
- End EVERY session by running /wrap.
