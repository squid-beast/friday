#!/usr/bin/env bash
# friday · scripts/snapshot.sh — timestamped local backup (NO git).
# rsync SOURCE_DIR (default: repo root) -> SNAPSHOT_DIR (default: ~/friday-snapshots)/friday-YYYYMMDD-HHMM/
# Excludes data/, reference/, .venv, __pycache__, caches. Keeps the newest 20 snapshots.
set -euo pipefail

SRC="${SOURCE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST_ROOT="${SNAPSHOT_DIR:-$HOME/friday-snapshots}"
DEST="$DEST_ROOT/friday-$(date +%Y%m%d-%H%M)"

mkdir -p "$DEST"
rsync -a \
  --exclude 'data/' \
  --exclude 'reference/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude 'ui/node_modules/' \
  --exclude 'ui/.svelte-kit/' \
  "$SRC/" "$DEST/"

# Prune to the newest 20 by name (friday-YYYYMMDD-HHMM sorts chronologically).
# Glob, never `ls` parsing: a hostile name (embedded newline) must not be able
# to turn into a cwd-relative rm -rf outside DEST_ROOT.
shopt -s nullglob
snaps=("$DEST_ROOT"/friday-*/)
count=${#snaps[@]}
if (( count > 20 )); then
  for old in "${snaps[@]:0:count-20}"; do rm -rf "$old"; done
fi

echo "snapshot: $DEST"
