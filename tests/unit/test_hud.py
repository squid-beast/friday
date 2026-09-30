"""The HUD backend: weather in °F, system snapshot, spoken reminders store,
automations normalization (n8n mocked), and the aggregator's stable shape.
Network is mocked; nothing here touches the real VPS or a real vault."""

from pathlib import Path

import httpx
import pytest

import adapters.weather as weather_mod
from adapters import system
from adapters.weather import conditions
from config.settings import get_settings
from integrations import automations, reminders

_RealAsyncClient = httpx.AsyncClient


# --- weather: Fahrenheit + structured ---


def _weather_handler(request: httpx.Request) -> httpx.Response:
    if "geocoding" in str(request.url):
        assert request.url.params.get("name")  # a city was asked
        return httpx.Response(200, json={"results": [
            {"name": "Farmington Hills", "latitude": 42.5, "longitude": -83.4}]})
    assert request.url.params["temperature_unit"] == "fahrenheit"  # the ask
    return httpx.Response(200, json={
        "current": {"temperature_2m": 63.4, "apparent_temperature": 61.9,
                    "weather_code": 3, "wind_speed_10m": 8.0,
                    "relative_humidity_2m": 55},
        "daily": {"temperature_2m_max": [81.0], "temperature_2m_min": [61.0],
                  "precipitation_probability_max": [6]}})


async def test_conditions_returns_fahrenheit_card_data(monkeypatch) -> None:
    monkeypatch.setattr(weather_mod.httpx, "AsyncClient",
        lambda **k: _RealAsyncClient(transport=httpx.MockTransport(_weather_handler)))
    c = await conditions("Farmington Hills")
    assert c == {"city": "Farmington Hills", "condition": "overcast", "temp": 63,
                 "feels": 62, "high": 81, "low": 61, "rain": 6,
                 "humidity": 55, "wind": 8}


# --- system vitals ---


def test_system_snapshot_shape_and_bounds() -> None:
    snap = system.snapshot()
    assert set(snap) == {"cpu", "ram", "disk", "uptime_h"}
    assert all(0 <= snap[k] <= 100 for k in ("cpu", "ram", "disk"))


# --- spoken reminders ---


def test_reminder_add_strips_the_lead_in_and_persists(tmp_path: Path) -> None:
    db = tmp_path / "r.json"
    assert reminders.add("Remind me to call the vendor", db=db) == "call the vendor"
    reminders.add("buy more RAM", db=db)
    texts = [r["text"] for r in reminders.pending(db=db)]
    assert texts == ["call the vendor", "buy more RAM"]


def test_empty_reminder_is_not_stored(tmp_path: Path) -> None:
    db = tmp_path / "r.json"
    assert reminders.add("remind me to", db=db) == ""
    assert reminders.pending(db=db) == []


# --- automations (n8n mocked) ---


@pytest.fixture
def n8n(monkeypatch):
    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example")
    monkeypatch.setenv("N8N_API_KEY", "k")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _utc(hour: int, minute: int = 0, days_ago: int = 0) -> str:
    """A LOCAL wall-clock time today (or days ago) as n8n's UTC 'Z' string."""
    from datetime import UTC, datetime, timedelta

    local = datetime.now().astimezone().replace(hour=hour, minute=minute, second=0,
                                                microsecond=0) - timedelta(days=days_ago)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _run(eid: str, wid: str, started: str, status: str = "success") -> dict:
    return {"id": eid, "workflowId": wid, "status": status,
            "startedAt": started, "stoppedAt": started}


def _mock_n8n(monkeypatch, workflows, runs, status: int = 200) -> None:
    """A fake n8n REST API: workflows list, per-workflow latest, newest-first paging."""
    newest = sorted(runs, key=lambda r: r["startedAt"], reverse=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={})
        q = request.url.params
        if request.url.path.endswith("/workflows"):
            return httpx.Response(200, json={"data": workflows})
        if "workflowId" in q:
            mine = [r for r in newest if r["workflowId"] == q["workflowId"]]
            return httpx.Response(200, json={"data": mine[:1]})
        start, page = int(q.get("cursor", 0)), int(q.get("limit", 250))
        chunk = newest[start:start + page]
        more = start + page < len(newest)
        return httpx.Response(200, json={"data": chunk,
                                         "nextCursor": str(start + page) if more else None})

    monkeypatch.setattr(automations.httpx, "AsyncClient",
        lambda **k: _RealAsyncClient(transport=httpx.MockTransport(handler), **{
            x: k[x] for x in k if x in ("base_url", "headers", "timeout")}))


_WFS = [{"id": "7", "name": "Vendor Report", "active": True},
        {"id": "9", "name": "Reminder Scheduler", "active": True},
        {"id": "3", "name": "Old Archived Flow", "active": False}]


async def test_one_row_per_active_workflow_local_time_and_dates(n8n, monkeypatch) -> None:
    from datetime import datetime, timedelta

    _mock_n8n(monkeypatch, _WFS, [
        _run("5", "9", _utc(11, 5)), _run("4", "9", _utc(11, 0)),
        _run("1", "7", _utc(9, 0, 1), "error"),  # Vendor Report last ran YESTERDAY
        _run("0", "3", _utc(8, 0)),  # inactive workflow: never a row
    ])
    out = await automations.recent()
    assert "error" not in out and out["counts"] == {"success": 3}
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%b %d")
    assert out["runs"] == [
        {"id": "5", "name": "Reminder Scheduler", "status": "success", "when": "11:05",
         "today": 2},
        {"id": "1", "name": "Vendor Report", "status": "error", "when": f"{yesterday} 09:00",
         "today": 0},
    ]


async def test_a_busy_scheduler_cannot_push_other_workflows_off(n8n, monkeypatch) -> None:
    monkeypatch.setattr(automations, "_PAGE", 15)  # 41 runs today -> 3 pages
    busy = [_run(f"s{i}", "9", _utc(10, i % 60)) for i in range(40)]
    _mock_n8n(monkeypatch, _WFS, [*busy, _run("v1", "7", _utc(1, 0))])
    out = await automations.recent()
    assert [r["name"] for r in out["runs"]] == ["Reminder Scheduler", "Vendor Report"]
    assert out["runs"][0]["today"] == 40 and out["counts"] == {"success": 41}


async def test_recent_reports_n8n_errors_instead_of_hiding_them(n8n, monkeypatch) -> None:
    _mock_n8n(monkeypatch, _WFS, [], status=401)
    out = await automations.recent()
    assert out["error"] == "n8n answered 401" and out["runs"] == []


async def test_recent_unreachable_is_named(n8n, monkeypatch) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(automations.httpx, "AsyncClient",
        lambda **k: _RealAsyncClient(transport=httpx.MockTransport(down), **{
            x: k[x] for x in k if x in ("base_url", "headers", "timeout")}))
    assert (await automations.recent())["error"] == "n8n unreachable"


async def test_recent_unconfigured_is_empty_not_a_crash(monkeypatch) -> None:
    monkeypatch.delenv("N8N_BASE_URL", raising=False)
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    get_settings.cache_clear()
    out = await automations.recent()
    assert out == {"runs": [], "counts": {}, "armed": False}
    get_settings.cache_clear()


def test_hud_payload_is_trimmed_and_reports_the_eyes(monkeypatch) -> None:
    from integrations import api_hud

    monkeypatch.setattr(api_hud, "_eyes_up", lambda: False)
    monkeypatch.setattr(api_hud, "_cached", lambda key, fetch: {})  # no network in unit tests
    data = api_hud.hud({})
    assert set(data) == {"system", "weather", "reminders", "automations", "daemon", "eyes"}
    assert data["eyes"] is False  # Snaps card says the camera is off, truthfully
