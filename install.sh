#!/usr/bin/env bash
# Platapicker installer — sets up a systemd service that runs on boot
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_USER="$(logname 2>/dev/null || echo "$USER")"
SERVICE_NAME="platapicker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV="$INSTALL_DIR/.venv"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${YELLOW}──${NC} $*"; }

# ── Preflight checks ──────────────────────────────────────────────────────────

step "Checking dependencies"

command -v python3 >/dev/null || error "python3 not found. Install it with: sudo apt install python3 python3-pip python3-venv"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)"; then
    info "Python $PYTHON_VERSION"
else
    error "Python 3.11+ required, found $PYTHON_VERSION"
fi

command -v node >/dev/null || error "node not found. Install it with: sudo apt install nodejs npm"
NODE_VERSION=$(node --version)
info "Node $NODE_VERSION"

command -v npm >/dev/null || error "npm not found"

if [[ $EUID -ne 0 ]]; then
    warn "Not running as root — will use sudo for systemd steps"
    SUDO="sudo"
else
    SUDO=""
fi

# ── Python virtualenv ─────────────────────────────────────────────────────────

step "Setting up Python virtualenv"

if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
    info "Created $VENV"
else
    info "Reusing existing $VENV"
fi

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
info "Python dependencies installed"

# Install Playwright browser (needed for Facebook/AuctionNinja scrapers)
if "$VENV/bin/python" -m playwright install chromium --with-deps 2>/dev/null; then
    info "Playwright Chromium installed"
else
    warn "Playwright browser install failed — Facebook/AuctionNinja scraping will use fallbacks"
fi

# ── Frontend build ────────────────────────────────────────────────────────────

step "Building frontend"

cd "$INSTALL_DIR/frontend"
npm install --silent
npm run build
cd "$INSTALL_DIR"
info "Frontend built → frontend/dist"

# ── Create .env if missing ────────────────────────────────────────────────────

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    step "Creating .env from template"
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    info "Created .env — edit it to add Discord webhooks, Facebook credentials, etc."
else
    info ".env already exists, skipping"
fi

# ── Systemd service file ──────────────────────────────────────────────────────

step "Installing systemd service"

$SUDO tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Platapicker deal monitoring service
Documentation=https://github.com/tsoup89/Platapus
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=10
TimeoutStopSec=20
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$INSTALL_DIR

# Write logs to journald (view with: journalctl -u platapicker -f)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=platapicker

# Protect the system while allowing network + file access
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

info "Wrote $SERVICE_FILE"

$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE_NAME"
info "Service enabled (will start on boot)"

# ── Start / restart the service ───────────────────────────────────────────────

step "Starting service"

if $SUDO systemctl is-active --quiet "$SERVICE_NAME"; then
    $SUDO systemctl restart "$SERVICE_NAME"
    info "Service restarted"
else
    $SUDO systemctl start "$SERVICE_NAME"
    info "Service started"
fi

sleep 2

if $SUDO systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Platapicker is running!                         ║${NC}"
    echo -e "${GREEN}║                                                  ║${NC}"
    echo -e "${GREEN}║  Dashboard:  http://localhost:8000               ║${NC}"
    echo -e "${GREEN}║  Logs:       journalctl -u platapicker -f        ║${NC}"
    echo -e "${GREEN}║  Status:     systemctl status platapicker        ║${NC}"
    echo -e "${GREEN}║  Stop:       sudo systemctl stop platapicker     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
else
    error "Service failed to start. Check logs: journalctl -u platapicker -n 50"
fi
