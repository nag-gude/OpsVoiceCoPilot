output "uri" {
  description = "Service URL"
  value       = google_cloud_run_service.service.status[0].url
}

output "name" {
  description = "Service name"
  value       = google_cloud_run_service.service.name
}

output "location" {
  description = "Service location"
  value       = google_cloud_run_service.service.location
}
