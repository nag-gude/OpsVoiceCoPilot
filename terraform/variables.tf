variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, Artifact Registry, and Vertex AI."
  type        = string
  default     = "europe-west2"
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository name for app images"
  type        = string
  default     = "ops-voice-copilot"
}

variable "image_name" {
  description = "Docker image name (tag) in Artifact Registry"
  type        = string
  default     = "app"
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated invocations on Cloud Run services"
  type        = bool
  default     = true
}

