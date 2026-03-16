#!/usr/bin/env bash
# Build the Ops Voice Co-Pilot image and push to Artifact Registry.
# Uses gcloud builds submit (Dockerfile in repo root). Run from project root.
# Used by terraform-bootstrap.sh step 4 and for manual rebuilds.
# Usage: ./scripts/build-image.sh [PROJECT_ID] [REGION] [ARTIFACT_REGISTRY_REPO] [IMAGE_NAME]
set -e
PROJECT_ID="${1:-$GOOGLE_CLOUD_PROJECT}"
REGION="${2:-europe-west1}"
REPO="${3:-ops-voice-copilot}"
IMAGE_NAME="${4:-app}"
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 PROJECT_ID [REGION] [ARTIFACT_REGISTRY_REPO] [IMAGE_NAME]"
  echo "Or set GOOGLE_CLOUD_PROJECT"
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:latest"
gcloud builds submit . \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --tag="$IMAGE_URI"
echo "Image: $IMAGE_URI"
