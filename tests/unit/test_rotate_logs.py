"""scripts/rotate_logs.py — copytruncate rotation for the launchd logs.
Over-limit logs gzip to a timestamped archive and truncate IN PLACE (the agent
keeps its append-mode fd — a rename would orphan it). Archives older than the
keep window are deleted; the live .log and fresh archives are left alone.
"""

import gzip
import os
import time
from pathlib import Path

from scripts.rotate_logs import rotate


def _write(path: Path, size: int) -> None:
    path.write_bytes(b"x" * size)


def test_over_limit_log_is_gzipped_and_truncated(tmp_path: Path) -> None:
    log = tmp_path / "dashboard.log"
    _write(log, 12 * 1024)
    rotated = rotate(tmp_path, max_bytes=10 * 1024, keep_days=7)
    assert rotated == 1
    assert log.exists() and log.stat().st_size == 0  # same file, emptied for the agent
    archives = list(tmp_path.glob("dashboard.*.log.gz"))
    assert len(archives) == 1
    with gzip.open(archives[0], "rb") as f:
        assert f.read() == b"x" * (12 * 1024)  # nothing lost


def test_under_limit_log_is_left_alone(tmp_path: Path) -> None:
    log = tmp_path / "killswitch.log"
    _write(log, 5 * 1024)
    assert rotate(tmp_path, max_bytes=10 * 1024, keep_days=7) == 0
    assert log.stat().st_size == 5 * 1024
    assert list(tmp_path.glob("*.gz")) == []


def test_archives_past_the_window_are_deleted(tmp_path: Path) -> None:
    old = tmp_path / "voiceworker.20260101-0000.log.gz"
    old.write_bytes(b"stale")
    os.utime(old, (time.time() - 8 * 86400, time.time() - 8 * 86400))  # 8 days old
    fresh = tmp_path / "voiceworker.20260115-0000.log.gz"
    fresh.write_bytes(b"recent")
    rotate(tmp_path, max_bytes=10 * 1024, keep_days=7)
    assert not old.exists() and fresh.exists()


def test_missing_dir_is_a_quiet_noop(tmp_path: Path) -> None:
    assert rotate(tmp_path / "nope", max_bytes=1, keep_days=7) == 0


def test_only_dot_log_files_rotate_not_archives_or_db(tmp_path: Path) -> None:
    _write(tmp_path / "metrics.db", 20 * 1024)  # a big db must NOT be rotated
    _write(tmp_path / "old.20260101-0000.log.gz", 20 * 1024)  # already an archive
    assert rotate(tmp_path, max_bytes=10 * 1024, keep_days=7) == 0
    assert (tmp_path / "metrics.db").stat().st_size == 20 * 1024
