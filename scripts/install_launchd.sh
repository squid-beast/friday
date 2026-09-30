#!/usr/bin/env bash
# jarvis-life-os · install (or --uninstall) the launchd agents. Idempotent.
# Usage: bash scripts/install_launchd.sh [--uninstall]
# Docker Desktop itself must be set to start at login (its own preference);
# the livekit agent retries `docker compose up -d` until it succeeds.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
STATE_DIR="${FRIDAY_STATE_DIR:-$HOME/Library/Application Support/Friday}"
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
DOCKER="$(command -v docker || echo /usr/local/bin/docker)"
SCREENPIPE="$(command -v screenpipe || echo /opt/homebrew/bin/screenpipe)"

mkdir -p "$AGENTS_DIR" "$STATE_DIR/logs"

for template in "$REPO"/launchd/*.plist; do
  name="$(basename "$template")"
  target="$AGENTS_DIR/$name"
  if [[ "${1:-}" == "--uninstall" ]]; then
    launchctl unload "$target" 2>/dev/null || true
    rm -f "$target"
    echo "removed $name"
    continue
  fi
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__STATE__|$STATE_DIR|g" \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__UV__|$UV|g" \
      -e "s|__DOCKER__|$DOCKER|g" \
      -e "s|__SCREENPIPE__|$SCREENPIPE|g" \
      "$template" > "$target"
  launchctl unload "$target" 2>/dev/null || true
  launchctl load "$target"
  echo "loaded $name"
done
