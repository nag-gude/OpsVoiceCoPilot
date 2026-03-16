import asyncio
import os

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


# ---------------------------------------------------------
# Convert HTTP URL -> WS URL
# ---------------------------------------------------------

def agent_ws_url():

    if AGENT_SERVICE_URL.startswith("https://"):
        return AGENT_SERVICE_URL.replace("https://", "wss://") + "/ws/live/voice"

    return AGENT_SERVICE_URL.replace("http://", "ws://") + "/ws/live/voice"


# ---------------------------------------------------------
# WebSocket proxy
# ---------------------------------------------------------

@app.websocket("/ws/live/voice")
async def websocket_proxy(client_ws: WebSocket):

    await client_ws.accept()

    upstream_url = agent_ws_url()

    logger.info("Proxy connecting to agent %s", upstream_url)

    try:

        async with websockets.connect(
            upstream_url,
            ping_interval=20,
            ping_timeout=20,
            max_size=10 * 1024 * 1024,
        ) as agent_ws:

            async def client_to_agent():

                try:

                    while True:

                        msg = await client_ws.receive()

                        if msg["type"] == "websocket.disconnect":
                            break

                        if msg.get("bytes") is not None:
                            await agent_ws.send(msg["bytes"])

                        elif msg.get("text") is not None:
                            await agent_ws.send(msg["text"])

                except WebSocketDisconnect:
                    logger.info("client disconnected")

                except Exception as e:
                    logger.exception("client_to_agent error %s", e)

                finally:
                    await agent_ws.close()


            async def agent_to_client():

                try:

                    async for message in agent_ws:

                        if isinstance(message, bytes):
                            await client_ws.send_bytes(message)

                        else:
                            await client_ws.send_text(message)

                except websockets.ConnectionClosed:
                    logger.info("agent websocket closed")

                except Exception as e:
                    logger.exception("agent_to_client error %s", e)

                finally:
                    try:
                        await client_ws.close()
                    except Exception:
                        pass


            await asyncio.gather(
                client_to_agent(),
                agent_to_client(),
            )

    except Exception as e:

        logger.exception("proxy error %s", e)

        err = str(e)

        try:
            await client_ws.send_json({
                "type": "error",
                "error": err,
                "message": err
            })
        except Exception:
            pass

        try:
            await client_ws.close()
        except Exception:
            pass


# ---------------------------------------------------------
# UI
# ---------------------------------------------------------

app.mount("/", StaticFiles(directory="ui", html=True), name="ui")