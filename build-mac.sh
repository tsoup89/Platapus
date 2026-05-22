#!/usr/bin/env bash
# build-mac.sh — Build Platapicker.app for macOS
# Usage: ./build-mac.sh
#
# Prerequisites:
#   • Node.js 18+ and npm
#   • Python 3.11+ with .venv already set up:
#       python3 -m venv .venv
#       source .venv/bin/activate
#       pip install -r requirements.txt
#       playwright install chromium

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo ""
echo "🦆  Building Platapicker.app"
echo "================================"

# ── 1. Check prerequisites ───────────────────────────────────────────── #
echo ""
echo "▶ Checking prerequisites..."

if ! command -v node &>/dev/null; then
  echo "❌  Node.js not found. Install from https://nodejs.org"
  exit 1
fi
echo "   Node.js $(node --version)"

if ! command -v npm &>/dev/null; then
  echo "❌  npm not found."
  exit 1
fi

if [ ! -f ".venv/bin/python" ] && [ ! -f ".venv/bin/python3" ]; then
  echo "❌  Python venv not found."
  echo "    Run:  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
echo "   Python venv ✓"

# ── 2. Install Electron deps ─────────────────────────────────────────── #
echo ""
echo "▶ Installing Electron dependencies..."
npm install --prefer-offline 2>&1 | tail -3

# ── 3. Build React frontend ──────────────────────────────────────────── #
echo ""
echo "▶ Building React frontend..."
cd frontend
npm install --prefer-offline 2>&1 | tail -3
npm run build
cd ..
echo "   frontend/dist ✓"

# ── 4. Package with electron-builder ────────────────────────────────── #
echo ""
echo "▶ Packaging .app (this may take a minute)..."
npx electron-builder --mac --dir

# ── 5. Report ────────────────────────────────────────────────────────── #
APP_PATH="$(find dist-electron -name '*.app' | head -1)"
if [ -n "$APP_PATH" ]; then
  echo ""
  echo "✅  Done!"
  echo ""
  echo "   App:  $APP_PATH"
  echo ""
  echo "   To run it:"
  echo "     open \"$APP_PATH\""
  echo ""
  echo "   To install:"
  echo "     cp -r \"$APP_PATH\" /Applications/"
  echo ""
else
  echo ""
  echo "⚠️  Build finished but .app not found in dist-electron/."
  echo "   Check the electron-builder output above."
fi
