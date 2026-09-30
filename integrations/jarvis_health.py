"""jarvis-life-os · integrations/jarvis_health.py

Jarvis's own vitals from the audit log — the one collector needing zero
credentials: wakes, workflow runs/failures, camera looks (last 24h).
"""

import json
import time

from audit.log import events_since
from integrations import store


def collect(*, read=events_since, record=store.record) -> int:
    """Store today's health counters; returns how many points were written."""
    events = read(time.time() - 86_400)
    wakes = sum(1 for e in events if e.kind == "wake")
    tools = [json.loads(e.detail) for e in events if e.kind == "tool" and e.detail]
    runs = sum(1 for t in tools if t.get("confirmed"))
    failures = sum(1 for t in tools if str(t.get("result", "")).startswith(("failed", "aborted")))
    looks = sum(1 for t in tools if t.get("tool") == "camera_look")
    points = {
        "wakes_24h": wakes,
        "tool_runs_24h": runs,
        "tool_failures_24h": failures,
        "camera_looks_24h": looks,
    }
    for metric, value in points.items():
        record("jarvis", metric, value)
    return len(points)
