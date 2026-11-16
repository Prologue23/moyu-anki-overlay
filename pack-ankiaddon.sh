#!/usr/bin/env bash
# Build a .ankiaddon for https://ankiweb.net/shared/upload
# Zip must contain files at the root (not a wrapping folder), no __pycache__.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$ROOT/dist"
NAME="moyu_anki_overlay"
OUT="$OUT_DIR/${NAME}.ankiaddon"

rm -rf "$ROOT"/__pycache__ "$ROOT"/*/__pycache__ 2>/dev/null || true
mkdir -p "$OUT_DIR"
rm -f "$OUT"

# Only ship runtime files (exclude tooling / git / local scripts)
cd "$ROOT"
zip -r "$OUT" \
  __init__.py \
  overlay.py \
  review_controller.py \
  rich_card.py \
  config_dialog.py \
  config.json \
  config.md \
  manifest.json \
  README.md \
  -x '*/__pycache__/*' '*.pyc' '.DS_Store'

echo "Built: $OUT"
unzip -l "$OUT"
