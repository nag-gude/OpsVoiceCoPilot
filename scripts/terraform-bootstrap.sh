#!/usr/bin/env bash
# Bootstrap: create state bucket, then run Terraform and Cloud Build one by one.
# 1) Create GCS bucket for state
# 2) Terraform init (GCS backend)
# 3) Terraform apply (targeted) — APIs + Artifact Registry + IAM so image can be pushed
# 4) Cloud Build — build and push the app image
# 5) Terraform apply (full) — Cloud Run and rest
#
# Usage: ./scripts/terraform-bootstrap.sh PROJECT_ID [BUCKET_NAME] [REGION]
# Example: ./scripts/terraform-bootstrap.sh my-project my-project-tfstate europe-west2
# Requires: terraform.tfvars in terraform/ (or set TF_VAR_* or pass -var); gcloud authenticated.
set -e
PROJECT_ID="${1:-$GOOGLE_CLOUD_PROJECT}"
BUCKET_NAME="${2:-${PROJECT_ID}-tfstate}"
REGION="${3:-europe-west1}"
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 PROJECT_ID [BUCKET_NAME] [REGION]"
  echo "Or set GOOGLE_CLOUD_PROJECT"
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TERRAFORM_DIR="$ROOT/terraform"
# Use tfvars if present
VAR_ARGS=""
if [ -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
  VAR_ARGS="-var-file=$TERRAFORM_DIR/terraform.tfvars"
else
  VAR_ARGS="-var=project_id=$PROJECT_ID -var=region=$REGION"
fi

echo "=== 1) State bucket ==="
echo "Project: $PROJECT_ID  Bucket: $BUCKET_NAME  Region: $REGION"
gcloud config set project "$PROJECT_ID"
TF_STATE_REGION="${TF_STATE_REGION:-$REGION}"
if gsutil ls -b "gs://${BUCKET_NAME}" 2>/dev/null; then
  echo "Bucket gs://${BUCKET_NAME} already exists."
else
  gsutil mb -p "$PROJECT_ID" -l "$TF_STATE_REGION" "gs://${BUCKET_NAME}"
  echo "Created gs://${BUCKET_NAME}"
fi
gsutil versioning set on "gs://${BUCKET_NAME}"

echo ""
echo "=== 2) Terraform init ==="
cd "$TERRAFORM_DIR"
terraform init \
  -backend-config="bucket=${BUCKET_NAME}" \
  -backend-config="prefix=ops-voice-copilot"

echo ""
echo "=== 3) Terraform apply (APIs + Artifact Registry + IAM) ==="
terraform apply $VAR_ARGS -auto-approve \
  -target=module.foundation

echo ""
echo "=== 4) Cloud Build — build and push image ==="
cd "$ROOT"
./scripts/build-image.sh "$PROJECT_ID" "$REGION"

echo ""
echo "=== 5) Terraform apply (full) ==="
cd "$TERRAFORM_DIR"
terraform apply $VAR_ARGS -auto-approve

echo ""
echo "Done. Gateway URL:"
terraform output -raw gateway_url 2>/dev/null || true
