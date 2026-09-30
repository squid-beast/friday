"""friday · tests/unit/test_hud_cache.py

api_hud's 60s memo: the UI polls every 6s, so weather + n8n are fetched at most
once a minute; a failed fetch is NOT cached (the next poll retries).
"""

import pytest

from integrations import api_hud


def test_memo_serves_within_ttl_and_refetches_after(monkeypatch) -> None:
    clock = {"t": 0.0}
    monkeypatch.setattr(api_hud.time, "monotonic", lambda: clock["t"])
    calls = []

    def fetch() -> dict:
        calls.append(1)
        return {"n": len(calls)}

    assert api_hud._cached("k", fetch) == {"n": 1}
    clock["t"] = 59.0
    assert api_hud._cached("k", fetch) == {"n": 1} and len(calls) == 1
    clock["t"] = 61.0
    assert api_hud._cached("k", fetch) == {"n": 2}


def test_failed_fetch_is_not_cached() -> None:
    def boom() -> dict:
        raise ConnectionError("n8n down")

    with pytest.raises(ConnectionError):
        api_hud._cached("k2", boom)
    assert "k2" not in api_hud._memo
