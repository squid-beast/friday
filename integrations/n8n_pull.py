"""friday · integrations/n8n_pull.py

The generic platform collector: n8n holds every platform credential and does
the API talking; the Mac just PULLS metrics from authed n8n webhooks listed in
config/metrics.yaml. Adding a platform = one n8n workflow + one YAML line.

Each webhook must return JSON: [{"platform": "...", "metric": "...",
"value": 123, "note": "optional"}, ...]
"""

import logging
from pathlib import Path

import httpx
import yaml

from config.settings import get_settings
from integrations import store

log = logging.getLogger(__name__)

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "metrics.yaml"
_TIMEOUT_S = 15.0


def sources(path: Path = _CONFIG) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [str(p) for p in (data.get("metric_webhooks") or [])]


async def collect(*, record=store.record, config: Path = _CONFIG) -> int:
    """Pull every configured webhook; a dead one is logged and skipped, never fatal."""
    settings = get_settings()
    paths = sources(config)
    if not paths or not settings.n8n_base_url or not settings.n8n_webhook_secret:
        return 0  # nothing configured yet — not an error
    written = 0
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        for webhook in paths:
            url = settings.n8n_base_url.rstrip("/") + (
                webhook if webhook.startswith("/") else f"/{webhook}"
            )
            try:
                response = await client.post(
                    url, json={}, headers={"X-Friday-Secret": settings.n8n_webhook_secret}
                )
                response.raise_for_status()
                rows = response.json()
            except Exception:
                log.warning("metrics pull failed for %s", webhook, exc_info=True)
                continue
            for row in rows if isinstance(rows, list) else []:
                try:
                    record(
                        str(row["platform"]), str(row["metric"]),
                        float(row["value"]), str(row.get("note", "")),
                    )
                    written += 1
                except (KeyError, TypeError, ValueError):
                    log.warning("malformed metric row from %s: %r", webhook, row)
    return written
