"""brain/checkin.py — the caring check-in rotates topics by wake count and
composes a warm question, degrading to silence if the LLM is down."""

import types

from brain.checkin import _ORDER, checkin_line, next_topic


def _audit(n_wakes):
    return lambda: [types.SimpleNamespace(kind="wake") for _ in range(n_wakes)]


def test_topic_rotates_by_wake_count():
    seen = [next_topic(_audit(i)) for i in range(len(_ORDER) + 1)]
    assert seen[: len(_ORDER)] == _ORDER  # a different concern each wake, in order
    assert seen[len(_ORDER)] == _ORDER[0]  # wraps around the day


def test_topic_defaults_when_audit_unreadable():
    def boom():
        raise RuntimeError("audit down")

    assert next_topic(boom) == _ORDER[0]


async def test_line_composed_grounded_in_memory():
    calls = {}

    async def think(prompt, **kw):
        calls["prompt"] = prompt
        return "How's the Rust project coming along, sir?"

    async def recall(q, k=1):
        return ["sir is learning Rust"]

    line = await checkin_line(think=think, recall=recall, audit_read=_audit(1))  # skills
    assert line == "How's the Rust project coming along, sir?"
    assert "Rust" in calls["prompt"]  # the recalled fact grounded the question


async def test_line_empty_when_llm_down():
    async def boom(prompt, **kw):
        raise RuntimeError("llm down")

    async def recall(q, k=1):
        return []

    assert await checkin_line(think=boom, recall=recall, audit_read=_audit(0)) == ""
