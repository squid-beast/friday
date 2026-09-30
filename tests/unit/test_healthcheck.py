"""scripts/healthcheck.py — quick never fails a session; full fails loud."""

from typing import Self

import httpx
import pytest

import scripts.healthcheck as hc
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch):
    for var in ("ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "TTS_VOICE_ID"):
        monkeypatch.setenv(var, "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _ok() -> None:
    return None


async def _boom() -> None:
    raise RuntimeError("401 unauthorized")


def test_quick_all_green(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: True)
    assert hc.main(["--quick"]) == 0
    assert hc.quick() == []


def test_quick_missing_key_warns_but_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: False)
    assert hc.main(["--quick"]) == 0  # SessionStart hook must never block
    out = capsys.readouterr().out
    assert "WARN: ANTHROPIC_API_KEY" in out
    assert "livekit" in out


def test_full_all_green(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    for name in hc.CHECKS:
        monkeypatch.setitem(hc.CHECKS, name, _ok)
    assert hc.main([]) == 0
    assert "all clear, sir" in capsys.readouterr().out


def test_full_failure_exits_one_with_reason(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setitem(hc.CHECKS, "anthropic", _boom)
    for name in ("deepgram", "cartesia"):
        monkeypatch.setitem(hc.CHECKS, name, _ok)
    assert hc.main([]) == 1
    assert "FAIL: anthropic: 401 unauthorized" in capsys.readouterr().out


def test_quick_invalid_env_value_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A typo'd .env is a broken state to REPORT — never a blocked session."""
    monkeypatch.setenv("SESSION_SILENCE_TIMEOUT_S", "notanumber")
    get_settings.cache_clear()
    assert hc.main(["--quick"]) == 0
    assert "WARN" in capsys.readouterr().out


def _fake_http(monkeypatch: pytest.MonkeyPatch, status: int) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []
    response = httpx.Response(status, request=httpx.Request("GET", "https://x"))

    class Client:
        def __init__(self, timeout: float | None = None) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str, headers: dict | None = None) -> httpx.Response:
            calls.append((url, headers))
            return response

    monkeypatch.setattr(hc.httpx, "AsyncClient", Client)
    return calls


async def test_check_deepgram_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
        await hc.check_deepgram()


async def test_check_cartesia_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTESIA_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="CARTESIA_API_KEY"):
        await hc.check_cartesia()


async def test_check_deepgram_auth_header_and_401(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_http(monkeypatch, 401)
    with pytest.raises(httpx.HTTPStatusError):
        await hc.check_deepgram()
    url, headers = calls[0]
    assert "deepgram" in url
    assert headers["Authorization"] == "Token test-key"


async def test_check_cartesia_auth_header_and_401(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_http(monkeypatch, 401)
    with pytest.raises(httpx.HTTPStatusError):
        await hc.check_cartesia()
    url, headers = calls[0]
    assert "cartesia" in url
    assert headers["X-API-Key"] == "test-key"


# --- Phase 6 doctor extensions ---


async def test_check_n8n_unconfigured_is_not_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N8N_BASE_URL", "")
    get_settings.cache_clear()
    calls = _fake_http(monkeypatch, 500)
    await hc.check_n8n()  # must not raise, must not call anything
    assert calls == []


def test_removed_eye_services_are_reported_dark_not_failed(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: True)
    assert "screenpipe" not in hc.CHECKS and "moondream" not in hc.CHECKS
    assert hc.main(["--quick"]) == 0
    out = capsys.readouterr().out
    assert "dark by design" in out and "WARN" not in out


def test_quick_warns_when_strict_voice_lock_is_missing_model(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("WAKE_REQUIRE_VERIFIER", "true")
    monkeypatch.setenv("WAKE_VERIFIER_PATH", "")
    get_settings.cache_clear()
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: True)
    assert hc.main(["--quick"]) == 0
    assert "strict owner-voice wake is on" in capsys.readouterr().out
