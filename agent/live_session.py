"""Ops Voice Co-Pilot - Gemini Live API session (Vertex AI).

Real-time, interruptible voice + vision agent. Accepts PCM audio (16 kHz) and
screenshot/screen-share frames; streams back PCM (24 kHz) and transcript events.
Uses ops-native persona and optional tool: get_recent_logs (Cloud Logging).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, AsyncIterator, Callable, Optional

from core.config import get_settings
from core.logging_config import get_logger
from tools.logging_tool import get_recent_logs_for_agent

# Type for optional remote get_recent_logs (e.g. Tools service HTTP call)
GetRecentLogsFetcher = Callable[[Optional[str], int], Any]  # Awaitable[str] when called

logger = get_logger(__name__)

LIVE_INPUT_SAMPLE_RATE = 16000

OPS_SYSTEM_INSTRUCTION = """You are the Ops Voice Co-Pilot: a calm, concise, interruption-aware assistant for operational triage. Tagline: "See it. Say it. Fix it."

Rules:
- Ground every answer in what you see (the dashboard/screenshot or log snippet the user shared) or in the results of tool calls. Give brief verbal citations, e.g. "The spike in the top-left graph at 14:32 aligns with these error lines in the log snippet at the bottom of your screen."
- If the user interrupts (e.g. "Wait, what about the database?"), immediately pivot to that topic using the current screen or logs—do not finish the previous sentence.
- When you use get_recent_logs, say something like "From the logs I just pulled..." so the user knows the answer is grounded in live data.
- If you are uncertain or lack evidence from the image or logs, say so. Do not state facts not supported by the context.
- Keep responses concise and ops-focused: what broke, what's spiking, likely cause, next step."""


def _get_live_client():
    """Return genai Client for Vertex AI, or None."""
    try:
        from google import genai
    except ImportError:
        return None
    settings = get_settings()
    if not settings.google_cloud_project:
        return None
    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.vertex_ai_location,
    )


def is_live_available() -> bool:
    """True if Live API can be used (google-genai + project set)."""
    try:
        from google import genai  # noqa: F401
    except ImportError:
        return False
    settings = get_settings()
    return bool(settings.google_cloud_project)


def _build_tools_config(project_id: str):
    """Build tools config for Live API: get_recent_logs (Cloud Logging)."""
    try:
        from google.genai import types
    except ImportError:
        return []

    # Use dict form for compatibility (some SDK versions prefer it)
    get_recent_logs_decl = {
        "name": "get_recent_logs",
        "description": "Fetch the most recent log entries from Google Cloud Logging for the current project. Use when the user asks 'why did this break?' or about errors. Returns recent log lines (timestamp, severity, message). Say 'From the logs I just pulled...' when using this.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filter_expr": {
                    "type": "STRING",
                    "description": "Optional filter, e.g. severity>=ERROR. Keep short.",
                },
                "page_size": {
                    "type": "INTEGER",
                    "description": "Max log entries to return (default 30).",
                },
            },
        },
    }
    try:
        return [types.Tool(function_declarations=[get_recent_logs_decl])]
    except Exception:
        return []


async def run_live_session(
    *,
    audio_input_queue: asyncio.Queue[bytes],
    text_input_queue: asyncio.Queue[str],
    video_input_queue: Optional[asyncio.Queue[bytes]] = None,
    audio_output_callback: Callable[[bytes], Any],
    event_callback: Optional[Callable[[dict], Any]] = None,
    get_recent_logs_fetcher: Optional[GetRecentLogsFetcher] = None,
) -> AsyncIterator[dict]:
    """
    Run one Gemini Live session: ops co-pilot with voice + vision + get_recent_logs.
    Yields events: {"type": "user"|"gemini", "text": "..."}, turn_complete, interrupted, error.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        err = "Live API not configured. Install google-genai."
        yield {"type": "error", "error": err, "message": err}
        return

    client = _get_live_client()
    if not client:
        err = "Live API not configured. Set GOOGLE_CLOUD_PROJECT."
        yield {"type": "error", "error": err, "message": err}
        return

    settings = get_settings()
    model = settings.gemini_live_model
    project_id = settings.google_cloud_project
    video_queue = video_input_queue or asyncio.Queue()

    tools_config = _build_tools_config(project_id) if project_id else []

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"),
            ),
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=OPS_SYSTEM_INSTRUCTION)],
        ),
        tools=tools_config if tools_config else None,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    async def send_audio():
        try:
            while True:
                chunk = await audio_input_queue.get()
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=chunk,
                        mime_type=f"audio/pcm;rate={LIVE_INPUT_SAMPLE_RATE}",
                    ),
                )
        except asyncio.CancelledError:
            pass

    async def send_video():
        try:
            while True:
                chunk = await video_queue.get()
                await session.send_realtime_input(
                    video=types.Blob(data=chunk, mime_type="image/jpeg"),
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

    event_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    async def receive_loop():
        try:
            async for response in session.receive():
                # Tool call: run get_recent_logs and send_tool_response
                tool_call = getattr(response, "tool_call", None)
                if tool_call:
                    fcs = getattr(tool_call, "function_calls", None) or []
                    for fc in fcs:
                        name = getattr(fc, "name", None)
                        fc_id = getattr(fc, "id", None)
                        args = getattr(fc, "args", None) or {}
                        if name == "get_recent_logs":
                            filter_expr = args.get("filter_expr")
                            page_size = args.get("page_size", 30)
                            if get_recent_logs_fetcher:
                                try:
                                    result_text = await get_recent_logs_fetcher(
                                        filter_expr, page_size
                                    )
                                except Exception as e:
                                    logger.exception("get_recent_logs_fetcher: %s", e)
                                    result_text = f"Error fetching logs: {e}"
                            else:
                                result_text = get_recent_logs_for_agent(
                                    project_id,
                                    filter_expr=filter_expr,
                                    page_size=page_size,
                                )
                            try:
                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            id=fc_id,
                                            name=name,
                                            response={"result": result_text},
                                        )
                                    ]
                                )
                            except Exception as e:
                                logger.exception("send_tool_response: %s", e)
                        else:
                            try:
                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            id=fc_id,
                                            name=name,
                                            response={"error": f"Unknown function: {name}"},
                                        )
                                    ]
                                )
                            except Exception as e:
                                logger.exception("send_tool_response: %s", e)
                    continue

                server_content = getattr(response, "server_content", None)
                if server_content:
                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn:
                        parts = getattr(model_turn, "parts", None) or []
                        for part in parts:
                            inline_data = getattr(part, "inline_data", None)
                            if inline_data and getattr(inline_data, "data", None):
                                data = inline_data.data
                                if inspect.iscoroutinefunction(audio_output_callback):
                                    await audio_output_callback(data)
                                else:
                                    audio_output_callback(data)
                    if getattr(server_content, "input_transcription", None):
                        t = getattr(server_content.input_transcription, "text", None)
                        if t:
                            await event_queue.put({"type": "user", "text": t})
                    if getattr(server_content, "output_transcription", None):
                        t = getattr(server_content.output_transcription, "text", None)
                        if t:
                            await event_queue.put({"type": "gemini", "text": t})
                    if getattr(server_content, "turn_complete", False):
                        await event_queue.put({"type": "turn_complete"})
                    if getattr(server_content, "interrupted", False):
                        await event_queue.put({"type": "interrupted"})
                if getattr(response, "text", None):
                    await event_queue.put({"type": "gemini", "text": response.text})
        except Exception as e:
            logger.exception("Live receive_loop: %s", e)
            err = str(e)
            await event_queue.put({"type": "error", "error": err, "message": err})
        finally:
            await event_queue.put(None)

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            send_audio_task = asyncio.create_task(send_audio())
            send_video_task = asyncio.create_task(send_video())
            send_text_task = asyncio.create_task(send_text())
            recv_task = asyncio.create_task(receive_loop())

            try:
                while True:
                    event = await event_queue.get()
                    if event is None:
                        break
                    if event.get("type") == "error":
                        yield event
                        break
                    if event_callback:
                        if inspect.iscoroutinefunction(event_callback):
                            await event_callback(event)
                        else:
                            event_callback(event)
                    yield event
            finally:
                send_audio_task.cancel()
                send_video_task.cancel()
                send_text_task.cancel()
                recv_task.cancel()
                for t in (send_audio_task, send_video_task, send_text_task, recv_task):
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
    except Exception as e:
        logger.exception("Live session error: %s", e)
        err = str(e)
        yield {"type": "error", "error": err, "message": err}
