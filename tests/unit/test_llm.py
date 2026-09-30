"""adapters/llm.py — think_stream yields text deltas (the voice pipeline speaks
on the first token). Network mocked to the Anthropic streaming shape."""

import pytest

import adapters.llm as llm_mod
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _StreamCM:
    def __init__(self, deltas):
        self._deltas = deltas

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    @property
    def text_stream(self):
        async def gen():
            for d in self._deltas:
                yield d

        return gen()


async def test_think_stream_yields_each_delta(monkeypatch):
    seen = {}

    class _Msgs:
        def stream(self, **kw):
            seen.update(kw)
            return _StreamCM(["Hel", "lo, ", "", "sir."])  # empty delta is dropped

    monkeypatch.setattr(llm_mod, "_get_client", lambda: type("C", (), {"messages": _Msgs()})())
    out = [d async for d in llm_mod.think_stream("hi", system="persona", fast=True)]
    assert out == ["Hel", "lo, ", "sir."]  # streamed pieces, empties filtered
    assert seen["model"] == get_settings().model_fast  # fast=True -> cheap model
    assert seen["system"] == "persona"
