#!/bin/bash
# build.sh — build and sign Talky.app for distribution on other Macs
set -euo pipefail

TALKY_DIST_PATH="${TALKY_DIST_PATH:-dist}"
TALKY_BUILD_PATH="${TALKY_BUILD_PATH:-build}"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$PWD/build/pyinstaller-cache}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$PWD/build/python-cache}"

echo "==> Activating virtualenv..."
source .venv/bin/activate

echo "==> Running PyInstaller..."
pyinstaller talky.spec --clean --noconfirm --distpath "$TALKY_DIST_PATH" --workpath "$TALKY_BUILD_PATH"

echo "==> Signing the local development build..."
codesign --force --deep --sign - "$TALKY_DIST_PATH/Talky.app"
codesign --verify --deep --strict "$TALKY_DIST_PATH/Talky.app"

echo "Build complete: $TALKY_DIST_PATH/Talky.app"
echo "   You can now open it by double-clicking in Finder."
echo ""
echo "This is an ad-hoc signed development build."
echo "Sharing broadly requires Developer ID signing and notarization."
