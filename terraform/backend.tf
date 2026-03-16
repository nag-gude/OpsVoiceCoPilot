# GCS backend for Terraform state.
# Configure at init with -backend-config (bucket must exist; use scripts/terraform-bootstrap.sh).
#
# Example:
#   terraform init -backend-config="bucket=YOUR_PROJECT_ID-tfstate" -backend-config="prefix=ops-voice-copilot"

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  backend "gcs" {}
}