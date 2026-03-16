import asyncio
import base64
import json
import os
from typing import Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from services.core.logging_config import get_logger
from services.agent.live_session import run_live_session, is_live_available

logger = get_logger(__name__)

app = FastAPI(
    title="Ops Voice Co-Pilot Agent",
    version="1.0.0"
)

TOOLS_SERVICE_URL = os.environ.get("TOOLS_SERVICE_URL", "").rstrip("/")

# reuse HTTP connections
http_client = httpx.AsyncClient(timeout=15.0)

MAX_IMAGE_SIZE = 5 * 1024 * 1024

def create_logs_fetcher():
    if not TOOLS_SERVICE_URL:
        return None

    async def fetcher(filter_expr: str, page_size: int):
        try:
            r = await http_client.post(
                f"{TOOLS_SERVICE_URL}/logs/recent",
                json={
                    "filter_expr": filter_expr,
                    "page_size": page_size
                }
            )
            r.raise_for_status()
            data = r.json()
            return data.get("result", "")
        except Exception as e:
            logger.exception("tools call failed: %s", e)
            return "Tools service unavailable"

    return fetcher


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ops-voice-copilot-agent",
        "live_available": is_live_available(),
        "tools_service": TOOLS_SERVICE_URL or "in-process"
    }


@app.websocket("/ws/live/voice")
async def websocket_live_voice(websocket: WebSocket):

    await websocket.accept()

    if not is_live_available():
        await websocket.send_json({
            "type": "error",
            "message": "Gemini Live not configured"
        })
        await websocket.close()
        return

    audio_input_queue = asyncio.Queue(maxsize=50)
    text_input_queue = asyncio.Queue(maxsize=20)
    video_input_queue = asyncio.Queue(maxsize=5)

    logs_fetcher = create_logs_fetcher()

    async def audio_output_callback(data: bytes):
        try:
            await websocket.send_bytes(data)
        except RuntimeError:
            logger.info("client disconnected")

    async def heartbeat():
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_json({"type": "ping"})
            except RuntimeError:
                break

    heartbeat_task = asyncio.create_task(heartbeat())

    async def receive_loop():
        try:
            while True:
                msg = await websocket.receive()

                if msg.get("bytes"):
                    try:
                        audio_input_queue.put_nowait(msg["bytes"])
                    except asyncio.QueueFull:
                        logger.warning("dropping audio frame")

                elif msg.get("text"):
                    text = msg["text"]

                    try:
                        payload = json.loads(text)

                        if payload.get("type") == "image":
                            img = base64.b64decode(payload.get("data", ""))

                            if len(img) > MAX_IMAGE_SIZE:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "image too large"
                                })
                                continue

                            await video_input_queue.put(img)
                            continue

                    except Exception:
                        pass

                    try:
                        text_input_queue.put_nowait(text)
                    except asyncio.QueueFull:
                        logger.warning("dropping text")

        except WebSocketDisconnect:
            logger.info("client disconnected")

    recv_task = asyncio.create_task(receive_loop())

    try:
        async for event in run_live_session(
            audio_input_queue=audio_input_queue,
            text_input_queue=text_input_queue,
            video_input_queue=video_input_queue,
            audio_output_callback=audio_output_callback,
            get_recent_logs_fetcher=logs_fetcher
        ):
            if event:
                await websocket.send_json(event)

    except Exception as e:
        logger.exception("live session error %s", e)

    finally:
        recv_task.cancel()
        heartbeat_task.cancel()

        try:
            await websocket.close()
        except Exception:
            pass