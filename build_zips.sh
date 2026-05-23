#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Building Frontend ==="
cd "$ROOT_DIR/frontend"
npm install
npm run build
echo "Zipping frontend build..."
cd "$ROOT_DIR"
zip -r frontend.zip frontend/dist/

echo ""
echo "=== Zipping Backend ==="
cd "$ROOT_DIR"
zip -r backend.zip backend/ \
  -x "backend/__pycache__/*" \
  -x "backend/**/__pycache__/*" \
  -x "backend/*.pyc" \
  -x "backend/**/*.pyc" \
  -x "backend/.env" \
  -x "backend/celerybeat-schedule.*"

echo ""
echo "=== Done ==="
ls -lh "$ROOT_DIR/frontend.zip" "$ROOT_DIR/backend.zip"
