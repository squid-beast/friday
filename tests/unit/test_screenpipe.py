"""jarvis-life-os · tests/unit/test_screenpipe.py

adapters/screenpipe.py mocked: query shape, exclusion filtering, the
screen_off cut, defensive parsing, service-down propagation.
"""

import json
from pathlib import Path

import httpx
import pytest

import adapters.screenpipe as sp
from config.settings import get_settings

_RealAsyncClient = httpx.AsyncClient


@pytest.fixture(autouse=True)
def _flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SCREEN_OFF_FILE", str(tmp_path / "screen_off"))
    monkeypatch.setenv("SCREENPIPE_EXCLUDE", "WhatsApp, Chase Bank")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _hit(text: str, app: str = "Safari") -> dict:
    return {
        "type": "OCR",
        "content": {
            "text": text,
            "app_name": app,
            "window_name": "win",
            "timestamp": "2026-08-09T15:00:00Z",
        },
    }


def _patch(monkeypatch: pytest.MonkeyPatch, payload: dict, status: int = 200):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text=json.dumps(payload))

    monkeypatch.setattr(
        sp.httpx,
        "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler)),
    )
    return requests


async def test_search_query_shape_and_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _patch(monkeypatch, {"data": [_hit("github.com/langchain langgraph repo")]})
    hits = await sp.search("that repo I looked at", limit=7)
    assert hits[0].app == "Safari" and "langgraph" in hits[0].text
    params = dict(httpx.QueryParams(requests[0].url.query.decode()))
    assert params["q"] == "that repo I looked at"
    assert params["content_type"] == "ocr"
    assert params["limit"] == "7"


async def test_excluded_apps_never_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        {"data": [_hit("balance $1,234", "Chase Bank"), _hit("hey bro", "WhatsApp"), _hit("ok")]},
    )
    hits = await sp.search("anything")
    assert [h.app for h in hits] == ["Safari"]  # bank + whatsapp filtered client-side


async def test_screen_off_cut_refuses_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _patch(monkeypatch, {"data": []})
    Path(get_settings().screen_off_file).touch()
    with pytest.raises(PermissionError):
        await sp.search("anything")
    assert requests == []


async def test_malformed_items_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, {"data": [{"type": "OCR"}, {"content": {"text": ""}}, _hit("good")]})
    hits = await sp.search("q")
    assert [h.text for h in hits] == ["good"]


async def test_service_down_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("screenpipe not running", request=request)

    monkeypatch.setattr(
        sp.httpx,
        "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(httpx.ConnectError):
        await sp.search("q")
