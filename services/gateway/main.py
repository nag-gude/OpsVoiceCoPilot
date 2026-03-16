"""Gateway microservice: single entry point for Ops Voice Co-Pilot.

Serves static UI at / and proxies WebSocket /ws/live/voice to the Agent service.
Environment: AGENT_SERVICE_URL (default http://localhost:8081).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import os

import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Ops Voice Co-Pilot Gateway",
    description="See it. Say it. Fix it. Entry point for voice + vision agent.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_SERVICE_URL = os.environ.get("AGENT_SERVICE_URL", "http://localhost:8081").rstrip("/")


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path or "/"

    # Long-lived cache for static assets served from Cloud Run (JS/CSS/images)
    if path.startswith("/js/") or path.startswith("/css/") or path.startswith("/assets/"):
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # HTML entrypoints should revalidate so users see new deployments quickly
    elif path == "/" or path.endswith(".html"):
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"

    return response


def _agent_ws_url():
    base = AGENT_SERVICE_URL
    if base.startswith("https://"):
        return base.replace("https://", "wss://", 1) + "/ws/live/voice"
    return base.replace("http://", "ws://", 1) + "/ws/live/voice"


@app.get("/health")
def health():
    """Gateway health; does not check downstream services."""
    return {
        "status": "ok",
        "service": "ops-voice-copilot-gateway",
        "mode": "microservices",
        "agent_url": AGENT_SERVICE_URL,
    }


@app.websocket("/ws/live/voice")
async def websocket_live_voice(websocket: WebSocket):
    """Proxy client WebSocket to Agent service /ws/live/voice (bidirectional binary + text)."""
    await websocket.accept()
    agent_url = _agent_ws_url()
    try:
        async with websockets.connect(agent_url) as agent_ws:
            async def client_to_agent():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") != "websocket.receive":
                            continue
                        if "bytes" in msg:
                            await agent_ws.send(msg["bytes"])
                        elif "text" in msg:
                            await agent_ws.send(msg["text"])
                except Exception as e:
                    if "1006" not in str(e):
                        logger.exception("live voice proxy client->agent: %s", e)

            async def agent_to_client():
                try:
                    while True:
                        data = await agent_ws.recv()
                        if isinstance(data, bytes):
                            await websocket.send_bytes(data)
                        else:
                            await websocket.send_text(data)
                except websockets.ConnectionClosed:
                    pass
                except Exception as e:
                    logger.exception("live voice proxy agent->client: %s", e)

            t1 = asyncio.create_task(client_to_agent())
            t2 = asyncio.create_task(agent_to_client())
            done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
    except Exception as e:
        logger.exception("gateway connect to agent: %s", e)
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


ui_path = Path(__file__).resolve().parents[2] / "ui"
if ui_path.is_dir():
    app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="ui")
    try:
        await websocket.close()
    except Exception:
        pass
