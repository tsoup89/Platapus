#!/usr/bin/env bash
# Platapicker uninstaller — stops and removes the systemd service
set -euo pipefail

SERVICE_NAME="platapicker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

SUDO=""
if [[ $EUID -ne 0 ]]; then
    SUDO="sudo"
fi

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    $SUDO systemctl stop "$SERVICE_NAME"
    info "Service stopped"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    $SUDO systemctl disable "$SERVICE_NAME"
    info "Service disabled"
fi

if [[ -f "$SERVICE_FILE" ]]; then
    $SUDO rm "$SERVICE_FILE"
    $SUDO systemctl daemon-reload
    info "Removed $SERVICE_FILE"
fi

warn "App files and database were NOT deleted."
warn "To fully remove: rm -rf $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
