"""friday · scripts/rotate_logs.py

Copytruncate log rotation for the launchd agents' logs (data/logs/*.log).
Each agent writes via a launchd stdout/stderr redirect held open in APPEND mode
across restarts — so we must NOT rename or delete the live file (that orphans
the agent's fd). Instead: gzip the contents to a timestamped archive, then
truncate the original to zero — the same inode, now empty, keeps receiving
writes. Archives older than the keep window are pruned.

Run hourly by com.friday.logrotate; `python -m scripts.rotate_logs` by hand.
"""

import gzip
import shutil
import sys
import time
from pathlib import Path

from config.settings import get_settings

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_KEEP_DAYS = 7


def _stamp(mtime: float) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(mtime))


def rotate(logs_dir: Path, max_bytes: int = _MAX_BYTES, keep_days: int = _KEEP_DAYS) -> int:
    """Rotate over-limit *.log files and prune stale *.log.gz archives.
    Returns how many logs were rotated this pass."""
    logs_dir = Path(logs_dir)
    if not logs_dir.is_dir():
        return 0

    rotated = 0
    for log in logs_dir.glob("*.log"):
        if log.stat().st_size < max_bytes:
            continue
        archive = logs_dir / f"{log.stem}.{_stamp(log.stat().st_mtime)}.log.gz"
        # ponytail: gzip-then-truncate loses the handful of lines written in the
        #   gap; acceptable for logs. copytruncate keeps the agent's append fd valid.
        with log.open("rb") as src, gzip.open(archive, "wb") as dst:
            shutil.copyfileobj(src, dst)
        log.write_bytes(b"")  # truncate in place — same inode the agent holds
        rotated += 1

    cutoff = time.time() - keep_days * 86400
    for archive in logs_dir.glob("*.log.gz"):
        if archive.stat().st_mtime < cutoff:
            archive.unlink(missing_ok=True)
    return rotated


def main() -> int:
    count = rotate(Path(get_settings().logs_dir))
    print(f"rotated {count} log(s); pruned archives older than {_KEEP_DAYS}d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
