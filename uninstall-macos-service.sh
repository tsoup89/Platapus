#!/usr/bin/env bash
# Platapicker — remove the always-on macOS LaunchAgent.
set -euo pipefail

LABEL="com.platapicker.backend"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && info "Service stopped." || warn "Service was not running."

if [[ -f "$PLIST" ]]; then
    rm -f "$PLIST"
    info "Removed $PLIST"
else
    warn "No plist at $PLIST"
fi

echo "Done. The always-on backend will no longer start at login."
echo "The Electron app will go back to spawning its own backend when opened."
