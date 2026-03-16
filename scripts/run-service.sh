#!/usr/bin/env bash

set -e

SERVICE="${SERVICE_NAME:-gateway}"
PORT="${PORT:-8080}"

echo "Starting $SERVICE on port $PORT"

case "$SERVICE" in

gateway)
exec uvicorn ops_voice_copilot.gateway.main:app \
--host 0.0.0.0 \
--port "$PORT" \
--workers 1
;;

agent)
exec uvicorn ops_voice_copilot.agent.main:app \
--host 0.0.0.0 \
--port "$PORT" \
--workers 1
;;

tools)
exec uvicorn ops_voice_copilot.tools.main:app \
--host 0.0.0.0 \
--port "$PORT" \
--workers 1
;;

*)
echo "Unknown SERVICE_NAME=$SERVICE"
exit 1
;;

esac