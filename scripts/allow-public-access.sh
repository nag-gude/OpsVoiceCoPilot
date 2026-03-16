#!/usr/bin/env bash
# Allow public (unauthenticated) access to the Cloud Run UI so anyone can open and test the app.
# Run from project root. Usage: ./scripts/allow-public-access.sh [PROJECT_ID] [REGION]
set -e
PROJECT_ID="${1:-$GOOGLE_CLOUD_PROJECT}"
REGION="${2:-europe-west1}"
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 PROJECT_ID [REGION]"
  echo "Or set GOOGLE_CLOUD_PROJECT"
  exit 1
fi
echo "Allowing public access to Cloud Run services (project=$PROJECT_ID region=$REGION)..."
for SVC in ops-voice-copilot ops-voice-copilot-agent ops-voice-copilot-tools; do
  gcloud run services add-iam-policy-binding "$SVC" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet 2>/dev/null && echo "  $SVC: public" || echo "  $SVC: skip (not found or already set)"
done
echo "Done. Open the Gateway URL to test (no sign-in required):"
gcloud run services describe ops-voice-copilot --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "  Run: gcloud run services describe ops-voice-copilot --region $REGION --format='value(status.url)'"
