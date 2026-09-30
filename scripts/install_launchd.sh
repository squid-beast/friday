#!/usr/bin/env bash
# friday · install (or remove) the launchd agents. Idempotent.
# Usage:
#   bash scripts/install_launchd.sh                  # the always-on core (launchd/*.plist)
#   ON_DEMAND=phone bash scripts/install_launchd.sh      # load one on-demand group only
#   ON_DEMAND_OFF=phone bash scripts/install_launchd.sh  # unload + remove that group only
#   bash scripts/install_launchd.sh --uninstall      # remove core + every on-demand group
# On-demand groups live in launchd/on-demand/<group>/ (phone = LiveKit + voiceworker,
# needs Docker Desktop running). The core install never touches them.
set -euo pipefail
shopt -s nullglob

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
STATE_DIR="${FRIDAY_STATE_DIR:-$HOME/Library/Application Support/Friday}"
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
DOCKER="$(command -v docker || echo /usr/local/bin/docker)"
CLOUDFLARED="$(command -v cloudflared || echo /opt/homebrew/bin/cloudflared)"

mkdir -p "$AGENTS_DIR" "$STATE_DIR/logs"

remove() {  # unload + delete one installed agent (template path -> installed name)
  local target="$AGENTS_DIR/$(basename "$1")"
  launchctl unload "$target" 2>/dev/null || true
  rm -f "$target"
  echo "removed $(basename "$1")"
}

install() {  # render placeholders, (re)load
  local target="$AGENTS_DIR/$(basename "$1")"
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__STATE__|$STATE_DIR|g" \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__UV__|$UV|g" \
      -e "s|__DOCKER__|$DOCKER|g" \
      -e "s|__CLOUDFLARED__|$CLOUDFLARED|g" \
      "$1" > "$target"
  launchctl unload "$target" 2>/dev/null || true
  launchctl load "$target"
  echo "loaded $(basename "$1")"
}

group_dir() {
  local dir="$REPO/launchd/on-demand/$1"
  [[ -d "$dir" ]] || { echo "unknown on-demand group: $1" >&2; exit 2; }
  echo "$dir"
}

if [[ "${1:-}" == "--uninstall" ]]; then
  for t in "$REPO"/launchd/*.plist "$REPO"/launchd/on-demand/*/*.plist; do remove "$t"; done
elif [[ -n "${ON_DEMAND_OFF:-}" ]]; then
  dir="$(group_dir "$ON_DEMAND_OFF")"  # assignment: an unknown group aborts under set -e
  for t in "$dir"/*.plist; do remove "$t"; done
  if [[ "$ON_DEMAND_OFF" == "phone" ]]; then  # the LiveKit container outlives its agent
    (cd "$REPO" && "$DOCKER" compose down 2>/dev/null) || true
  fi
elif [[ -n "${ON_DEMAND:-}" ]]; then
  dir="$(group_dir "$ON_DEMAND")"
  for t in "$dir"/*.plist; do install "$t"; done
else
  for t in "$REPO"/launchd/*.plist; do install "$t"; done
fi
