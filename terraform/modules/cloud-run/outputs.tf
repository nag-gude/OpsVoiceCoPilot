output "uri" {
  description = "Service URL"
  value       = google_cloud_run_v2_service.service.uri
}

output "name" {
  description = "Service name"
  value       = google_cloud_run_v2_service.service.name
}

output "location" {
  description = "Service location"
  value       = google_cloud_run_v2_service.service.location
}
