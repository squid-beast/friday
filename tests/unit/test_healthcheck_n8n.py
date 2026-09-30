"""friday · tests/unit/test_healthcheck_n8n.py

`make doctor`'s n8n check (2026-09-29): reachable + authorised via the REST API
key, and every registered adapters.n8n tool must have an ACTIVE POST workflow
on its path — a URL that merely answers is no longer "healthy".
"""

import httpx
import pytest

import scripts.healthcheck as hc
from config.settings import get_settings
from tests.fakes import fake_http


@pytest.fixture(autouse=True)
def _fresh():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fake_http(monkeypatch, status: int, json: dict | None = None) -> list:
    return fake_http(monkeypatch, hc, status, json)


async def test_check_n8n_unconfigured_is_not_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_BASE_URL", "")
    get_settings.cache_clear()
    calls = _fake_http(monkeypatch, 500)
    await hc.check_n8n()  # must not raise, must not call anything
    assert calls == []


def _wf(path: str, method: str = "POST", active: bool = True) -> dict:
    return {"active": active, "nodes": [{"type": "n8n-nodes-base.webhook",
                                         "parameters": {"path": path, "httpMethod": method}}]}


@pytest.fixture
def n8n_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("N8N_BASE_URL", "http://n8n.tailnet:5678")
    monkeypatch.setenv("N8N_API_KEY", "api-key")
    get_settings.cache_clear()


def _tool(path: str):
    from config.tools import Tool

    return Tool(name="friday_flow", description="x", adapter="adapters.n8n:run",
                webhook_path=path, risk="confirm")


async def test_check_n8n_uses_the_api_key_and_passes_with_no_n8n_tools(
    monkeypatch: pytest.MonkeyPatch, n8n_env
) -> None:
    calls = _fake_http(monkeypatch, 200, {"data": [_wf("lead-intake")]})
    monkeypatch.setattr(hc, "load_tools", lambda: [])
    await hc.check_n8n()
    url, headers = calls[0]
    assert url.endswith("/api/v1/workflows?limit=250") and headers["X-N8N-API-KEY"] == "api-key"


async def test_check_n8n_fails_when_a_tool_has_no_active_post_workflow(
    monkeypatch: pytest.MonkeyPatch, n8n_env
) -> None:
    _fake_http(monkeypatch, 200, {"data": [_wf("friday-a", "GET"), _wf("friday-b", active=False)]})
    monkeypatch.setattr(hc, "load_tools", lambda: [_tool("/webhook/friday-a")])
    with pytest.raises(ValueError, match="friday_flow"):
        await hc.check_n8n()  # GET-only / inactive workflows can't serve Friday's POST


async def test_check_n8n_passes_when_the_tool_path_is_served(
    monkeypatch: pytest.MonkeyPatch, n8n_env
) -> None:
    _fake_http(monkeypatch, 200, {"data": [_wf("friday-a")]})
    monkeypatch.setattr(hc, "load_tools", lambda: [_tool("/webhook/friday-a")])
    await hc.check_n8n()


async def test_check_n8n_bad_key_fails(monkeypatch: pytest.MonkeyPatch, n8n_env) -> None:
    _fake_http(monkeypatch, 401)
    with pytest.raises(httpx.HTTPStatusError):
        await hc.check_n8n()


def test_hook_key_matches_how_the_adapter_builds_urls() -> None:
    assert hc._hook_key("/webhook/friday-summary") == "friday-summary"
    assert hc._hook_key("webhook/bookyourslot/find") == "bookyourslot/find"
    assert hc._hook_key("/friday-summary") is None  # not a production webhook URL: 404


def test_multi_method_webhook_nodes_count_as_post() -> None:
    wf = {"active": True, "nodes": [{"type": "n8n-nodes-base.webhook",
                                     "parameters": {"path": "friday-a",
                                                    "httpMethod": ["GET", "POST"]}}]}
    no_method = {"active": True, "nodes": [{"type": "n8n-nodes-base.webhook",
                                            "parameters": {"path": "friday-b"}}]}  # GET
    assert hc._active_post_hooks([wf, no_method]) == {"friday-a"}


async def test_check_n8n_follows_pagination(monkeypatch: pytest.MonkeyPatch, n8n_env) -> None:
    pages = [{"data": [], "nextCursor": "p2"}, {"data": [_wf("friday-a")]}]
    urls: list[str] = []

    class Client:
        def __init__(self, timeout=None) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def get(self, url: str, headers=None) -> httpx.Response:
            urls.append(url)
            return httpx.Response(200, json=pages[len(urls) - 1],
                                  request=httpx.Request("GET", url))

    monkeypatch.setattr(hc.httpx, "AsyncClient", Client)
    monkeypatch.setattr(hc, "load_tools", lambda: [_tool("/webhook/friday-a")])
    await hc.check_n8n()  # the served path is only on page 2
    assert urls[1].endswith("&cursor=p2")
