"""jarvis-life-os · tests/integration/test_n8n_contract.py

adapters/n8n.py against a mock HTTP transport: secret header on every request,
exactly one retry on transport error / 5xx, no retry on 4xx, missing env raises.
"""

import httpx
import pytest

from adapters import n8n
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example.test")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s3cret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


_RealAsyncClient = httpx.AsyncClient  # captured before patching — the lambda must not recurse


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def tracking_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        n8n.httpx,
        "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(tracking_handler)),
    )
    return requests


async def test_secret_header_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _patch_client(monkeypatch, lambda r: httpx.Response(200, text="started"))
    result = await n8n.call("/webhook/content")
    assert result == "started"
    assert requests[0].headers["X-Jarvis-Secret"] == "s3cret"
    assert str(requests[0].url) == "https://n8n.example.test/webhook/content"


async def test_path_without_slash_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _patch_client(monkeypatch, lambda r: httpx.Response(200, text="ok"))
    await n8n.call("webhook/content")
    assert str(requests[0].url).endswith("/webhook/content")


async def test_one_retry_on_500_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([httpx.Response(500), httpx.Response(200, text="second try")])
    requests = _patch_client(monkeypatch, lambda r: next(responses))
    assert await n8n.call("/webhook/x") == "second try"
    assert len(requests) == 2


async def test_500_twice_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _patch_client(monkeypatch, lambda r: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await n8n.call("/webhook/x")
    assert len(requests) == 2  # exactly one retry, never a storm


async def test_4xx_fails_immediately_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _patch_client(monkeypatch, lambda r: httpx.Response(401))
    with pytest.raises(httpx.HTTPStatusError):
        await n8n.call("/webhook/x")
    assert len(requests) == 1  # a bad secret is config, not weather


async def test_transport_error_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    requests = _patch_client(monkeypatch, handler)
    with pytest.raises(httpx.ConnectError):
        await n8n.call("/webhook/x")
    assert len(requests) == 2


async def test_missing_env_raises_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_BASE_URL", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="N8N_BASE_URL"):
        await n8n.call("/webhook/x")


async def test_missing_secret_raises_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="N8N_WEBHOOK_SECRET"):
        await n8n.call("/webhook/x")


async def test_run_wrapper_sends_utterance_as_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _patch_client(monkeypatch, lambda r: httpx.Response(200, text="ok"))
    await n8n.run("/webhook/content", "run it for the Riverside client")
    import json

    assert json.loads(requests[0].content) == {"utterance": "run it for the Riverside client"}
