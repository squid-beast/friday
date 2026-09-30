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

import httpx

from config.settings import get_settings

_KEY_FIELDS = ("anthropic_api_key", "deepgram_api_key", "cartesia_api_key")
_HTTP_TIMEOUT_S = 5.0


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def quick() -> list[str]:
    settings = get_settings()
    warns = [f"WARN: {f.upper()} not set (.env)" for f in _KEY_FIELDS if not getattr(settings, f)]
    if not settings.tts_voice_id:
        warns.append("WARN: TTS_VOICE_ID not set — Cartesia default voice will be used")
    if settings.wake_require_verifier and not settings.wake_verifier_path:
        warns.append("WARN: strict owner-voice wake is on, but WAKE_VERIFIER_PATH is missing")
    if not port_open("127.0.0.1", 7880):
        warns.append("WARN: livekit down (docker compose up -d; console mode works without it)")
    return warns


async def check_anthropic() -> None:
    from adapters.llm import think

    await think("Reply with the single word: pong", fast=True)


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
    settings = get_settings()
    if not settings.n8n_base_url:
        return  # not configured until the Phase 4 table is filled — not a failure
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        response = await client.get(settings.n8n_base_url)
    if response.status_code >= 500:
        raise ValueError(f"n8n unhealthy: {response.status_code}")


async def check_chroma() -> None:
    from adapters.memory import recall

    await recall("healthcheck ping")  # embedded store: open + query round trip


# Off on purpose (their launchd agents were removed 2026-09-29) — reported, never failed.
DARK_BY_DESIGN = "INFO: dark by design — screen recall (screenpipe) + camera sight (moondream)"

CHECKS: dict[str, Callable[[], Awaitable[None]]] = {
    "anthropic": check_anthropic,
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
