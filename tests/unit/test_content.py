"""jarvis-life-os · tests/unit/test_content.py

Content Studio pipeline: dedupe, status lifecycle, n8n pull/publish contracts,
the publish audit, and unarmed-webhook refusals. All network mocked.
"""

import json
from pathlib import Path

import httpx
import pytest

from config.settings import get_settings
from integrations import content

_RealAsyncClient = httpx.AsyncClient
TREND = {"id": "t1", "title": "Before/after storefront reel", "hook": "POV: your shop at 6am",
         "source": "instagram", "score": 91}


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "content.db"
    monkeypatch.setattr(content, "_DB", path)
    return path


@pytest.fixture
def n8n_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("N8N_BASE_URL", "https://n8n.example.test")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("CONTENT_TRENDING_WEBHOOK", "/webhook/content-trending")
    monkeypatch.setenv("CONTENT_PUBLISH_WEBHOOK", "/webhook/content-publish")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _patch(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def tracking(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        content.httpx, "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(tracking)),
    )
    return requests


# --- store lifecycle ---


def test_upsert_dedupes_and_preserves_review_state(db: Path) -> None:
    assert content.upsert([TREND]) == 1
    content.set_status("t1", "posted", "my caption")
    assert content.upsert([TREND]) == 0  # re-pull never resurrects
    (item,) = content.items(status=None)
    assert item.status == "posted" and item.caption == "my caption"


def test_items_sorted_by_score_and_filtered_by_status(db: Path) -> None:
    content.upsert([TREND, {**TREND, "id": "t2", "score": 99}, {**TREND, "id": "t3"}])
    content.set_status("t3", "skipped")
    fresh = content.items()
    assert [i.id for i in fresh] == ["t2", "t1"]  # score desc, skipped hidden


def test_malformed_rows_skipped(db: Path) -> None:
    assert content.upsert([{"title": "no id"}, TREND, "garbage"]) == 1


def test_set_status_guards(db: Path) -> None:
    content.upsert([TREND])
    with pytest.raises(ValueError, match="unknown status"):
        content.set_status("t1", "yeeted")
    with pytest.raises(ValueError, match="no such item"):
        content.set_status("ghost", "posted")


# --- pull ---


async def test_pull_fetches_with_secret_and_stores(db: Path, n8n_env, monkeypatch) -> None:
    requests = _patch(monkeypatch, lambda r: httpx.Response(200, text=json.dumps([TREND])))
    assert await content.pull() == 1
    assert requests[0].headers["X-Jarvis-Secret"] == "s3cret"
    assert str(requests[0].url).endswith("/webhook/content-trending")


async def test_pull_unconfigured_raises_with_hint(db: Path, monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_TRENDING_WEBHOOK", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="not configured"):
            await content.pull()
    finally:
        get_settings.cache_clear()


# --- publish ---


async def test_publish_sends_caption_marks_posted_and_audits(
    db: Path, n8n_env, monkeypatch
) -> None:
    content.upsert([TREND])
    audited: list[tuple[str, str, bool]] = []

    def audit(tool: str, args: str, result: str, *, confirmed: bool) -> None:
        audited.append((tool, args, confirmed))

    requests = _patch(monkeypatch, lambda r: httpx.Response(200, text="scheduled"))
    result = await content.publish("t1", "custom caption ✨", audit=audit)
    assert result == "scheduled"
    body = json.loads(requests[0].content)
    assert body["caption"] == "custom caption ✨" and body["id"] == "t1"
    assert content.items(status=None)[0].status == "posted"
    assert audited == [("ig_publish", "t1", True)]  # every publish is audited


async def test_publish_unknown_item_never_calls_n8n(db: Path, n8n_env, monkeypatch) -> None:
    requests = _patch(monkeypatch, lambda r: httpx.Response(200))
    with pytest.raises(ValueError, match="no such item"):
        await content.publish("ghost", "caption")
    assert requests == []


async def test_publish_failure_leaves_item_reviewable(db: Path, n8n_env, monkeypatch) -> None:
    content.upsert([TREND])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("n8n down", request=request)

    _patch(monkeypatch, handler)
    with pytest.raises(httpx.ConnectError):
        await content.publish("t1", "caption")
    assert content.items()[0].status == "new"  # not falsely marked posted
