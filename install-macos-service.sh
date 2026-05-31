#!/usr/bin/env bash
# Platapicker — install an always-on macOS LaunchAgent.
#
# Runs the FastAPI backend (and its scheduler) in the background, so deal
# scraping + Discord alerts keep firing even when the Electron app is closed.
# The Electron app detects this backend and attaches to it instead of spawning
# a second one.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$INSTALL_DIR/.venv"
PYTHON="$VENV/bin/python"
DATA_DIR="$HOME/Library/Application Support/Platapicker"
LOG_DIR="$DATA_DIR/logs"
LABEL="com.platapicker.backend"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Preflight ──────────────────────────────────────────────────────────────
[[ -x "$PYTHON" ]] || error "venv python not found at $PYTHON — run ./setup.sh first."
[[ -f "$INSTALL_DIR/run.py" ]] || error "run.py not found in $INSTALL_DIR"

mkdir -p "$DATA_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
info "Data dir: $DATA_DIR"

# ── Write the LaunchAgent plist ────────────────────────────────────────────
# PLATAPICKER_DATA_DIR pins the backend to the SAME database the Electron app
# uses, so history/alerts/settings are shared. Setting it also makes run.py
# disable uvicorn hot-reload (production mode). Host is 127.0.0.1 — local only.
# For physical-phone mobile testing, run a TEMPORARY 0.0.0.0 backend instead
# (see mobile/README or: APP_HOST=0.0.0.0 .venv/bin/python run.py); don't expose
# the always-on service. The iOS Simulator can reach 127.0.0.1 with no exposure.
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$INSTALL_DIR/run.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PLATAPICKER_DATA_DIR</key>
        <string>$DATA_DIR</string>
        <key>DATABASE_URL</key>
        <string>sqlite:///$DATA_DIR/platapicker.db</string>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
        <key>APP_HOST</key>
        <string>127.0.0.1</string>
        <key>APP_PORT</key>
        <string>8000</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/backend.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/backend.err.log</string>
</dict>
</plist>
EOF
info "Wrote $PLIST"

# ── (Re)load it ────────────────────────────────────────────────────────────
# bootout first so a re-run picks up changes; ignore error if not yet loaded.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
info "Service loaded (will start now and on every login)."

# ── Verify ─────────────────────────────────────────────────────────────────
echo "Waiting for backend to come up..."
for i in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:8000/api/health" >/dev/null 2>&1 \
       || curl -fsS "http://127.0.0.1:8000/api/overview" >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Platapicker backend is running (always-on)            ║${NC}"
        echo -e "${GREEN}║                                                        ║${NC}"
        echo -e "${GREEN}║  Dashboard:  http://localhost:8000                     ║${NC}"
        echo -e "${GREEN}║  Logs:       tail -f \"$LOG_DIR\"/backend.*.log         ║${NC}"
        echo -e "${GREEN}║  Status:     launchctl print gui/\$(id -u)/$LABEL       ║${NC}"
        echo -e "${GREEN}║  Uninstall:  ./uninstall-macos-service.sh              ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
        echo ""
        exit 0
    fi
    sleep 1
done

warn "Service loaded but health check didn't pass in time."
warn "Check the logs: tail -n 50 \"$LOG_DIR/backend.err.log\""
exit 1
