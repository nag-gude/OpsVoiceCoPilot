FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

RUN chmod +x scripts/run-service.sh

ENTRYPOINT ["/app/scripts/run-service.sh"]