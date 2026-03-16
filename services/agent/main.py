"""Agent microservice: Gemini Live API voice + vision.

Exposes /health and WebSocket /ws/live/voice. When TOOLS_SERVICE_URL is set,
get_recent_logs is fulfilled by calling the Tools service; otherwise in-process.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import base64
import json
import os

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from core.config import get_settings
from core.logging_config import get_logger
from agent.live_session import is_live_available, run_live_session

logger = get_logger(__name__)
app = FastAPI(title="Ops Voice Co-Pilot Agent", version="1.0.0")

TOOLS_SERVICE_URL = os.environ.get("TOOLS_SERVICE_URL", "").rstrip("/")


def _make_get_recent_logs_fetcher():
    """Return an async fetcher that calls Tools service, or None if not configured."""
    if not TOOLS_SERVICE_URL:
        return None

    async def fetcher(filter_expr, page_size):
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{TOOLS_SERVICE_URL}/logs/recent",
                json={"filter_expr": filter_expr, "page_size": page_size},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("result", data.get("error", ""))

    return fetcher


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ops-voice-copilot-agent",
        "live_available": is_live_available(),
        "tools_service": TOOLS_SERVICE_URL or "in-process",
    }


@app.websocket("/ws/live/voice")
async def websocket_live_voice(websocket: WebSocket):
    """Live API voice: binary PCM + JSON image/text. Uses Tools service for get_recent_logs when set."""
    await websocket.accept()
    if not is_live_available():
        msg = "Live API not configured. Set GOOGLE_CLOUD_PROJECT and deploy with Vertex AI."
        await websocket.send_json({"type": "error", "error": msg, "message": msg})
        await websocket.close()
        return

    audio_input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    text_input_queue: asyncio.Queue[str] = asyncio.Queue()
    video_input_queue: asyncio.Queue[bytes] = asyncio.Queue()
    get_recent_logs_fetcher = _make_get_recent_logs_fetcher()

    async def audio_output_callback(data: bytes):
        await websocket.send_bytes(data)

    PROACTIVE_PROMPT = (
        "Look at the screenshot I just shared. "
        "In one short sentence, say what you notice (e.g. errors, spikes, anomalies) and offer to walk through the likely cause. Then stop."
    )

    async def receive_from_client():
        try:
            while True:
                message = await websocket.receive()
                if message.get("bytes"):
                    await audio_input_queue.put(message["bytes"])
                elif message.get("text"):
                    text = message["text"]
                    try:
                        payload = json.loads(text)
                        if isinstance(payload, dict) and payload.get("type") == "image":
                            b64 = payload.get("data", "")
                            image_data = base64.b64decode(b64)
                            await video_input_queue.put(image_data)
                            if payload.get("proactive"):
                                async def send_proactive_prompt():
                                    await asyncio.sleep(1.0)
                                    await text_input_queue.put(PROACTIVE_PROMPT)
                                asyncio.create_task(send_proactive_prompt())
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass
                    await text_input_queue.put(text)
        except WebSocketDisconnect:
            logger.info("live voice websocket disconnected")
        except Exception as e:
            logger.exception("live voice receive error: %s", e)

    recv_task = asyncio.create_task(receive_from_client())

    try:
        async for event in run_live_session(
            audio_input_queue=audio_input_queue,
            text_input_queue=text_input_queue,
            video_input_queue=video_input_queue,
            audio_output_callback=audio_output_callback,
            get_recent_logs_fetcher=get_recent_logs_fetcher,
        ):
            if event and event.get("type") == "error":
                await websocket.send_json(event)
                break
            if event:
                await websocket.send_json(event)
    except Exception as e:
        logger.exception("live voice session error: %s", e)
        err = str(e)
        await websocket.send_json({"type": "error", "error": err, "message": err})
    finally:
        recv_task.cancel()
        try:
            await recv_task
        except asyncio.CancelledError:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
