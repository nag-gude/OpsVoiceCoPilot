#!/usr/bin/env bash
# Run one of gateway, agent, or tools. Used by Cloud Run (SERVICE_NAME env) and docker-compose overrides.
# Default: gateway (for single-container run).
set -e
SERVICE="${SERVICE_NAME:-gateway}"
case "$SERVICE" in
  gateway) exec python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port "${PORT:-8080}" ;;
  agent)   exec python -m uvicorn services.agent.main:app --host 0.0.0.0 --port "${PORT:-8080}" ;;
  tools)   exec python -m uvicorn services.tools.main:app --host 0.0.0.0 --port "${PORT:-8080}" ;;
  *)       echo "Unknown SERVICE_NAME=$SERVICE (gateway|agent|tools)" ; exit 1 ;;
esac
