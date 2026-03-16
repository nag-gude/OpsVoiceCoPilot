#!/usr/bin/env bash
# Deploy Ops Voice Co-Pilot (microservices) to Cloud Run: Tools, Agent, Gateway.
# Usage: ./scripts/deploy-cloudrun.sh [PROJECT_ID] [REGION]
# Output: Gateway URL (user-facing). Requires gcloud and Docker/source build.
set -e
PROJECT_ID="${1:-$GOOGLE_CLOUD_PROJECT}"
REGION="${2:-europe-west1}"
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 PROJECT_ID [REGION]"
  echo "Or set GOOGLE_CLOUD_PROJECT"
  exit 1
fi
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com vertexai.googleapis.com logging.googleapis.com --quiet

# 1. Deploy Tools (no service deps)
echo "Deploying Tools service..."
gcloud run deploy ops-voice-copilot-tools \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --no-use-http2 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,SERVICE_NAME=tools" \
  --quiet
TOOLS_URL=$(gcloud run services describe ops-voice-copilot-tools --region "$REGION" --format='value(status.url)')
echo "Tools URL: $TOOLS_URL"

# 2. Deploy Agent (depends on Tools)
echo "Deploying Agent service..."
gcloud run deploy ops-voice-copilot-agent \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --no-use-http2 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,VERTEX_AI_LOCATION=$REGION,TOOLS_SERVICE_URL=$TOOLS_URL,SERVICE_NAME=agent" \
  --quiet
AGENT_URL=$(gcloud run services describe ops-voice-copilot-agent --region "$REGION" --format='value(status.url)')
echo "Agent URL: $AGENT_URL"

# 3. Deploy Gateway (depends on Agent) — user-facing
echo "Deploying Gateway service..."
gcloud run deploy ops-voice-copilot \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --no-use-http2 \
  --set-env-vars "AGENT_SERVICE_URL=$AGENT_URL,SERVICE_NAME=gateway" \
  --quiet
GATEWAY_URL=$(gcloud run services describe ops-voice-copilot --region "$REGION" --format='value(status.url)')

echo "Done. User-facing URL (Gateway): $GATEWAY_URL"
echo "Set IAM (Vertex AI User + Logs Viewer) on the service accounts for Agent and Tools if not already set."
