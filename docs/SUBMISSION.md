# Ops Voice Co-Pilot — Submission (Gemini Live Agent Challenge)

Use the sections below when filling out the [Devpost submission form](https://geminiliveagentchallenge.devpost.com/). Replace `[YOUR_...]` placeholders with your actual values.

**Documentation index:** [README](../README.md) (overview, quick start, deploy) · [ARCHITECTURE.md](ARCHITECTURE.md) (diagrams, data flow, demo) · [DEPLOYMENT.md](DEPLOYMENT.md) (Terraform, script, demo logs).

---

## Project name

**Ops Voice Co-Pilot**

*(You can change this at any time.)*

---

## Elevator pitch

**See it. Say it. Fix it.**

Real-time voice + vision agent for operational triage. Ask out loud “why did this break?” while sharing a dashboard or log screen—get grounded answers you can trust, without typing.

*(Short tagline; you can change later.)*

---

## About the project

Be sure to write what inspired you, what you learned, how you built your project, and the challenges you faced.

### Inspiration

When something breaks in production, operators and SREs stare at dashboards and logs and often have to type queries or click around to piece together the story. We wanted a **hands-free, voice-first** way to ask “why did this break?” or “what’s this spike?” and get answers that are **tied to what’s actually on screen and in the logs**—not generic advice. The [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) and the Live Agents track (real-time, interruptible voice + vision) were a perfect fit for building this ops co-pilot.

### What it does

- **Voice:** Real-time, interruptible conversation via the **Gemini Live API** (Vertex AI). You speak; the co-pilot responds by voice. You can interrupt at any time (barge-in).
- **Vision:** You upload or paste a screenshot of a dashboard (Grafana, GCP Console, Datadog) or log view. The agent grounds every answer in what it sees on that screen.
- **Grounding:** Answers reference the image and, when relevant, **recent log entries** from **Google Cloud Logging**. The agent can call a `get_recent_logs` tool and say things like “From the logs I just pulled…” so you know the answer is based on live data.
- **Deployment:** Backend runs on **Google Cloud Run** as three microservices: Gateway (UI + WebSocket proxy), Agent (Gemini Live), and Tools (Cloud Logging). Uses **Vertex AI** (Gemini Live) and **Cloud Logging**.

### How we built it

- **Frontend:** A simple web UI (HTML, CSS, JavaScript) for uploading/pasting screenshots, connecting voice (WebSocket), and starting the mic. Audio is captured at 16 kHz PCM (batched), sent over the WebSocket; playback is 24 kHz PCM from the server. The UI shows a **sample demo transcript** on first load and a “Load sample demo” button for presentations.
- **Backend:** FastAPI on Python, **microservices only**. **Gateway** (`services/gateway/main.py`) serves the UI and proxies the WebSocket to the **Agent**; **Agent** (`services/agent/main.py`, `services/agent/live_session.py`) runs the Gemini Live session and calls the **Tools** service over HTTP for `get_recent_logs`. All three run from the **same container image**; `SERVICE_NAME` (gateway|agent|tools) selects the process (Dockerfile entrypoint).
- **Gemini Live:** We use the **Google GenAI SDK** (`google-genai`) with Vertex AI in **europe-west1**, model **gemini-live-2.5-flash-native-audio**. The Live session has a system instruction for an ops co-pilot (grounding, citations). When the model calls `get_recent_logs`, the Agent POSTs to Tools `/logs/recent` and sends the result via `send_tool_response`.
- **GCP:** Cloud Run hosts all three services (single image); Vertex AI for the Live API; Cloud Logging in the Tools service. Deployment: **Terraform** (recommended) with GCS backend via `scripts/terraform-bootstrap.sh`, or **script** via `scripts/deploy-cloudrun.sh`. Demo: `scripts/push-demo-logs.sh` seeds Cloud Logging with sample failure entries so the agent can cite them when you ask “Why did this break?”

### Challenges we ran into

- **WebSocket proxy:** The Gateway proxies the Live voice WebSocket to the Agent without dropping binary (PCM) or text frames. We used the `websockets` library and two async tasks (client→agent, agent→client) so both directions stream correctly.
- **Tool calling in Live API:** Wiring the Live API’s tool-call responses to the Tools HTTP service required matching the SDK’s response shape and sending `FunctionResponse` with the correct `id` and `name`.
- **Grounding without hallucination:** We tuned the system instruction so the agent explicitly cites what it sees (“the spike in the top-left graph”) and says “From the logs I just pulled…” when using the tool, and admits uncertainty when evidence is missing.

### Accomplishments that we're proud of

- Delivering a **real-time, interruptible** voice agent that truly uses **vision + tool data** for grounding, not just chat.
- A **microservices architecture** (Gateway, Agent, Tools) with clear separation of concerns; one image, three Cloud Run services, wired by `deploy-cloudrun.sh`.
- **Reproducible setup:** README with local (Docker Compose or three terminals) and GCP deploy steps so judges can run and test the project.

### What we learned

- The Gemini Live API’s bidirectional streaming model (audio in/out, optional image input, tool calls) fits ops triage well when combined with a strict grounding persona.
- Proxying WebSockets that carry both binary and JSON between browser and backend services needs careful handling so no messages are lost and connections stay in sync.
- Cloud Logging’s list-entries API works well as a “get recent logs” tool for the agent; keeping the Tool as a separate service keeps the Agent focused on the Live session and makes scaling and IAM easier.

### What's next for Ops Voice Co-Pilot

- **Proactive alerts:** When the user shares a screen, the agent could say one short sentence like “I notice three error spikes in the last 5 minutes—want me to walk through the likely cause?”
- **More tools:** e.g. fetch metrics from Cloud Monitoring or run a BigQuery snippet for data checks.
- **Session memory:** Optional persistence of conversation and referenced screens across reloads (UI toggle and localStorage).
- **Auth:** Add IAP or identity so only authorized operators can use the co-pilot in production.

---

## Built with

What languages, frameworks, platforms, cloud services, databases, APIs, or other technologies did you use?

- **Languages:** Python, JavaScript (frontend)
- **Frameworks:** FastAPI, Uvicorn
- **APIs / SDKs:** Google-GenAI-SDK (`google-genai`) for Gemini Live API, Google Cloud Logging client
- **Platforms / Cloud:** Google Cloud Run, Vertex AI (Gemini Live), Google Cloud Logging
- **Other:** WebSocket (voice + proxy), Web Audio API (mic capture and playback), Docker, Docker Compose, Terraform (GCS backend, Cloud Run, IAM), gcloud CLI

---

## "Try it out" links

Add links where people can try your project or see your code.

- **Live demo (if deployed):** `https://[YOUR_GATEWAY_URL]` — e.g. Cloud Run Gateway URL from `terraform output gateway_url` or the URL printed by `deploy-cloudrun.sh`.
- **Code repository:** `https://github.com/nag-gude/OpsVoiceCoPilot` (or your fork).
- **Documentation:** [README](../README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOYMENT.md](DEPLOYMENT.md) in the repo.

---

## What date did you start this project?

**MM-DD-YY** — e.g. `02-15-26` if you started February 15, 2026.

*(Projects must be newly created during the Submission Period.)*

---

## URL to PUBLIC Code Repo

`https://github.com/nag-gude/OpsVoiceCoPilot`

*(So judges can see how the project was built.)*

---

## Did you add Reproducible Testing instructions to your README?

**Yes.** The README and [DEPLOYMENT.md](DEPLOYMENT.md) include:

- **Quick start (local):** Clone, venv, `pip install -r requirements.txt`, set `GOOGLE_CLOUD_PROJECT` in `.env`, run via `docker compose up --build` or three terminals. Open http://localhost:8080.
- **Deploy (Terraform):** `./scripts/terraform-bootstrap.sh PROJECT_ID [BUCKET] [REGION]`; then `terraform output gateway_url`. Use region `europe-west1` for Gemini Live.
- **Deploy (script):** `./scripts/deploy-cloudrun.sh PROJECT_ID REGION`; add IAM for Agent and Tools (see README).
- **Demo:** `./scripts/push-demo-logs.sh PROJECT_ID` seeds logs; UI has sample transcript and "Load sample demo" button.
- **How to use the UI:** upload/paste screenshot, Connect (Voice), Start mic, optional “Send image to co-pilot,” then ask “Why did this break?” or “What’s this spike?”

Judges can reproduce the project locally or on their own GCP project using these instructions.

---

## URL to Proof of Google Cloud deployment

Proof = (1) a short screen recording showing the app running on GCP (e.g. Cloud Run console or the live UI), or (2) links to files in your repo that show use of Google Cloud.

- **Option 1 (video):** `https://[YOUR_VIDEO_LINK]` — e.g. Loom or YouTube showing the Gateway URL, Connect (Voice), and a voice Q&A.
- **Option 2 (repo links):**
  - **Vertex AI / Gemini Live API:** [services/agent/live_session.py](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/services/agent/live_session.py) — Live session, `genai.Client(vertexai=True)`, `send_realtime_input`, tool response.
  - **Cloud Logging:** [services/tools/logging_tool.py](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/services/tools/logging_tool.py) — `get_recent_logs`, Cloud Logging client.
  - **Cloud Run / deployment:** [scripts/deploy-cloudrun.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/deploy-cloudrun.sh), [terraform/main.tf](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/terraform/main.tf), [Dockerfile](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/Dockerfile).

---

## (REQUIRED) Where did you upload an architecture diagram?

**Image carousel / File upload / Code repo** — select as applicable.

- **Code repo:** The architecture is documented in the repo at **docs/ARCHITECTURE.md**, including ASCII diagrams for monolith and microservices and Mermaid diagrams. You can export a diagram from that file (or draw one from it) and upload it to the submission **Image Gallery / File Upload** so judges see a clear visual of how Gemini connects to the backend, Cloud Logging, and frontend.

---

## URL to published piece of content (blog, podcast, video)

*(Optional.)* If you publish a blog, podcast, or video about how the project was built with Google AI and Google Cloud:

- **URL:** `https://[YOUR_BLOG_OR_VIDEO_URL]`
- **Required wording:** State that the piece was created for the purposes of entering this hackathon. When sharing on social media, use **#GeminiLiveAgentChallenge**.

---

## Automating Cloud Deployment

Link to the part of your code that shows automated deployment (scripts or infrastructure-as-code).

- **Terraform (recommended):** [terraform/main.tf](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/terraform/main.tf) — Foundation (APIs, Artifact Registry, IAM) and three Cloud Run modules (Tools, Agent, Gateway). [scripts/terraform-bootstrap.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/terraform-bootstrap.sh) creates the GCS state bucket, runs Terraform, and [scripts/build-image.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/build-image.sh) builds and pushes the single image.
- **Script deploy:** [scripts/deploy-cloudrun.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/deploy-cloudrun.sh) — Deploys Tools, Agent, and Gateway to Cloud Run and wires URLs.
- **Image and runtime:** [Dockerfile](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/Dockerfile) (single image; `SERVICE_NAME` selects process), [scripts/run-service.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/run-service.sh) (local run by service name), [docker-compose.yml](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/docker-compose.yml).

---

## URL to PUBLIC Google Developer Group profile

*(Optional, for bonus points.)* Sign up at [GDG](https://gdg.community.dev/) and add your public profile URL:

`https://gdg.community.dev/u/m4qhnu`

---

## Submission checklist

Confirm before submitting:

1. **Does your project meet all three criteria?**
   - **Leverage a Gemini model** — Yes (Vertex AI Gemini Live).
   - **Agents must be built using Google GenAI SDK OR ADK** — Yes (Google GenAI SDK, `google-genai`).
   - **Use at least one Google Cloud service** — Yes (Cloud Run, Vertex AI, Cloud Logging).

2. **Does your text description summarize features, technologies, data sources, and learnings?** — Yes (see “About the project” above).

3. **Do you have a PUBLIC repo URL and spin-up instructions in the README?** — Yes (add your repo URL and ensure README is complete).

4. **Did you record a short video with proof of GCP deployment?** — (Add your video or repo links as proof.)

5. **Did you upload an architecture diagram image?** — (Upload an image from or based on docs/ARCHITECTURE.md.)

6. **Did you upload a 4-minute demonstration video?** — (Required; upload your demo video.)

---

## Bonus (optional)

- **Content:** Publish a blog/podcast/video with hackathon disclaimer and #GeminiLiveAgentChallenge.
- **Automated deployment:** Link to [terraform/main.tf](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/terraform/main.tf) and [scripts/terraform-bootstrap.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/terraform-bootstrap.sh), or [scripts/deploy-cloudrun.sh](https://github.com/nag-gude/OpsVoiceCoPilot/blob/main/scripts/deploy-cloudrun.sh) (and Dockerfile, docker-compose) in the form.
- **GDG:** Add your public GDG profile URL.

---

*Remember: You can submit and then continue to improve the project until the deadline. Upload videos well before the deadline to allow for processing.*
