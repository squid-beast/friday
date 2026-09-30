"""adapters/telephony.py — calls refuse cleanly until configured, need a real
number, and dispatch to the provider once wired (network mocked)."""

import pytest

import adapters.telephony as tel
from adapters.telephony import _extract_number, call
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _clear():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_refuses_when_unconfigured(monkeypatch):
    monkeypatch.delenv("TELEPHONY_PROVIDER", raising=False)
    monkeypatch.delenv("TELEPHONY_API_KEY", raising=False)
    get_settings.cache_clear()
    assert "isn't set up" in await call("", "call the plumber on 555-123-4567")


async def test_needs_a_number(monkeypatch):
    monkeypatch.setenv("TELEPHONY_PROVIDER", "vapi")
    monkeypatch.setenv("TELEPHONY_API_KEY", "k")
    get_settings.cache_clear()
    assert "need the number" in await call("", "call my mum please")


async def test_non_vapi_provider_not_wired(monkeypatch):
    monkeypatch.setenv("TELEPHONY_PROVIDER", "twilio")
    monkeypatch.setenv("TELEPHONY_API_KEY", "k")
    get_settings.cache_clear()
    assert "isn't wired" in await call("", "call 555-222-3333")


async def test_vapi_path_dispatches(monkeypatch):
    for k, v in {"TELEPHONY_PROVIDER": "vapi", "TELEPHONY_API_KEY": "k",
                 "TELEPHONY_FROM_NUMBER": "pn_1", "TELEPHONY_AGENT_ID": "as_1"}.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    sent = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=15):
        sent["auth"] = req.headers.get("Authorization")
        return FakeResp()

    monkeypatch.setattr(tel.urllib.request, "urlopen", fake_urlopen)
    reply = await call("", "call the dentist on +1 (415) 555-2671 and reschedule")
    assert "Placing the call" in reply and "+14155552671" in reply
    assert sent["auth"] == "Bearer k"


def test_extract_number():
    assert _extract_number("", "call +1 (415) 555-2671 now") == "+14155552671"
    assert _extract_number("555-123-4567", "call them") == "5551234567"
    assert _extract_number("", "call my mum") == ""
