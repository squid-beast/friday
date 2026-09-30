"""friday · integrations/automations.py

Reads the n8n execution history for the HUD Automations card via the public
REST API (X-N8N-API-KEY). READ-ONLY: business workflows are displayed, never
touched. One row per ACTIVE workflow (its latest run, fetched per workflow so a
busy scheduler can't push the others off the card) + today's counts by status
(paged back to local midnight). Times are local; a run from another day shows
its date. A failure is reported as {"error": ...} — never "no runs yet".
"""

import asyncio
from datetime import UTC, datetime

import httpx

from config.settings import get_settings

_TIMEOUT = 12.0
_PAGE = 250  # n8n's max page size
_MAX_PAGES = 4  # ponytail: counts cap at 1000 runs/day; raise if a workflow ever outruns it
_EPOCH = datetime.fromtimestamp(0, UTC)


def _client() -> httpx.AsyncClient | None:
    s = get_settings()
    if not s.n8n_base_url or not s.n8n_api_key:
        return None
    return httpx.AsyncClient(base_url=s.n8n_base_url.rstrip("/"), timeout=_TIMEOUT,
                             headers={"X-N8N-API-KEY": s.n8n_api_key})


def _status(row: dict) -> str:
    return row.get("status") or ("success" if row.get("finished") else "running")


def _local(iso: str | None) -> datetime | None:
    """n8n timestamps are UTC ISO-8601 ('...Z'); the HUD speaks local time."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


async def _get(client: httpx.AsyncClient, path: str, **params) -> dict:
    response = await client.get(path, params=params)
    response.raise_for_status()
    return response.json()


async def _workflows(client: httpx.AsyncClient) -> list[dict]:
    rows, cursor = [], None
    while True:
        data = await _get(client, "/api/v1/workflows", limit=_PAGE,
                          **({"cursor": cursor} if cursor else {}))
        rows += data.get("data", [])
        cursor = data.get("nextCursor")
        if not cursor:
            return rows


async def _today_counts(client: httpx.AsyncClient, today) -> tuple[dict, dict]:
    """(counts by status, runs per workflow) for the local day, newest first."""
    counts: dict[str, int] = {}
    per_wf: dict[str, int] = {}
    cursor = None
    for _ in range(_MAX_PAGES):
        data = await _get(client, "/api/v1/executions", limit=_PAGE,
                          **({"cursor": cursor} if cursor else {}))
        for row in data.get("data", []):
            started = _local(row.get("startedAt"))
            if started is None or started.date() != today:
                return counts, per_wf  # newest-first: the rest are older than today
            counts[_status(row)] = counts.get(_status(row), 0) + 1
            wid = str(row.get("workflowId", ""))
            per_wf[wid] = per_wf.get(wid, 0) + 1
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return counts, per_wf


async def recent() -> dict:
    """One row per active workflow (latest run) + today's counts (local day)."""
    client = _client()
    if client is None:
        return {"runs": [], "counts": {}, "armed": False}
    today = datetime.now().astimezone().date()
    try:
        async with client:
            workflows = [w for w in await _workflows(client) if w.get("active")]
            latest = await asyncio.gather(*(
                _get(client, "/api/v1/executions", workflowId=w["id"], limit=1)
                for w in workflows))
            counts, per_wf = await _today_counts(client, today)
    except httpx.HTTPStatusError as exc:
        return {"runs": [], "counts": {}, "armed": True,
                "error": f"n8n answered {exc.response.status_code}"}
    except Exception:
        return {"runs": [], "counts": {}, "armed": True, "error": "n8n unreachable"}
    runs = []
    for wf, page in zip(workflows, latest, strict=True):
        rows = page.get("data", [])
        if not rows:
            continue
        row, wid = rows[0], str(wf["id"])
        started = _local(row.get("startedAt"))
        stopped = _local(row.get("stoppedAt")) or started
        runs.append({
            "_at": started or _EPOCH, "id": str(row.get("id", "")),
            "name": wf.get("name", "workflow"), "status": _status(row),
            "when": _when(stopped, today), "today": per_wf.get(wid, 0),
        })
    runs.sort(key=lambda r: r["_at"], reverse=True)
    return {"runs": [{k: v for k, v in r.items() if k != "_at"} for r in runs],
            "counts": counts, "armed": True}


def _when(moment: datetime | None, today) -> str:
    if moment is None:
        return ""
    return moment.strftime("%H:%M") if moment.date() == today else moment.strftime("%b %d %H:%M")
