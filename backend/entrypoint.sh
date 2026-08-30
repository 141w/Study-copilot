#!/bin/bash
set -euo pipefail

echo "🚀 Study Copilot - Entrypoint"

# Ensure data directories exist
mkdir -p /app/uploads /app/vectorstore /app/.embedding_cache

# Test nginx config
nginx -t

# Start nginx (foreground, root — nginx drops to www-data worker)
echo "🌐 Starting nginx..."
nginx

# Start uvicorn (background) — run as appuser if available
echo "🐍 Starting uvicorn..."
if id appuser &>/dev/null; then
    su -s /bin/bash appuser -c \
        "cd /app && exec uvicorn app.main:app --host 127.0.0.1 --port 8000" &
else
    uvicorn app.main:app --host 127.0.0.1 --port 8000 &
fi
UVICORN_PID=$!

# Wait for either process to exit
wait -n

# Clean up
kill $UVICORN_PID 2>/dev/null || true
wait $UVICORN_PID 2>/dev/null || true
