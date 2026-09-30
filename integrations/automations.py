"""friday · integrations/automations.py

Reads the n8n execution history for the HUD Automations card via the public
REST API (X-N8N-API-KEY). recent() normalizes runs (name, status, when);
detail() fetches one run's output for the tap-to-expand. Everything degrades to
empty on any failure — the HUD never breaks because the VPS is unreachable.
"""

import time

import httpx

from config.settings import get_settings

_TIMEOUT = 12.0


def _client() -> tuple[httpx.AsyncClient, str] | None:
    s = get_settings()
    if not s.n8n_base_url or not s.n8n_api_key:
        return None
    base = s.n8n_base_url.rstrip("/")
    return httpx.AsyncClient(base_url=base, timeout=_TIMEOUT,
                             headers={"X-N8N-API-KEY": s.n8n_api_key}), base


def _status(row: dict) -> str:
    return row.get("status") or ("success" if row.get("finished") else "running")


async def recent(limit: int = 15) -> dict:
    """Recent runs + today's counts by status. Empty dict shape when unconfigured."""
    made = _client()
    if made is None:
        return {"runs": [], "counts": {}, "armed": False}
    client, _ = made
    try:
        async with client:
            rows = (await client.get("/api/v1/executions",
                                     params={"limit": limit})).json().get("data", [])
            names = await _names(client)
    except Exception:
        return {"runs": [], "counts": {}, "armed": True}
    today = time.strftime("%Y-%m-%d", time.localtime())
    counts: dict[str, int] = {}
    runs = []
    for row in rows:
        st = _status(row)
        started = str(row.get("startedAt", ""))[:10]
        if started == today:
            counts[st] = counts.get(st, 0) + 1
        runs.append({
            "id": str(row.get("id", "")),
            "name": names.get(str(row.get("workflowId", "")), "workflow"),
            "status": st,
            "when": _clock(row.get("stoppedAt") or row.get("startedAt")),
        })
    return {"runs": runs, "counts": counts, "armed": True}


async def _names(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        data = (await client.get("/api/v1/workflows",
                                 params={"limit": 200})).json().get("data", [])
        return {str(w["id"]): w.get("name", "workflow") for w in data}
    except Exception:
        return {}


def _clock(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S")
        return time.strftime("%H:%M", t)
    except (ValueError, TypeError):
        return ""


async def detail(execution_id: str) -> dict:
    """One run's outcome for tap-to-expand — status + a short data preview."""
    made = _client()
    if made is None or not execution_id:
        return {"found": False}
    client, _ = made
    try:
        async with client:
            row = (await client.get(f"/api/v1/executions/{execution_id}",
                                    params={"includeData": "true"})).json()
    except Exception:
        return {"found": False}
    data = row.get("data", {})
    preview = str(data)[:800] if data else "no output captured"
    return {"found": True, "status": _status(row),
            "when": _clock(row.get("stoppedAt")), "preview": preview}
