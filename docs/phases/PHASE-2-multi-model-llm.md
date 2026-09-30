# Phase 2 — Call other models (multi-provider LLM)

> **Goal:** Friday can use Anthropic *and* OpenAI, Gemini, OpenRouter, or a local/OpenAI-compatible
> endpoint — chosen by env, optionally per-task by the router. Anthropic stays the default.
> **Adapter-only change — no `graph.py` edit.**

## Why it's clean
`adapters/llm.py` has exactly two seams: `get_llm()` (the LiveKit voice-pipeline component) and
`think()` (the one-shot brain helper). Both are provider-swappable in one file — the whole point of
the adapter pattern.

## Build
1. **`config/settings.py`:** add `llm_provider: str = "anthropic"`, `openai_api_key`,
   `google_api_key`, `openrouter_api_key`, `llm_base_url: str = ""` (OpenRouter/local). Keep
   `model_smart` / `model_fast`.
2. **`adapters/llm.py`:**
   - `think()` → branch on `llm_provider`. Anthropic stays as-is. For OpenAI-compatible providers
     (OpenAI, OpenRouter, Groq, local vLLM/Ollama) use one `AsyncOpenAI(base_url=…, api_key=…)`
     path — a single branch covers all. Gemini via its SDK or its OpenAI-compat endpoint.
     *(Optional: back `think()` with LiteLLM to collapse providers into one call — a hand branch
     keeps deps minimal; your call.)*
   - `get_llm()` (voice pipeline) → for non-Anthropic, return LiveKit's **OpenAI plugin with a
     custom `base_url`/`api_key`** (`livekit.plugins.openai`) — the supported way to point the
     realtime pipeline at other providers. Anthropic keeps its native plugin.
3. **Per-task model (optional):** let the router pass `think(..., model=…)` — fast model for
   routing/classification, smart model for reasoning, a specific model for coding. Stays inside
   `think()`; **no graph change**.
4. Update `.env.example` with the new vars (per Phase 1's contract rule).

## [LOHITH INPUT]
`OPENAI_API_KEY` / `GOOGLE_API_KEY` / `OPENROUTER_API_KEY` (whichever you want); pick
`MODEL_SMART` / `MODEL_FAST`.

## Tests (same session)
`tests/unit` — fake each provider client; assert `think()` returns text and honors `llm_provider`;
assert missing key raises `ValueError` in the adapter (settings never raises). No network.

## Acceptance
Flip `LLM_PROVIDER=openai` (or `openrouter`) in `.env`, `make voice` → a spoken turn answers;
`make doctor` pings the active provider; `make lint && make test` green. Then `/wrap` + snapshot.
