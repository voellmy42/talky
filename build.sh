#!/bin/bash
# build.sh — build and sign Talky.app for distribution on other Macs
set -e

echo "==> Activating virtualenv..."
source .venv/bin/activate

echo "==> Running PyInstaller..."
pyinstaller talky.spec --clean --noconfirm

echo "==> Re-signing all nested binaries (adhoc, no hardened runtime)..."
# Note: --options runtime breaks PyInstaller bundles; simple adhoc signing is correct here.
codesign --force --deep --sign - dist/Talky.app

echo ""
echo "✅ Build complete: dist/Talky.app"
echo ""
echo "To install on another Mac, run this on the OTHER machine:"
echo "  xattr -cr ~/Desktop/Talky.app"
echo "  sudo spctl --master-disable   # temporarily allow any app"
echo "  open ~/Desktop/Talky.app"
echo "  sudo spctl --master-enable    # re-enable Gatekeeper after first launch"
