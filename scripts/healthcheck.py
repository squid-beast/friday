"""friday · scripts/healthcheck.py

--quick (SessionStart hook): env keys present + local port probes. Prints WARN
lines but ALWAYS exits 0 — a broken service must never block a session.
Full mode (make doctor): real API auth pings; one line per failure, exit 1.
"""

import argparse
import asyncio
import socket
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from config.settings import get_settings
from config.tools import load_tools

_VOICE_KEYS = ("deepgram_api_key", "cartesia_api_key")
_LLM_KEYS = {"anthropic": "anthropic_api_key", "openai": "openai_api_key",
             "openrouter": "openrouter_api_key", "gemini": "google_api_key"}
_HTTP_TIMEOUT_S = 5.0
_PHONE_VOICE_AGENT = Path.home() / "Library/LaunchAgents/com.friday.livekit.plist"


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def quick() -> list[str]:
    settings = get_settings()
    llm_key = _LLM_KEYS.get(settings.llm_provider.strip().lower())  # compatible: optional
    keys = ((llm_key,) if llm_key else ()) + _VOICE_KEYS
    warns = [f"WARN: {f.upper()} not set (.env)" for f in keys if not getattr(settings, f)]
    if not settings.tts_voice_id:
        warns.append("WARN: TTS_VOICE_ID not set — Cartesia default voice will be used")
    if settings.wake_require_verifier and not settings.wake_verifier_path:
        warns.append("WARN: strict owner-voice wake is on, but WAKE_VERIFIER_PATH is missing")
    if _PHONE_VOICE_AGENT.exists() and not port_open("127.0.0.1", 7880):
        warns.append("WARN: phone voice is on but LiveKit is down — start Docker Desktop "
                      "(or `make phone-voice-off`)")
    return warns


async def check_llm() -> None:
    """A real one-word completion on the ACTIVE provider (LLM_PROVIDER)."""
    from adapters.llm import think

    await think("Reply with the single word: pong", fast=True, max_tokens=8)


async def check_deepgram() -> None:
    key = get_settings().deepgram_api_key
    if not key:
        raise ValueError("DEEPGRAM_API_KEY not set")
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        response = await client.get(
            "https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {key}"}
        )
        response.raise_for_status()


async def check_cartesia() -> None:
    key = get_settings().cartesia_api_key
    if not key:
        raise ValueError("CARTESIA_API_KEY not set")
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        response = await client.get(
            "https://api.cartesia.ai/voices",
            headers={"X-API-Key": key, "Cartesia-Version": "2024-06-10"},
        )
        response.raise_for_status()


async def check_n8n() -> None:
    """Reachable + authorised (REST API with the key), and every registered
    adapters.n8n tool has an ACTIVE workflow serving its path as POST. Read-only:
    business workflows are listed, never touched."""
    settings = get_settings()
    if not settings.n8n_base_url:
        return  # n8n not configured — not a failure
    if not settings.n8n_api_key:
        raise ValueError("N8N_API_KEY not set — can't verify workflows")
    base = f"{settings.n8n_base_url.rstrip('/')}/api/v1/workflows?limit=250"
    workflows, cursor = [], ""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        while True:
            response = await client.get(
                base + (f"&cursor={cursor}" if cursor else ""),
                headers={"X-N8N-API-KEY": settings.n8n_api_key},
            )
            response.raise_for_status()
            page = response.json()
            workflows += page.get("data", [])
            cursor = page.get("nextCursor") or ""
            if not cursor:
                break
    served = _active_post_hooks(workflows)
    missing = [t.name for t in load_tools() if t.adapter.startswith("adapters.n8n")
               and _hook_key(t.webhook_path) not in served]
    if missing:
        raise ValueError(f"no active POST workflow for tool(s): {', '.join(missing)}")


def _hook_key(webhook_path: str) -> str | None:
    """The webhook-node path adapters.n8n will actually hit, or None when the
    tool's path isn't a production webhook URL (it would 404)."""
    path = webhook_path.lstrip("/")
    return path.removeprefix("webhook/").strip("/") if path.startswith("webhook/") else None


def _active_post_hooks(workflows: list[dict]) -> set[str]:
    hooks = set()
    for wf in workflows:
        if not wf.get("active"):
            continue
        for node in wf.get("nodes", []):
            params = node.get("parameters", {})
            methods = params.get("httpMethod", "GET")  # n8n's default is GET
            methods = methods if isinstance(methods, list) else [methods]
            if node.get("type") == "n8n-nodes-base.webhook" and "POST" in methods:
                hooks.add(str(params.get("path", "")).strip("/"))
    return hooks


async def check_chroma() -> None:
    from adapters.memory import recall

    await recall("healthcheck ping")  # embedded store: open + query round trip


# Off on purpose (their launchd agents were removed 2026-09-29) — reported, never failed.
DARK_BY_DESIGN = ("INFO: dark by design — screen recall (screenpipe) + camera sight (moondream);"
                  " phone voice is on demand (`make phone-voice`)")

CHECKS: dict[str, Callable[[], Awaitable[None]]] = {
    "llm": check_llm,
    "deepgram": check_deepgram,
    "cartesia": check_cartesia,
    "n8n": check_n8n,
    "chroma": check_chroma,
}


async def full() -> list[str]:
    failures = []
    for name, check in CHECKS.items():
        try:
            await check()
        except Exception as exc:
            failures.append(f"FAIL: {name}: {exc}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="no network beyond localhost")
    args = parser.parse_args(argv)
    if args.quick:
        try:
            warns = quick()
        except Exception as exc:
            warns = [f"WARN: settings invalid: {' '.join(str(exc).split())}"]
        for line in [*warns, DARK_BY_DESIGN]:
            print(line)
        return 0
    failures = asyncio.run(full())
    for line in [*failures, DARK_BY_DESIGN]:
        print(line)
    print("all clear, sir" if not failures else f"{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
