"""friday · integrations/collect.py

The collection sweep: local health + every configured n8n platform pull.
Run by the hourly launchd timer, or by hand: uv run python -m integrations.collect
"""

import asyncio
import logging
import sys

from integrations import friday_health, n8n_pull, store

log = logging.getLogger(__name__)


async def calendar_count(*, record=store.record) -> int:
    """Today's event count for the board; silently skipped until Calendar permission."""
    try:
        from adapters.calendar import events_today

        events = await events_today()
    except Exception:
        log.warning("calendar count skipped", exc_info=True)
        return 0
    record("calendar", "events_today", len(events))
    return 1


async def run() -> int:
    written = friday_health.collect()
    written += await calendar_count()
    written += await n8n_pull.collect()
    return written


def main() -> int:
    written = asyncio.run(run())
    print(f"collected {written} metric points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
