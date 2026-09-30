"""scripts/healthcheck.py — quick never fails a session; full fails loud."""


import httpx
import pytest

import scripts.healthcheck as hc
from config.settings import get_settings
from tests.fakes import fake_http


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
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: False)
    monkeypatch.setattr(hc, "_PHONE_VOICE_AGENT", tmp_path / "absent.plist")
    assert hc.main(["--quick"]) == 0  # SessionStart hook must never block
    out = capsys.readouterr().out
    assert "WARN: ANTHROPIC_API_KEY" in out
    assert "LiveKit is down" not in out  # phone voice not installed = nothing to warn about


def test_quick_warns_livekit_only_when_phone_voice_is_installed(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path
) -> None:
    agent = tmp_path / "com.friday.livekit.plist"
    agent.write_text("<plist/>")
    monkeypatch.setattr(hc, "_PHONE_VOICE_AGENT", agent)
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: False)
    assert hc.main(["--quick"]) == 0
    assert "LiveKit is down" in capsys.readouterr().out


def test_full_all_green(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    for name in hc.CHECKS:
        monkeypatch.setitem(hc.CHECKS, name, _ok)
    assert hc.main([]) == 0
    assert "all clear, sir" in capsys.readouterr().out


def test_full_failure_exits_one_with_reason(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setitem(hc.CHECKS, "llm", _boom)
    for name in ("deepgram", "cartesia"):
        monkeypatch.setitem(hc.CHECKS, name, _ok)
    assert hc.main([]) == 1
    assert "FAIL: llm: 401 unauthorized" in capsys.readouterr().out


def test_quick_invalid_env_value_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A typo'd .env is a broken state to REPORT — never a blocked session."""
    monkeypatch.setenv("SESSION_SILENCE_TIMEOUT_S", "notanumber")
    get_settings.cache_clear()
    assert hc.main(["--quick"]) == 0
    assert "WARN" in capsys.readouterr().out


def _fake_http(
    monkeypatch: pytest.MonkeyPatch, status: int, json: dict | None = None
) -> list[tuple[str, dict]]:
    return fake_http(monkeypatch, hc, status, json)


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


def test_quick_checks_the_active_providers_key(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(hc, "port_open", lambda *a, **k: True)
    assert hc.main(["--quick"]) == 0
    out = capsys.readouterr().out
    assert "WARN: OPENAI_API_KEY not set" in out and "ANTHROPIC_API_KEY" not in out
