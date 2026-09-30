"""friday · tests/unit/test_metrics_store.py

integrations/store.py: roundtrip, windowing, summary grouping, missing db.
"""

from pathlib import Path

from integrations.store import record, series, summary


def test_record_and_series_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "metrics.db"
    record("instagram", "reel_views_7d", 1200, db=db)
    record("instagram", "reel_views_7d", 1500, "after reel drop", db=db)
    points = series("instagram", "reel_views_7d", db=db)
    assert [p.value for p in points] == [1200.0, 1500.0]
    assert points[1].note == "after reel drop"


def test_series_filters_platform_and_metric(tmp_path: Path) -> None:
    db = tmp_path / "metrics.db"
    record("instagram", "reel_views_7d", 1, db=db)
    record("leads", "new_leads_7d", 2, db=db)
    assert [p.value for p in series("leads", "new_leads_7d", db=db)] == [2.0]
    assert series("leads", "reel_views_7d", db=db) == []


def test_summary_groups_by_platform_then_metric(tmp_path: Path) -> None:
    db = tmp_path / "metrics.db"
    record("bookyourslot", "bookings_7d", 9, db=db)
    record("bookyourslot", "mrr", 35, db=db)
    record("friday", "wakes_24h", 4, db=db)
    data = summary(db=db)
    assert set(data) == {"bookyourslot", "friday"}
    assert set(data["bookyourslot"]) == {"bookings_7d", "mrr"}
    assert data["friday"]["wakes_24h"][0].value == 4.0


def test_missing_db_reads_empty(tmp_path: Path) -> None:
    assert series("x", "y", db=tmp_path / "nope.db") == []
    assert summary(db=tmp_path / "nope.db") == {}
