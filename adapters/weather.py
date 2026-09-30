"""friday · adapters/weather.py

Weather sense via Open-Meteo — free, keyless (nothing to leak). Fahrenheit +
mph, WEATHER_CITY names home; a spoken place ("weather in Austin?") overrides.
conditions() returns structured data for the HUD card; report() formats the
sentence Friday speaks. An unset city SAYS what's missing, never raises there.
"""

import re

import httpx

from config.settings import get_settings

_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 10.0

_WMO = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "icy fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers",
    82: "violent showers", 85: "snow showers", 86: "heavy snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail",
    99: "a thunderstorm with heavy hail",
}

_PLACE = re.compile(r"\b(?:in|at|for) ([a-z][a-z .,'-]{2,40})", re.IGNORECASE)
_TRAILING = re.compile(
    r"\s*(?:today|tomorrow|tonight|right now|now|please|sir)\s*[?.!]*$", re.IGNORECASE
)


def _spoken_place(utterance: str) -> str:
    match = _PLACE.search(utterance or "")
    if not match:
        return ""
    return _TRAILING.sub("", match.group(1)).strip(" ?.!,")


async def conditions(city: str) -> dict:
    """Structured current + today, in °F / mph. Raises on network/unknown-city."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        geo = (await client.get(_GEO, params={"name": city, "count": 1})).json()
        places = geo.get("results") or []
        if not places:
            raise ValueError(f"couldn't place '{city}'")
        place = places[0]
        data = (await client.get(_FORECAST, params={
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": ("temperature_2m,apparent_temperature,weather_code,"
                        "wind_speed_10m,relative_humidity_2m"),
            "daily": ("temperature_2m_max,temperature_2m_min,"
                      "precipitation_probability_max"),
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "timezone": "auto", "forecast_days": 1,
        })).json()
    now, day = data["current"], data["daily"]
    return {
        "city": place["name"],
        "condition": _WMO.get(now["weather_code"], "unreadable skies"),
        "temp": round(now["temperature_2m"]),
        "feels": round(now["apparent_temperature"]),
        "high": round(day["temperature_2m_max"][0]),
        "low": round(day["temperature_2m_min"][0]),
        "rain": day["precipitation_probability_max"][0],
        "humidity": now["relative_humidity_2m"],
        "wind": round(now["wind_speed_10m"]),
    }


async def report(arg: str, utterance: str) -> str:
    """tools.yaml contract: fn(arg, utterance). The spoken forecast."""
    city = _spoken_place(utterance) or get_settings().weather_city
    if not city:
        return ("No home city is configured for weather — one line in .env "
                "fixes it: WEATHER_CITY.")
    try:
        c = await conditions(city)
    except ValueError as exc:
        return f"I couldn't read the weather — {exc}, sir."
    return (
        f"{c['city']}: {c['condition']}, {c['temp']}°F "
        f"(feels like {c['feels']}°F), humidity {c['humidity']}%, "
        f"wind {c['wind']} mph. Today {c['low']} to {c['high']}°F, "
        f"rain chance {c['rain']}%."
    )
