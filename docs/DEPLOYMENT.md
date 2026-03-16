# Deploying Ops Voice Co-Pilot to GCP

Two options: **Terraform (GCS backend)** for repeatable, stateful deployments, or the **shell script** for a quick one-off deploy.


## Option 1: Terraform with GCS backend (recommended)

Terraform stores state in a **Google Cloud Storage (GCS)** bucket so that state is shared and safe across runs and team members.

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.5
- [gcloud](https://cloud.google.com/sdk/docs/install) CLI, authenticated
- Docker (for local build) or Cloud Build will build in the cloud

### 1. Configure Terraform (one-time)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set project_id (and optionally region)
```

**Region:** Default is **europe-west1**. The voice agent uses **Gemini Live** (`gemini-live-2.5-flash-native-audio`), which is [supported in selected regions](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-live-api) including `europe-west1`, `europe-west4`, `us-central1`. Use one of these for the Agent service to avoid WebSocket 400 errors.

### 2. Run bootstrap (one-time or to redeploy)

From the **project root**:

```bash
chmod +x scripts/terraform-bootstrap.sh
./scripts/terraform-bootstrap.sh YOUR_PROJECT_ID [BUCKET_NAME] [REGION]
```

Example: `./scripts/terraform-bootstrap.sh my-project my-project-tfstate europe-west2`

Bootstrap runs **one by one**:

1. **State bucket** — creates `gs://BUCKET_NAME` (or `gs://PROJECT_ID-tfstate`) and enables versioning
2. **Terraform init** — GCS backend with `prefix=ops-voice-copilot`
3. **Terraform apply (targeted)** — applies the `foundation` module (APIs, Artifact Registry, IAM) so the image can be built and pushed
4. **Build image** — runs `scripts/build-image.sh` to build the app image (via `gcloud builds submit` and the repo Dockerfile) and push to Artifact Registry
5. **Terraform apply (full)** — deploys Cloud Run (Tools → Agent → Gateway). All three use the **same container image**; `SERVICE_NAME` selects which process runs. Each service uses a **custom service account** with least-privilege IAM (Tools/Agent: Artifact Registry reader + Logging viewer; Agent only: Vertex AI user; Gateway: Artifact Registry reader only).

Outputs:

- **gateway_url** — open this URL in the browser (UI + WebSocket from Cloud Run)
- **agent_url**, **tools_url** — internal service URLs

### 3. Re-run after code changes

To rebuild the image and update Cloud Run, run the build then apply:

```bash
./scripts/build-image.sh YOUR_PROJECT_ID europe-west1
cd terraform && terraform apply
```

### Building the image

Bootstrap step 4 runs **`scripts/build-image.sh`**, which uses `gcloud builds submit` and the repo **Dockerfile** to build and push the image to Artifact Registry. For a manual rebuild:

```bash
./scripts/build-image.sh YOUR_PROJECT_ID europe-west1
```

### Manual Terraform (without full bootstrap)

If you already have the state bucket and image built:

```bash
cd terraform
terraform init -backend-config="bucket=YOUR_BUCKET" -backend-config="prefix=ops-voice-copilot"
terraform plan
terraform apply
```

Ensure the image exists in Artifact Registry before applying (e.g. run `./scripts/build-image.sh` first).

### Backend configuration (reference)

| Backend config | Description |
|----------------|-------------|
| `bucket` | GCS bucket name (must exist; create with `scripts/terraform-bootstrap.sh`) |
| `prefix` | Optional path prefix for state file (e.g. `ops-voice-copilot` or `env/prod`) |

Example for a separate state file per environment:

```bash
terraform init -backend-config="bucket=my-company-tfstate" -backend-config="prefix=ops-voice-copilot/prod"
```

### Public access (test without sign-in)

Terraform sets `allow_unauthenticated = true` by default so **anyone can open the UI and test** without logging in. If you previously deployed with it set to `false`, or the UI asks for login, run once from the project root:

```bash
./scripts/allow-public-access.sh YOUR_PROJECT_ID europe-west1
```

This grants `allUsers` the **Cloud Run Invoker** role on the Gateway, Agent, and Tools services.

### Demo: push failure logs to GCP

To seed Cloud Logging with demo failure entries for testing (so the voice agent can cite them when you ask "Why did this break?"):

```bash
python scripts/push-demo-logs.py YOUR_PROJECT_ID
```

Requires `google-cloud-logging` (in `requirements.txt`) and credentials (`gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`). If you see "google-cloud-logging not installed", run `pip install -r requirements.txt`, then run the script again. The script writes five ERROR/WARNING entries to the `ops-voice-copilot-demo` log; they appear in `get_recent_logs` and in the agent’s answers.


## Option 2: Shell script (quick deploy)

From the project root:

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1
./scripts/deploy-cloudrun.sh $PROJECT_ID $REGION
```

Then grant Vertex AI User and Logs Viewer to the Agent and Tools service accounts (see [README](../README.md)).


## Post-deploy: IAM (script deploy only)

If you used the **shell script**, add roles manually. If you used **Terraform**, IAM is managed by Terraform via custom service accounts (`ops-voice-copilot-tools`, `ops-voice-copilot-agent`, `ops-voice-copilot-gateway`) with least-privilege roles per service.

For the script path:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
for SVC in ops-voice-copilot-agent ops-voice-copilot-tools; do
  gcloud run services add-iam-policy-binding $SVC --region $REGION \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
  gcloud run services add-iam-policy-binding $SVC --region $REGION \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/logging.viewer"
done
```


## Architecture (deployed)

See [ARCHITECTURE.md](ARCHITECTURE.md). In GCP:

- **Gateway** (ops-voice-copilot) — public; serves UI and proxies WebSocket to Agent
- **Agent** (ops-voice-copilot-agent) — Gemini Live API; calls Tools for logs
- **Tools** (ops-voice-copilot-tools) — Cloud Logging API

All three use the same container image; `SERVICE_NAME` and env vars select the process.
