"""friday · tests/fakes.py

Fake adapters for network-free graph tests. FakeLLM is scripted: it returns its
replies in order and fails loudly if asked for more than was scripted.
FakeN8n arrives with the ops node in Phase 4.
"""

from typing import Self

import httpx

from adapters.vault import VaultHit


class FakeLLM:
    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.calls: list[dict] = []

    async def think(
        self,
        prompt: str,
        *,
        system: str | None = None,
        fast: bool = False,
        max_tokens: int = 512,
    ) -> str:
        self.calls.append(
            {"prompt": prompt, "system": system, "fast": fast, "max_tokens": max_tokens}
        )
        if not self.replies:
            raise AssertionError("FakeLLM: no scripted reply left")
        return self.replies.pop(0)

    async def think_stream(
        self, prompt: str, *, system: str | None = None,
        fast: bool = False, max_tokens: int = 512,
    ):
        """Streaming twin of think(): yields the next scripted reply in two chunks."""
        reply = await self.think(prompt, system=system, fast=fast, max_tokens=max_tokens)
        mid = len(reply) // 2 or len(reply)
        for chunk in (reply[:mid], reply[mid:]):
            if chunk:
                yield chunk


class BrokenLLM:
    async def think(
        self,
        prompt: str,
        *,
        system: str | None = None,
        fast: bool = False,
        max_tokens: int = 512,
    ) -> str:
        raise ConnectionError("anthropic unreachable")


class FakeVault:
    def __init__(self, hits: list[VaultHit] | None = None) -> None:
        self.hits = hits or []
        self.appended: list[str] = []
        self.queries: list[str] = []

    async def search(self, query: str, max_hits: int = 5) -> list[VaultHit]:
        self.queries.append(query)
        return self.hits[:max_hits]

    def append_inbox(self, text: str) -> str:
        self.appended.append(text)
        return "_inbox/friday-notes.md"


async def sample_tool(arg: str, utterance: str) -> str:
    """Target for _default_execute's importlib resolution test."""
    return f"{arg}|{utterance}"


class FakeMemory:
    def __init__(self, facts: list[str] | None = None) -> None:
        self.facts = facts or []
        self.stored: list[str] = []

    async def remember(self, fact: str) -> None:
        self.stored.append(fact)

    async def recall(self, query: str, k: int = 3) -> list[str]:
        return self.facts[:k]


class FakeBrain:
    """A non-streaming route (vault/ops-style): the whole reply arrives in updates."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    async def astream(self, state, config, *, stream_mode=None):
        self.calls.append((state, config))
        yield "updates", {"chat": {"reply": "Indeed, sir.", "route": "chat", "messages": []}}


def fake_http(monkeypatch, module, status: int, json: dict | None = None) -> list:
    """Replace module.httpx.AsyncClient with a one-response fake; returns the
    recorded (url, headers) calls. For the doctor's GET-only checks."""
    calls: list[tuple[str, dict]] = []
    response = httpx.Response(status, json=json, request=httpx.Request("GET", "https://x"))

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

    monkeypatch.setattr(module.httpx, "AsyncClient", Client)
    return calls
