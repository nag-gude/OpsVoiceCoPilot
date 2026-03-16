import asyncio
import os

import websockets
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.core.logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Ops Voice CoPilot Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_SERVICE_URL = os.environ.get(
    "AGENT_SERVICE_URL",
    "http://localhost:8081"
).rstrip("/")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "gateway",
        "agent_url": AGENT_SERVICE_URL
    }


def agent_ws_url():
    if AGENT_SERVICE_URL.startswith("https"):
        return AGENT_SERVICE_URL.replace("https://", "wss://") + "/ws/live/voice"
    return AGENT_SERVICE_URL.replace("http://", "ws://") + "/ws/live/voice"


@app.websocket("/ws/live/voice")
async def websocket_proxy(ws: WebSocket):

    await ws.accept()

    try:
        async with websockets.connect(agent_ws_url()) as agent_ws:

            async def client_to_agent():
                while True:
                    msg = await ws.receive()

                    if msg.get("bytes"):
                        await agent_ws.send(msg["bytes"])
                    elif msg.get("text"):
                        await agent_ws.send(msg["text"])

            async def agent_to_client():
                while True:
                    data = await agent_ws.recv()

                    if isinstance(data, bytes):
                        await ws.send_bytes(data)
                    else:
                        await ws.send_text(data)

            await asyncio.gather(
                client_to_agent(),
                agent_to_client()
            )

    except Exception as e:
        logger.exception("proxy error %s", e)


app.mount("/", StaticFiles(directory="ui", html=True), name="ui")