"""scripts/snapshot.sh — the no-git rollback mechanism (safety: TDD, written first).

Overrides: SOURCE_DIR (what to copy), SNAPSHOT_DIR (where snapshots land).
"""

import os
import re
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "snapshot.sh"
NAME_RE = re.compile(r"^jarvis-\d{8}-\d{4}$")


def run_snapshot(
    source: Path, dest: Path, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ | {"SOURCE_DIR": str(source), "SNAPSHOT_DIR": str(dest)}
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def make_source(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    for f in (
        "Makefile",
        "config/settings.py",
        "data/audit.db",
        "reference/upstream.py",
        ".venv/lib.py",
        "brain/__pycache__/graph.pyc",
    ):
        p = src / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return src


def test_creates_browsable_timestamped_copy(tmp_path: Path) -> None:
    dest = tmp_path / "snaps"
    result = run_snapshot(make_source(tmp_path), dest)
    assert result.returncode == 0, result.stderr
    snaps = [d for d in dest.iterdir() if d.is_dir()]
    assert len(snaps) == 1
    assert NAME_RE.match(snaps[0].name)
    assert (snaps[0] / "Makefile").exists()
    assert (snaps[0] / "config" / "settings.py").exists()


def test_excludes_data_reference_venv_pycache(tmp_path: Path) -> None:
    dest = tmp_path / "snaps"
    run_snapshot(make_source(tmp_path), dest)
    snap = next(d for d in dest.iterdir() if d.is_dir())
    for excluded in ("data", "reference", ".venv", "brain/__pycache__"):
        assert not (snap / excluded).exists(), f"{excluded} should not be in snapshots"


def test_prunes_to_last_20(tmp_path: Path) -> None:
    dest = tmp_path / "snaps"
    dest.mkdir()
    now = time.time()
    for i in range(21):  # oldest = jarvis-20240101-0000, newest seeded = -0020
        old = dest / f"jarvis-20240101-{i:04d}"
        old.mkdir()
        os.utime(old, (now - 3600 + i, now - 3600 + i))
    result = run_snapshot(make_source(tmp_path), dest)
    assert result.returncode == 0, result.stderr
    remaining = sorted(d.name for d in dest.iterdir() if d.is_dir())
    assert len(remaining) == 20
    assert "jarvis-20240101-0000" not in remaining  # two oldest pruned
    assert "jarvis-20240101-0001" not in remaining
    assert any(NAME_RE.match(n) and not n.startswith("jarvis-20240101") for n in remaining)


def test_prune_cannot_delete_outside_snapshot_dir(tmp_path: Path) -> None:
    """A hostile dir name with an embedded newline must never make the prune
    rm -rf a cwd-relative path (make snapshot runs from the project root)."""
    dest = tmp_path / "snaps"
    dest.mkdir()
    workdir = tmp_path / "cwd"
    victim = workdir / "VICTIM"
    victim.mkdir(parents=True)
    hostile = dest / "jarvis-evil\nVICTIM"
    hostile.mkdir()
    now = time.time()
    os.utime(hostile, (now - 7200, now - 7200))  # oldest -> prune candidate
    for i in range(24):
        old = dest / f"jarvis-20240101-{i:04d}"
        old.mkdir()
        os.utime(old, (now - 3600 + i, now - 3600 + i))
    result = run_snapshot(make_source(tmp_path), dest, cwd=workdir)
    assert result.returncode == 0, result.stderr
    assert victim.exists(), "prune escaped SNAPSHOT_DIR and deleted from cwd"
