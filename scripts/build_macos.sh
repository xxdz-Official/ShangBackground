#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m PyInstaller --clean --noconfirm ShangBackground-macos.spec

echo "Built: dist/ShangBackground.app"
