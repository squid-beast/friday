"""friday · tests/unit/test_metrics_voice.py

Spoken metrics digest: deterministic, grounded in the store, platform-filtered
by what sir actually asked. No LLM in this layer by design.
"""

from pathlib import Path

import pytest

import integrations.store as store_mod
from integrations.metrics_voice import report
from integrations.store import record


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "metrics.db"
    monkeypatch.setattr(store_mod, "_DB", db)
    record("instagram", "reel_views_7d", 15000, db=db)
    record("instagram", "reel_views_7d", 19300, db=db)
    record("bookyourslot", "mrr_usd", 133, db=db)


async def test_platform_question_filters_to_that_platform(seeded) -> None:
    text = await report("", "how did the reels do this week?")
    assert "instagram reel_views_7d: 19300 (up 4300 vs previous)" in text
    assert "bookyourslot" not in text


async def test_general_question_reads_the_whole_board(seeded) -> None:
    text = await report("", "give me the numbers")
    assert "instagram" in text and "bookyourslot mrr_usd: 133" in text


async def test_empty_store_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_mod, "_DB", tmp_path / "empty.db")
    assert "store is empty" in await report("", "how are the reels doing?")
