"""friday · tests/unit/test_collectors.py

friday_health (audit -> counters) and n8n_pull (webhook rows -> store),
all mocked: header, dead-webhook resilience, malformed rows, unconfigured no-op.
"""

import json
from pathlib import Path

import httpx
import pytest

import integrations.n8n_pull as pull
from audit.log import Event
from config.settings import get_settings
from integrations import friday_health

_RealAsyncClient = httpx.AsyncClient


class Sink:
    def __init__(self) -> None:
        self.points: list[tuple[str, str, float]] = []

    def record(self, platform: str, metric: str, value: float, note: str = "", **kw) -> None:
        self.points.append((platform, metric, value))


# --- friday_health ---


def _tool(name: str, result: str, confirmed: bool) -> Event:
    detail = json.dumps({"tool": name, "args": "", "result": result, "confirmed": confirmed})
    return Event(ts=1.0, kind="tool", detail=detail)


def test_friday_health_counts() -> None:
    events = [
        Event(ts=1.0, kind="wake", detail="wake_phrase"),
        Event(ts=2.0, kind="wake", detail="manual"),
        _tool("content_pipeline", "started", True),
        _tool("content_pipeline", "failed: unreachable/error", True),
        _tool("camera_look", "a mug", True),
        _tool("wire_refund", "aborted: pin refused", False),
    ]
    sink = Sink()
    assert friday_health.collect(read=lambda since: events, record=sink.record) == 4
    data = {m: v for _, m, v in sink.points}
    assert data == {
        "wakes_24h": 2, "tool_runs_24h": 3, "tool_failures_24h": 2, "camera_looks_24h": 1,
    }


# --- calendar count (collect.py) ---


async def test_calendar_count_records_todays_events(monkeypatch: pytest.MonkeyPatch) -> None:
    import adapters.calendar as cal
    from integrations.collect import calendar_count

    async def fake_events():
        return ["a", "b", "c"]

    monkeypatch.setattr(cal, "events_today", fake_events)
    sink = Sink()
    assert await calendar_count(record=sink.record) == 1
    assert sink.points == [("calendar", "events_today", 3)]


async def test_calendar_count_skips_without_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import adapters.calendar as cal
    from integrations.collect import calendar_count

    async def denied():
        raise PermissionError("not granted")

    monkeypatch.setattr(cal, "events_today", denied)
    sink = Sink()
    assert await calendar_count(record=sink.record) == 0
    assert sink.points == []


# --- n8n_pull ---


@pytest.fixture
def n8n_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example.test")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s3cret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _config(tmp_path: Path, *webhooks: str) -> Path:
    path = tmp_path / "metrics.yaml"
    lines = "\n".join(f"  - {w}" for w in webhooks)
    path.write_text(f"metric_webhooks:\n{lines}\n" if webhooks else "metric_webhooks: []\n")
    return path


def _patch(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def tracking(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        pull.httpx,
        "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(tracking)),
    )
    return requests


async def test_pull_stores_rows_with_secret_header(
    n8n_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {"platform": "instagram", "metric": "reel_views_7d", "value": 12000},
        {"platform": "instagram", "metric": "follows_7d", "value": 84, "note": "reel spike"},
    ]
    requests = _patch(monkeypatch, lambda r: httpx.Response(200, text=json.dumps(rows)))
    sink = Sink()
    written = await pull.collect(
        record=sink.record, config=_config(tmp_path, "/webhook/metrics-ig"))
    assert written == 2
    assert ("instagram", "reel_views_7d", 12000.0) in sink.points
    assert requests[0].headers["X-Friday-Secret"] == "s3cret"


async def test_dead_webhook_skipped_not_fatal(
    n8n_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = [{"platform": "leads", "metric": "new_7d", "value": 5}]

    def handler(request: httpx.Request) -> httpx.Response:
        if "dead" in str(request.url):
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200, text=json.dumps(good))

    _patch(monkeypatch, handler)
    sink = Sink()
    written = await pull.collect(
        record=sink.record,
        config=_config(tmp_path, "/webhook/dead", "/webhook/metrics-leads"),
    )
    assert written == 1  # the sweep survives a dark platform


async def test_malformed_rows_skipped(
    n8n_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [{"platform": "x"}, {"platform": "x", "metric": "ok", "value": "not-a-number"},
            {"platform": "x", "metric": "good", "value": 1}]
    _patch(monkeypatch, lambda r: httpx.Response(200, text=json.dumps(rows)))
    sink = Sink()
    assert await pull.collect(record=sink.record, config=_config(tmp_path, "/w")) == 1


async def test_unconfigured_is_a_silent_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N8N_BASE_URL", "")
    get_settings.cache_clear()
    try:
        requests = _patch(monkeypatch, lambda r: httpx.Response(200, text="[]"))
        assert await pull.collect(record=Sink().record, config=_config(tmp_path, "/w")) == 0
        assert requests == []
    finally:
        get_settings.cache_clear()
