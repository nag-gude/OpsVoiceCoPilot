# Terraform modules

Reusable modules for the Ops Voice Co-Pilot GCP deployment.

| Module | Purpose |
|--------|--------|
| **foundation** | Enables required APIs (Cloud Run, Artifact Registry, Vertex AI, Cloud Build, IAM), creates the Artifact Registry repository, creates **custom service accounts** with least-privilege IAM (Tools: AR reader + Logging viewer; Agent: AR reader + Logging viewer + Vertex AI user; Gateway: AR reader only), and grants Cloud Build SA push access. Outputs `image_uri`, `project_number`, `region`, `tools_sa_email`, `agent_sa_email`, `gateway_sa_email`. |
| **cloud-run-service** | Single Cloud Run v2 service with configurable name, image, env vars, scaling, and optional public invoker. Use for any service that shares the same image and port. Outputs `uri`, `name`, `location`. |

The root `main.tf` composes these modules: one `foundation` and three `cloud-run-service` instances (tools → agent → gateway) with the appropriate env vars and dependencies.
