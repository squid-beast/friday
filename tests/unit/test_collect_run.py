"""jarvis-life-os · tests/unit/test_collect_run.py

The full collection sweep: run() sums every collector; main() reports.
"""

import pytest


class Sink:
    def __init__(self) -> None:
        self.points = []

    def record(self, platform, metric, value, note="", **kw) -> None:
        self.points.append((platform, metric, value))


async def test_run_sums_all_collectors(monkeypatch: pytest.MonkeyPatch) -> None:
    import integrations.collect as collect_mod

    async def fake_calendar(**kw):
        return 1

    async def fake_pull(**kw):
        return 5

    monkeypatch.setattr(collect_mod.jarvis_health, "collect", lambda **kw: 4)
    monkeypatch.setattr(collect_mod, "calendar_count", fake_calendar)
    monkeypatch.setattr(collect_mod.n8n_pull, "collect", fake_pull)
    assert await collect_mod.run() == 10


def test_main_prints_the_count(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import integrations.collect as collect_mod

    async def fake_run():
        return 7

    monkeypatch.setattr(collect_mod, "run", fake_run)
    assert collect_mod.main() == 0
    assert "collected 7 metric points" in capsys.readouterr().out


