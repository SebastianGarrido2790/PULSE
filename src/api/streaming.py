"""PULSE — Streaming Route Handlers (SSE & WebSocket).

Provides transport adapters for streaming match replay events to external consumers
via Server-Sent Events (SSE) and WebSockets using the shared event generator.

Authority: Phase 6 Decisions D-1, D-5, D-6, D-8, D-10.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph

from src.api.schemas import MatchMetadataResponse, MatchReplayRequest, StreamPointEvent
from src.config.loader import load_params
from src.simulator.replay import generate_point_events, get_available_matches, load_match_records
from src.utils.logger import get_logger

logger = get_logger(__name__)

streaming_router = APIRouter(prefix="/v1/matches", tags=["Streaming"])


def format_sse_event(event: StreamPointEvent) -> str:
    """Format a StreamPointEvent into a standardized SSE data line.

    Args:
        event: Validated point or error event.

    Returns:
        str: Serialized SSE data payload ending in double newline.
    """
    return f"data: {event.model_dump_json()}\n\n"


async def sse_event_stream(
    match_id: str,
    speed_multiplier: float,
    graph: CompiledStateGraph,
    keep_alive_interval: float,
) -> AsyncGenerator[str, None]:
    """Yield formatted SSE event frames with interleaved keep-alive comments.

    Uses an internal async queue fed by a background producer task. This decouples
    heartbeat timeouts from in-flight generator execution so long inter-point delays
    never cause generator cancellation (D-5).

    Args:
        match_id: Match identifier to stream.
        speed_multiplier: Playback speed multiplier (0 for instant zero-delay replay).
        graph: In-memory compiled LangGraph application.
        keep_alive_interval: Interval in seconds between keep-alive heartbeat comments.

    Yields:
        str: SSE data frames or keep-alive comments.

    Authority: Phase 6 Decisions D-1, D-5, D-6, D-8.
    """
    queue: asyncio.Queue[StreamPointEvent | Exception | None] = asyncio.Queue()

    async def _producer() -> None:
        try:
            async for event in generate_point_events(
                match_id=match_id,
                speed_multiplier=speed_multiplier,
                graph=graph,
            ):
                await queue.put(event)
            await queue.put(None)
        except Exception as exc:
            await queue.put(exc)

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=keep_alive_interval)
                if item is None:
                    break
                if isinstance(item, Exception):
                    err_event = StreamPointEvent(
                        event_type="error",
                        match_id=match_id,
                        point_index=0,
                        error_message=f"Stream generator error: {item}",
                    )
                    yield format_sse_event(err_event)
                    break
                yield format_sse_event(item)
            except TimeoutError:
                # Emit SSE comment heartbeat per D-5 without cancelling producer
                yield ": keep-alive\n\n"
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass


@streaming_router.get(
    "",
    response_model=list[str],
    summary="List available matches for replay",
)
async def list_available_matches() -> list[str]:
    """Return all unique match IDs available in the dataset."""
    return get_available_matches()


@streaming_router.get(
    "/{match_id}",
    response_model=MatchMetadataResponse,
    summary="Get metadata for a specific match",
)
async def get_match_metadata(match_id: str) -> MatchMetadataResponse:
    """Return match metadata including surface, players, and total point count.

    Authority: Phase 6 Decision D-10.
    """
    try:
        records = load_match_records(match_id)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Match [{match_id}] could not be loaded: {exc}",
        ) from exc

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Match [{match_id}] not found in dataset",
        )

    first_pt = records[0]
    p1 = first_pt.server if first_pt.server_is_p1 else first_pt.returner
    p2 = first_pt.returner if first_pt.server_is_p1 else first_pt.server

    return MatchMetadataResponse(
        match_id=match_id,
        surface=first_pt.surface.value
        if hasattr(first_pt.surface, "value")
        else str(first_pt.surface),
        server_p1=p1,
        returner_p2=p2,
        total_points=len(records),
        match_format="bo3",
    )


@streaming_router.get(
    "/{match_id}/stream",
    summary="Stream match replay via Server-Sent Events (SSE)",
)
async def stream_match_sse(
    match_id: str,
    request: Request,
    replay_params: Annotated[MatchReplayRequest, Query()],
) -> StreamingResponse:
    """Stream point events for a match via Server-Sent Events (SSE).

    Each client connection instantiates an independent event generator (D-8)
    consuming the compiled graph on app.state (D-12). Periodic ': keep-alive\n\n'
    comments are interleaved during idle periods (D-5).

    Authority: Phase 6 Decisions D-1, D-5, D-6, D-8, D-10.
    """
    graph: CompiledStateGraph | None = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="PULSE graph engine is not initialized or still starting up",
        )

    params = load_params()
    keep_alive = params.api.sse_keep_alive_interval_s

    return StreamingResponse(
        sse_event_stream(
            match_id=match_id,
            speed_multiplier=replay_params.speed_multiplier,
            graph=graph,
            keep_alive_interval=keep_alive,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@streaming_router.websocket(
    "/{match_id}/ws",
)
async def stream_match_ws(
    websocket: WebSocket,
    match_id: str,
    replay_params: Annotated[MatchReplayRequest, Query()],
) -> None:
    """Stream point events for a match over a WebSocket connection.

    Consumes the exact same underlying event generator as the SSE route (D-1),
    transmitting raw JSON strings per point event (D-8).

    Authority: Phase 6 Decisions D-1, D-6, D-8, D-10.
    """
    await websocket.accept()
    graph: CompiledStateGraph | None = getattr(websocket.app.state, "graph", None)
    if graph is None:
        await websocket.close(
            code=1011,
            reason="PULSE graph engine is not initialized",
        )
        return

    try:
        async for event in generate_point_events(
            match_id=match_id,
            speed_multiplier=replay_params.speed_multiplier,
            graph=graph,
        ):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally for match [%s]", match_id)
    except Exception as e:
        logger.error("WebSocket streaming exception for match [%s]: %s", match_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
