#!/usr/bin/env bash
# distribute.sh — Build Platapicker and create a zip ready to share with friends.
#
# What this produces:
#   dist-electron/Platapicker-[version].zip
#     ├── Platapicker.app   ← double-clickable Mac app
#     └── setup.sh          ← run once in Terminal to set up Python

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VERSION=$(node -e "console.log(require('./package.json').version)" 2>/dev/null || echo "1.0.0")
OUTPUT_ZIP="$ROOT/dist-electron/Platapicker-${VERSION}.zip"

echo ""
echo "🦆  Platapicker Distribution Build v${VERSION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Build frontend ────────────────────────────────────────────────── #
echo ""
echo "▶ Building frontend..."
cd frontend
node node_modules/vite/bin/vite.js build
cd "$ROOT"
echo "  ✓ frontend/dist built"

# ── 2. Package with electron-builder ────────────────────────────────── #
echo ""
echo "▶ Packaging .app..."
node_modules/.bin/electron-builder --mac --dir 2>&1 | grep -E "(Building|Packaging|✓|error|Error)" || true

APP_PATH=$(find dist-electron -name "*.app" -maxdepth 4 2>/dev/null | head -1)
if [ -z "$APP_PATH" ]; then
  echo "  ✗ .app not found — check electron-builder output"
  exit 1
fi
echo "  ✓ $APP_PATH"

# ── 3. Create zip ────────────────────────────────────────────────────── #
echo ""
echo "▶ Creating zip..."

mkdir -p dist-electron
rm -f "$OUTPUT_ZIP"

TMP_DIR=$(mktemp -d)
cp -r "$APP_PATH" "$TMP_DIR/Platapicker.app"
cp "$ROOT/setup.sh" "$TMP_DIR/setup.sh"
chmod +x "$TMP_DIR/setup.sh"

cd "$TMP_DIR"
zip -r "$OUTPUT_ZIP" "Platapicker.app" "setup.sh" -x "**/.DS_Store" -x "**/.__*"
cd "$ROOT"

rm -rf "$TMP_DIR"

SIZE=$(du -sh "$OUTPUT_ZIP" | cut -f1)
echo "  ✓ $OUTPUT_ZIP ($SIZE)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  Done! Share this file with your friends:"
echo ""
echo "   $OUTPUT_ZIP"
echo ""
echo "   They:"
echo "   1. Download and unzip the file"
echo "   2. Open Terminal, run: bash setup.sh"
echo "   3. Open Platapicker from /Applications"
echo ""
