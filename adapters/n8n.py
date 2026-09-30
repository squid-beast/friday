"""jarvis-life-os · adapters/n8n.py

Authed webhook caller to the Hostinger n8n. POST + X-Jarvis-Secret header,
10s timeout, exactly ONE retry — and only on transport errors or 5xx; a 4xx is
a config mistake and fails immediately. Returns the (truncated) response body
for the spoken summary.
"""

import httpx

from config.settings import get_settings

_TIMEOUT_S = 10.0
_BODY_CHARS = 500


def _require() -> tuple[str, str]:
    settings = get_settings()
    if not settings.n8n_base_url:
        raise ValueError("N8N_BASE_URL not set")
    if not settings.n8n_webhook_secret:
        raise ValueError("N8N_WEBHOOK_SECRET not set")
    return settings.n8n_base_url.rstrip("/"), settings.n8n_webhook_secret


async def call(webhook_path: str, payload: dict | None = None) -> str:
    base, secret = _require()
    url = base + (webhook_path if webhook_path.startswith("/") else f"/{webhook_path}")
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        for attempt in (1, 2):
            try:
                response = await client.post(
                    url, json=payload or {}, headers={"X-Jarvis-Secret": secret}
                )
                if response.status_code >= 500 and attempt == 1:
                    continue  # the one retry
                response.raise_for_status()
                return response.text[:_BODY_CHARS]
            except httpx.TransportError:
                if attempt == 2:
                    raise
    raise AssertionError("unreachable")  # loop always returns or raises


async def run(webhook_path: str, utterance: str) -> str:
    """Tool-contract wrapper: sir's utterance rides along as the webhook payload,
    so n8n workflows can parse specifics ("...for the Riverside client") themselves."""
    return await call(webhook_path, {"utterance": utterance})
