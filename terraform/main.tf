provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# Foundation: APIs, Artifact Registry, IAM for image push/pull
# -----------------------------------------------------------------------------
module "foundation" {
  source = "./modules/foundation"

  project_id             = var.project_id
  region                 = var.region
  artifact_registry_repo = var.artifact_registry_repo
  image_name             = var.image_name
}

# -----------------------------------------------------------------------------
# Cloud Run: Tools (no service dependencies)
# -----------------------------------------------------------------------------
module "tools" {
  source = "./modules/cloud-run"

  project_id             = var.project_id
  name                   = "ops-voice-copilot-tools"
  location               = var.region
  image_uri              = module.foundation.image_uri
  service_account_email  = module.foundation.tools_sa_email
  allow_unauthenticated  = var.allow_unauthenticated
  min_instance_count     = 1            # WebSocket stability
  max_instance_count     = 10

  env = {
    SERVICE_NAME          = "tools"
    GOOGLE_CLOUD_PROJECT  = var.project_id
    GOOGLE_CLOUD_REGION   = var.region
  }

  depends_on = [module.foundation]
}

# -----------------------------------------------------------------------------
# Cloud Run: Agent (depends on Tools URL)
# -----------------------------------------------------------------------------
module "agent" {
  source = "./modules/cloud-run"

  project_id             = var.project_id
  name                   = "ops-voice-copilot-agent"
  location               = var.region
  image_uri              = module.foundation.image_uri
  service_account_email  = module.foundation.agent_sa_email
  allow_unauthenticated  = var.allow_unauthenticated
  min_instance_count     = 1
  max_instance_count     = 10

  env = {
    SERVICE_NAME           = "agent"
    GOOGLE_CLOUD_PROJECT   = var.project_id
    GOOGLE_CLOUD_REGION    = var.region
    GOOGLE_CLOUD_LOCATION  = var.region
    VERTEX_AI_LOCATION     = var.region
    TOOLS_SERVICE_URL      = module.tools.uri
  }

  depends_on = [module.foundation, module.tools]
}

# -----------------------------------------------------------------------------
# Cloud Run: Gateway (user-facing; depends on Agent URL)
# -----------------------------------------------------------------------------
module "gateway" {
  source = "./modules/cloud-run"

  project_id             = var.project_id
  name                   = "ops-voice-copilot"
  location               = var.region
  image_uri              = module.foundation.image_uri
  service_account_email  = module.foundation.agent_sa_email
  allow_unauthenticated  = var.allow_unauthenticated
  min_instance_count     = 1
  max_instance_count     = 10

  env = {
    SERVICE_NAME          = "gateway"
    GOOGLE_CLOUD_REGION   = var.region
    AGENT_SERVICE_URL     = module.agent.uri
  }

  depends_on = [module.foundation, module.agent]
}