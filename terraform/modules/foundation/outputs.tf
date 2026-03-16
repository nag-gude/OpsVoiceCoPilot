output "image_uri" {
  description = "Full image URI for the app (legacy single-image deploy; points to 'app')"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/${var.image_name}:latest"
}

output "tools_image_uri" {
  description = "Full image URI for the Tools service"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/tools:latest"
}

output "agent_image_uri" {
  description = "Full image URI for the Agent service"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/agent:latest"
}

output "gateway_image_uri" {
  description = "Full image URI for the Gateway service"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/gateway:latest"
}

output "project_number" {
  description = "GCP project number (for IAM)"
  value       = data.google_project.project.number
}

output "region" {
  description = "GCP region"
  value       = var.region
}

output "tools_sa_email" {
  description = "Custom service account email for the Tools Cloud Run service"
  value       = google_service_account.tools.email
}

output "agent_sa_email" {
  description = "Custom service account email for the Agent Cloud Run service"
  value       = google_service_account.agent.email
}

output "gateway_sa_email" {
  description = "Custom service account email for the Gateway Cloud Run service"
  value       = google_service_account.gateway.email
}