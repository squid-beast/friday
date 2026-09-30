"""adapters/weather.py — the weather sense, network mocked. Happy path
formatting, the helpful unconfigured line, unknown city, and API failure
surfacing (ops turns raises into the in-persona apology)."""

import httpx
import pytest

import adapters.weather as weather_mod
from adapters.weather import report
from config.settings import get_settings

_RealAsyncClient = httpx.AsyncClient  # captured before patching — no recursion


@pytest.fixture
def city(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_CITY", "Hyderabad")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock(handler, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        weather_mod.httpx, "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler)),
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    if "geocoding" in str(request.url):
        return httpx.Response(200, json={"results": [
            {"name": "Hyderabad", "latitude": 17.4, "longitude": 78.5}]})
    return httpx.Response(200, json={
        "current": {"temperature_2m": 31.2, "apparent_temperature": 35.6,
                    "weather_code": 3, "wind_speed_10m": 14.2,
                    "relative_humidity_2m": 74},
        "daily": {"temperature_2m_max": [33.0], "temperature_2m_min": [24.0],
                  "precipitation_probability_max": [40]},
    })


async def test_reports_conditions_in_plain_facts(city, monkeypatch) -> None:
    _mock(_ok_handler, monkeypatch)
    line = await report("", "what's the weather?")
    assert "Hyderabad: overcast, 31°F" in line  # Fahrenheit since 2026-08-20
    assert "feels like 36°F" in line and "rain chance 40%" in line


def test_spoken_place_extraction() -> None:
    from adapters.weather import _spoken_place

    assert _spoken_place("what's the weather in austin today?") == "austin"
    assert _spoken_place("weather for New York please") == "New York"
    assert _spoken_place("will it rain tomorrow?") == ""  # no place -> home city


async def test_spoken_place_overrides_home_city(city, monkeypatch) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in str(request.url):
            seen.append(request.url.params["name"])
            return httpx.Response(200, json={"results": [
                {"name": "Austin", "latitude": 30.3, "longitude": -97.7}]})
        return _ok_handler(request)

    _mock(handler, monkeypatch)
    line = await report("", "what's the weather in Austin right now?")
    assert seen == ["Austin"] and line.startswith("Austin:")


async def test_unconfigured_city_says_what_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("WEATHER_CITY", raising=False)
    get_settings.cache_clear()
    assert "WEATHER_CITY" in await report("", "weather?")


async def test_unknown_city_admits_it(city, monkeypatch) -> None:
    _mock(lambda r: httpx.Response(200, json={"results": []}), monkeypatch)
    assert "couldn't place" in await report("", "weather?")


async def test_api_failure_raises_for_the_ops_apology(city, monkeypatch) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("open-meteo unreachable")

    _mock(boom, monkeypatch)
    with pytest.raises(httpx.ConnectError):
        await report("", "weather?")  # ops_execute catches -> apology line
