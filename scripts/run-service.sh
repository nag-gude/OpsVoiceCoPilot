#!/usr/bin/env bash
# Entry point for Ops Voice Co-Pilot services (gateway|agent|tools)
# Ensures PORT is set and prints debug info.

set -euo pipefail

# Default service and port
SERVICE="${SERVICE_NAME:-gateway}"
PORT="${PORT:-8080}"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting service: $SERVICE on port $PORT"

# Function to check that uvicorn is installed
check_uvicorn() {
    if ! command -v uvicorn >/dev/null 2>&1; then
        echo "Error: uvicorn not installed!"
        exit 1
    fi
}

check_uvicorn

# Run the requested service
case "$SERVICE" in
  gateway)
    exec uvicorn services.gateway.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --ws websockets \
        --log-level info
    ;;
  agent)
    exec uvicorn services.agent.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --ws websockets \
        --log-level info
    ;;
  tools)
    exec uvicorn services.tools.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --ws websockets \
        --log-level info
    ;;
  *)
    echo "Unknown SERVICE_NAME='$SERVICE' (expected gateway|agent|tools)"
    exit 1
    ;;
esac