resource "google_cloud_run_v2_service" "service" {
  name     = var.name
  location = var.location
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {

    service_account = var.service_account_email
    containers {
      image = var.image_uri

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "LAST_DEPLOY_TIMESTAMP"
        value = timestamp()
      }

      ports {
        container_port = var.container_port
      }
    }
    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = google_cloud_run_v2_service.service.project
  location = google_cloud_run_v2_service.service.location
  name     = google_cloud_run_v2_service.service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
