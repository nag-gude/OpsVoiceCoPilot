"""
Ops Voice Co-Pilot - Gemini Live API session (Vertex AI).

Real-time, interruptible voice + vision agent. Accepts PCM audio (16 kHz)
and screenshot frames; streams back PCM audio (24 kHz) and transcript events.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, AsyncIterator, Callable, Optional

from services.core.config import get_settings
from services.core.logging_config import get_logger
from services.tools.logging_tool import get_recent_logs_for_agent

logger = get_logger(__name__)

LIVE_INPUT_SAMPLE_RATE = 16000
MAX_AUDIO_CHUNK = 32000

OPS_SYSTEM_INSTRUCTION = """
You are the Ops Voice Co-Pilot: a calm, concise, interruption-aware assistant
for operational triage. Tagline: "See it. Say it. Fix it."

Rules:
- Ground answers in screenshots or logs.
- If interrupted, pivot immediately.
- If using logs say "From the logs I just pulled..."
- Be concise: what broke, what's spiking, likely cause, next step.
"""

GetRecentLogsFetcher = Callable[[Optional[str], int], Any]


# ---------------------------------------------------------
# Gemini client
# ---------------------------------------------------------

# Gemini Live 2.5 Flash Native Audio supported regions (Vertex AI)
LIVE_API_REGION_DEFAULT = "europe-west1"
LIVE_API_MODEL = "gemini-live-2.5-flash-native-audio"


def _get_live_client():
    try:
        from google import genai
    except ImportError:
        return None

    settings = get_settings()

    if not settings.google_cloud_project:
        return None

    location = (
        settings.vertex_ai_location
        or settings.google_cloud_location
        or LIVE_API_REGION_DEFAULT
    )
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=location,
    )


def is_live_available() -> bool:
    try:
        from google import genai  # noqa
    except ImportError:
        return False

    settings = get_settings()
    return bool(settings.google_cloud_project)


# ---------------------------------------------------------
# Tools configuration
# ---------------------------------------------------------

def _build_tools_config(project_id: str):

    try:
        from google.genai import types
    except Exception:
        logger.warning("google.genai.types missing")
        return []

    get_recent_logs_decl = {
        "name": "get_recent_logs",
        "description": "Fetch recent Cloud Logging entries",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filter_expr": {"type": "STRING"},
                "page_size": {"type": "INTEGER"},
            },
        },
    }

    try:
        return [types.Tool(function_declarations=[get_recent_logs_decl])]
    except Exception:
        return []


# ---------------------------------------------------------
# Main session
# ---------------------------------------------------------

async def run_live_session(
    *,
    audio_input_queue: asyncio.Queue[bytes],
    text_input_queue: asyncio.Queue[str],
    video_input_queue: Optional[asyncio.Queue[bytes]] = None,
    audio_output_callback: Callable[[bytes], Any],
    event_callback: Optional[Callable[[dict], Any]] = None,
    get_recent_logs_fetcher: Optional[GetRecentLogsFetcher] = None,
) -> AsyncIterator[dict]:

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "error", "error": "google-genai not installed"}
        return

    settings = get_settings()
    client = _get_live_client()

    if not client:
        yield {"type": "error", "error": "Gemini Live not configured"}
        return

    project_id = settings.google_cloud_project
    model = settings.gemini_live_model

    video_queue = video_input_queue or asyncio.Queue()

    tools_config = _build_tools_config(project_id)

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Puck"
                )
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=OPS_SYSTEM_INSTRUCTION)]
        ),
        tools=tools_config if tools_config else None,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    event_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    # ---------------------------------------------------------
    # Senders
    # ---------------------------------------------------------

    async def send_audio():

        try:
            while True:

                chunk = await audio_input_queue.get()

                if not chunk or len(chunk) == 0:
                    continue

                if len(chunk) > MAX_AUDIO_CHUNK:
                    continue

                await session.send_realtime_input(
                    audio=types.Blob(
                        data=chunk,
                        mime_type="audio/pcm;rate=16000",
                    )
                )

        except asyncio.CancelledError:
            pass


    async def send_video():

        try:
            while True:

                frame = await video_queue.get()

                await session.send_realtime_input(
                    video=types.Blob(
                        data=frame,
                        mime_type="image/jpeg",
                    )
                )

        except asyncio.CancelledError:
            pass


    async def send_text():

        try:
            while True:

                text = await text_input_queue.get()

                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=text)],
                    ),
                    turn_complete=True,
                )

        except asyncio.CancelledError:
            pass


    # ---------------------------------------------------------
    # Receiver
    # ---------------------------------------------------------

    async def receive_loop():

        try:

            async for response in session.receive():

                # Tool call
                tool_call = getattr(response, "tool_call", None)

                if tool_call:

                    for fc in tool_call.function_calls or []:

                        name = getattr(fc, "name", None)
                        fc_id = getattr(fc, "id", None)
                        args = getattr(fc, "args", {}) or {}

                        if name == "get_recent_logs":

                            filter_expr = args.get("filter_expr")
                            page_size = args.get("page_size", 30)

                            if get_recent_logs_fetcher:
                                result = await get_recent_logs_fetcher(
                                    filter_expr, page_size
                                )
                            else:
                                result = get_recent_logs_for_agent(
                                    project_id,
                                    filter_expr=filter_expr,
                                    page_size=page_size,
                                )

                            await session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(
                                        id=fc_id,
                                        name=name,
                                        response={"result": result},
                                    )
                                ]
                            )

                    continue

                server_content = getattr(response, "server_content", None)

                if server_content:

                    model_turn = getattr(server_content, "model_turn", None)

                    if model_turn:

                        for part in model_turn.parts or []:

                            inline_data = getattr(part, "inline_data", None)

                            if inline_data and inline_data.data:

                                data = inline_data.data

                                if inspect.iscoroutinefunction(
                                    audio_output_callback
                                ):
                                    await audio_output_callback(data)
                                else:
                                    audio_output_callback(data)

                            # Emit transcript from text parts so the UI shows Co-pilot replies
                            part_text = getattr(part, "text", None)
                            if part_text and part_text.strip():
                                await event_queue.put({
                                    "type": "gemini",
                                    "text": part_text.strip(),
                                })

                    if server_content.input_transcription:
                        await event_queue.put({
                            "type": "user",
                            "text": server_content.input_transcription.text
                        })

                    if server_content.output_transcription:
                        await event_queue.put({
                            "type": "gemini",
                            "text": server_content.output_transcription.text
                        })

                    if server_content.turn_complete:
                        await event_queue.put({"type": "turn_complete"})

                    if server_content.interrupted:
                        await event_queue.put({"type": "interrupted"})

                # Some SDK versions expose transcript at top level
                response_text = getattr(response, "text", None)
                if response_text and response_text.strip():
                    await event_queue.put({
                        "type": "gemini",
                        "text": response_text.strip(),
                    })

        except Exception as e:

            logger.exception("Gemini receive error")

            await event_queue.put({
                "type": "error",
                "error": str(e)
            })

        finally:
            await event_queue.put(None)


    # ---------------------------------------------------------
    # Session
    # ---------------------------------------------------------

    try:

        logger.info(
            "Starting Gemini Live session",
            extra={"model": model, "project": project_id}
        )

        async with client.aio.live.connect(
            model=model,
            config=config
        ) as session:

            await asyncio.sleep(0.2)

            send_audio_task = asyncio.create_task(send_audio())
            send_video_task = asyncio.create_task(send_video())
            send_text_task = asyncio.create_task(send_text())
            recv_task = asyncio.create_task(receive_loop())

            try:

                while True:

                    event = await event_queue.get()

                    if event is None:
                        break

                    if event_callback:

                        if inspect.iscoroutinefunction(event_callback):
                            await event_callback(event)
                        else:
                            event_callback(event)

                    yield event

            finally:

                for task in (
                    send_audio_task,
                    send_video_task,
                    send_text_task,
                    recv_task,
                ):
                    task.cancel()

                for task in (
                    send_audio_task,
                    send_video_task,
                    send_text_task,
                    recv_task,
                ):
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    except Exception as e:

        logger.exception("Gemini Live session error")

        yield {
            "type": "error",
            "error": str(e),
        }