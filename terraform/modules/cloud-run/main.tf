resource "google_cloud_run_service" "service" {
  name     = var.name
  location = var.location
  project  = var.project_id

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = tostring(var.min_instance_count)
        "autoscaling.knative.dev/maxScale" = tostring(var.max_instance_count)
      }
    }
    spec {
      containers {
        image = var.image_uri
        ports {
          container_port = 8080
        }

        dynamic "env" {
          for_each = var.env
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name = "LAST_UPDATED_TIMESTAMP"
          value = timestamp()
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }

        startup_probe {
          tcp_socket {
            port = 8080
          }
          period_seconds    = 10
          timeout_seconds   = 5
          failure_threshold = 12
        }
      }

      container_concurrency = var.container_concurrency
      service_account_name  = var.service_account_email
      timeout_seconds       = 300
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Optionally allow unauthenticated access
resource "google_cloud_run_service_iam_member" "invoker" {
  count   = var.allow_unauthenticated ? 1 : 0
  project = var.project_id
  location = var.location
  service = google_cloud_run_service.service.name
  role    = "roles/run.invoker"
  member  = "allUsers"
}