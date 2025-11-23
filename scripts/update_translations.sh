#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(dirname "$0")/..
cd "$ROOT_DIR/geo_search"

if ! command -v lupdate >/dev/null 2>&1; then
  echo "lupdate not found in PATH. On Ubuntu, install: sudo apt-get install qttools5-dev-tools"
  echo "On Windows, ensure Qt Linguist tools are installed and lupdate is on PATH."
  exit 2
fi

echo "Running lupdate to update .ts files..."
lupdate . -no-obsolete -ts i18n/*.ts

echo "Running lrelease to build .qm files..."
lrelease i18n/*.ts || true

echo "Done. Review changes and commit if OK."
