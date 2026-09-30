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


async def test_recent_normalizes_runs_and_counts_today(n8n, monkeypatch) -> None:
    import time
    today = time.strftime("%Y-%m-%d", time.localtime())

    def handler(request: httpx.Request) -> httpx.Response:
        if "/workflows" in str(request.url):
            return httpx.Response(200, json={"data": [{"id": "7", "name": "Vendor Report"}]})
        return httpx.Response(200, json={"data": [
            {"id": "1", "workflowId": "7", "status": "success",
             "startedAt": f"{today}T09:00:00.000Z", "stoppedAt": f"{today}T09:00:04.000Z"},
            {"id": "2", "workflowId": "7", "status": "error",
             "startedAt": f"{today}T10:00:00.000Z", "stoppedAt": f"{today}T10:00:01.000Z"}]})

    monkeypatch.setattr(automations.httpx, "AsyncClient",
        lambda **k: _RealAsyncClient(transport=httpx.MockTransport(handler), **{
            x: k[x] for x in k if x in ("base_url", "headers", "timeout")}))
    out = await automations.recent()
    assert out["armed"] is True
    assert out["counts"] == {"success": 1, "error": 1}
    assert out["runs"][0] == {"id": "1", "name": "Vendor Report",
                              "status": "success", "when": "09:00"}


async def test_recent_unconfigured_is_empty_not_a_crash(monkeypatch) -> None:
    monkeypatch.delenv("N8N_BASE_URL", raising=False)
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    get_settings.cache_clear()
    out = await automations.recent()
    assert out == {"runs": [], "counts": {}, "armed": False}
    get_settings.cache_clear()
