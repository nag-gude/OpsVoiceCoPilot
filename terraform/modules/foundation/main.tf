# Required APIs for Ops Voice Co-Pilot
resource "google_project_service" "run" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  project            = var.project_id
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "vertexai" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  project            = var.project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

# Artifact Registry repository for app image
resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  description   = "Container images for the application"
  format        = "DOCKER"
  depends_on    = [google_project_service.artifactregistry]
}

data "google_project" "project" {
  project_id = var.project_id
}

# -----------------------------------------------------------------------------
# Custom service accounts (least privilege per service)
# -----------------------------------------------------------------------------

# Tools: pull image + read logs only
resource "google_service_account" "tools" {
  project      = var.project_id
  account_id   = "ops-voice-copilot-tools"
  display_name = "Ops Voice Co-Pilot Tools (Cloud Run)"
  depends_on   = [google_project_service.iam]
}

# Agent: pull image + read logs + Vertex AI (Gemini)
resource "google_service_account" "agent" {
  project      = var.project_id
  account_id   = "ops-voice-copilot-agent"
  display_name = "Ops Voice Co-Pilot Agent (Cloud Run)"
  depends_on   = [google_project_service.iam]
}

# Gateway: pull image only (user-facing proxy)
resource "google_service_account" "gateway" {
  project      = var.project_id
  account_id   = "ops-voice-copilot-gateway"
  display_name = "Ops Voice Co-Pilot Gateway (Cloud Run)"
  depends_on   = [google_project_service.iam]
}

# All three need to pull the app image from Artifact Registry
resource "google_artifact_registry_repository_iam_member" "tools_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.tools.email}"
}

resource "google_artifact_registry_repository_iam_member" "agent_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_artifact_registry_repository_iam_member" "gateway_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.gateway.email}"
}

# Tools + Agent: read logs (Tools service queries Cloud Logging)
resource "google_project_iam_member" "tools_logs" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.tools.email}"
}

resource "google_project_iam_member" "agent_logs" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Agent only: Vertex AI / Gemini
resource "google_project_iam_member" "agent_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Cloud Build default SA can push images (unchanged)
resource "google_artifact_registry_repository_iam_member" "cloudbuild_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}