#!/usr/bin/env bash
# Platapicker Setup — run this once to install Platapicker on your Mac.
# No third-party software required. Uses Python 3 that comes with macOS.
#
# Usage:
#   1. Unzip the Platapicker download
#   2. Open Terminal, drag this file into it, press Enter

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VENV_DIR="$HOME/Library/Application Support/platapicker/venv"
APP_NAME="Platapicker.app"
INSTALL_DIR="/Applications"

echo ""
echo -e "${BOLD}🦆  Platapicker Setup${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Find Python 3 ────────────────────────────────────────────── #

echo -e "${BOLD}▶ Checking Python 3...${NC}"

PYTHON=""
for candidate in python3 /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if command -v "$candidate" &>/dev/null 2>&1; then
    VERSION=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    MAJOR=$(echo "$VERSION" | cut -d. -f1)
    MINOR=$(echo "$VERSION" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$candidate"
      echo -e "  ${GREEN}✓${NC} Found Python $VERSION at $candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo ""
  echo -e "  ${RED}✗ Python 3.9+ not found.${NC}"
  echo ""
  echo "  Your Mac needs Python 3.9 or later."
  echo "  Open the App Store and search for 'Python' — it's free."
  echo "  Or visit: https://www.python.org/downloads/macos/"
  echo ""
  exit 1
fi

# ── Step 2: Create virtual environment ──────────────────────────────── #

echo ""
echo -e "${BOLD}▶ Setting up Python environment...${NC}"

mkdir -p "$(dirname "$VENV_DIR")"

if [ -d "$VENV_DIR" ]; then
  echo -e "  ${YELLOW}↻${NC} Existing environment found — updating..."
  "$VENV_DIR/bin/pip" install --upgrade pip --quiet
else
  "$PYTHON" -m venv "$VENV_DIR"
  echo -e "  ${GREEN}✓${NC} Created Python environment"
fi

# ── Step 3: Install Python packages ─────────────────────────────────── #

echo ""
echo -e "${BOLD}▶ Installing packages (this takes ~60 seconds the first time)...${NC}"

# Find requirements.txt — either next to this script or inside the .app
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQS=""
for loc in \
  "$SCRIPT_DIR/requirements.txt" \
  "$SCRIPT_DIR/$APP_NAME/Contents/Resources/requirements.txt"; do
  if [ -f "$loc" ]; then
    REQS="$loc"
    break
  fi
done

if [ -z "$REQS" ]; then
  echo -e "  ${RED}✗ requirements.txt not found${NC}"
  exit 1
fi

"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$REQS" --quiet

echo -e "  ${GREEN}✓${NC} Packages installed"

# ── Step 4: Install the app ──────────────────────────────────────────── #

echo ""
echo -e "${BOLD}▶ Installing Platapicker.app...${NC}"

APP_SRC="$SCRIPT_DIR/$APP_NAME"

if [ ! -d "$APP_SRC" ]; then
  echo -e "  ${YELLOW}!${NC} $APP_NAME not found next to this script — skipping install to /Applications"
  echo -e "    (If you already moved it there manually, that's fine)"
else
  if [ -d "$INSTALL_DIR/$APP_NAME" ]; then
    echo -e "  ${YELLOW}↻${NC} Replacing existing install..."
    rm -rf "$INSTALL_DIR/$APP_NAME"
  fi
  cp -r "$APP_SRC" "$INSTALL_DIR/"
  echo -e "  ${GREEN}✓${NC} Installed to /Applications/Platapicker.app"
fi

# ── Done ─────────────────────────────────────────────────────────────── #

echo ""
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}✅  Setup complete!${NC}"
echo ""
echo "  Open Platapicker from your Applications folder"
echo "  (or Spotlight: ⌘ Space → 'Platapicker')"
echo ""

# Offer to open the app right now
if [ -d "$INSTALL_DIR/$APP_NAME" ]; then
  read -r -p "  Open Platapicker now? [Y/n] " REPLY
  REPLY=${REPLY:-Y}
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    open "$INSTALL_DIR/$APP_NAME"
  fi
fi
