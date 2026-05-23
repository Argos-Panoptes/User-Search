#!/usr/bin/env bash
docker compose up -d

URL="http://localhost:5173"

if command -v xdg-open >/dev/null 2>&1; then
  # Linux
  xdg-open "$URL"
elif command -v open >/dev/null 2>&1; then
  # macOS
  open "$URL"
elif command -v start >/dev/null 2>&1; then
  # Windows (Git Bash)
  start "$URL"
else
  echo "No idea how to open a browser on this system."
  echo "Open this manually: $URL"
fi