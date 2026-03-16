# Ops Voice Co-Pilot — Cloud Run
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt --use-deprecated=legacy-resolver

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements.txt
# Ensure UI is in the image so Gateway can serve index.html, js/app.js, css/styles.css
COPY ui ./ui
COPY . .
ENV API_HOST=0.0.0.0
ENV API_PORT=8080
EXPOSE 8080
RUN chmod +x scripts/run-service.sh
ENV SERVICE_NAME=gateway
ENTRYPOINT ["/app/scripts/run-service.sh"]
