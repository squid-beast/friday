# Friday — v2 Phases (index)

One file per phase. Work **one phase per session**; end each with `/wrap` + `make snapshot`.
Overview, decisions, and the security model live in `../UPGRADE-PLAN.md`.

| # | Phase | File | Why this order |
|---|-------|------|----------------|
| 1 | **Code cleanup + integrations** | `PHASE-1-cleanup-and-integrations.md` | Stabilize the base before adding anything |
| 2 | Multi-model LLM | `PHASE-2-multi-model-llm.md` | Low risk, immediate flexibility |
| 3 | Fish Audio voice + emotion | `PHASE-3-fish-audio-voice-emotion.md` | Biggest "buddy feel" jump; self-contained |
| 4 | Buddy behaviors + real actions | `PHASE-4-buddy-and-actions.md` | Activate n8n + proactivity |
| 5 | Only-my-voice (owner verification) | `PHASE-5-only-my-voice.md` | Must land before public exposure |
| 6 | Public deploy (Cloudflare Tunnel) | `PHASE-6-public-deploy.md` | Flip public LAST, after auth is armed |

**Guardrails on every phase (from `CLAUDE.md` / `CONVENTIONS.md`):** new capability =
`tools.yaml` + one adapter, never a `graph.py` edit · vendor SDKs only in `adapters/` and
`integrations/` · files ≤200 lines · tests in the same session, safety code TDD · n8n-first ·
secrets only via `config/settings.py` · every tool call through `audit/log.py` · kill phrases stay
offline · `make lint && make test` before done.
