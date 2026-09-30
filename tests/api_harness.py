"""friday · tests/api_harness.py

Shared HTTP helpers for the API suites (test_api_v1*.py): a fake brain bridge,
tiny urllib GET/POST wrappers, and the HTTPError code reader.
"""

import json
import urllib.request


class FakeBridge:
    def __init__(self) -> None:
        self.asked: list[str] = []

    def ask(self, text: str) -> dict:
        self.asked.append(text)
        return {"reply": f"Indeed, sir. ({len(text)} chars heard)", "pending": False}


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read(), dict(r.headers)


def _post(url: str, payload, raw: bytes | None = None):
    data = raw if raw is not None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=5) as r:
        return r.status, json.loads(r.read())


def _code(err) -> int:
    return err.value.code
