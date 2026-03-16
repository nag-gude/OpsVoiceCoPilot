variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Artifact Registry and APIs"
  type        = string
}

variable "artifact_registry_repo" {
  description = "Artifact Registry repository ID for container images"
  type        = string
}

variable "image_name" {
  description = "Docker image name (tag) in the repository"
  type        = string
}