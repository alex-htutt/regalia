#!/usr/bin/env sh
# Build the standalone Regalia app (macOS/Linux). Windows: build.bat.
# Run from the dashboard/ folder. Output lands in dist/ (onefile).
set -e
cd "$(dirname "$0")"
pip install -r requirements.txt -r requirements-dev.txt
pyinstaller --noconfirm regalia.spec
echo
echo "Built → dist/Regalia  (macOS also: dist/Regalia.app)"
