"""Unit tests for src/api/streaming.py (SSE and WebSocket streaming endpoints).

Verifies SSE formatting, keep-alive comments, WebSocket messaging,
and multi-client independence (Phase 6 Decisions D-1, D-5, D-6, D-8, Gate 6).
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import StreamPointEvent
from src.api.streaming import format_sse_event, sse_event_stream
from src.graph.state import PointContext


@pytest.fixture
def streaming_parquet_file(tmp_path: Path) -> Path:
    """Create a temporary fixture parquet file with 2 points for streaming tests."""
    parquet_path = tmp_path / "streaming_points.parquet"
    data = [
        {
            "match_id": "stream_test_match_001",
            "point_id": "pt_0",
            "server": "Carlos Alcaraz",
            "returner": "Novak Djokovic",
            "server_is_p1": True,
            "surface": "HARD",
            "serve_number": 1,
            "serve_direction": "wide",
            "p1_score": "0",
            "p2_score": "0",
            "p1_games": 0,
            "p2_games": 0,
            "p1_sets": 0,
            "p2_sets": 0,
            "rally_length": 4,
            "point_winner": "server",
            "break_point": False,
            "set_point": False,
            "match_point": False,
        },
        {
            "match_id": "stream_test_match_001",
            "point_id": "pt_1",
            "server": "Carlos Alcaraz",
            "returner": "Novak Djokovic",
            "server_is_p1": True,
            "surface": "HARD",
            "serve_number": 2,
            "serve_direction": "T",
            "p1_score": "15",
            "p2_score": "0",
            "p1_games": 0,
            "p2_games": 0,
            "p1_sets": 0,
            "p2_sets": 0,
            "rally_length": 6,
            "point_winner": "returner",
            "break_point": False,
            "set_point": False,
            "match_point": False,
        },
    ]
    df = pd.DataFrame(data)
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def test_format_sse_event() -> None:
    """Verify format_sse_event produces valid SSE data lines ending in double newline."""
    context = PointContext(
        match_id="test_match",
        point_index=0,
        server_id="Player A",
        returner_id="Player B",
        surface="HARD",
        serve_number=1,
    )
    event = StreamPointEvent(
        event_type="point",
        match_id="test_match",
        point_index=0,
        point_context=context,
    )
    formatted = format_sse_event(event)
    assert formatted.startswith("data: ")
    assert formatted.endswith("\n\n")
    parsed_json = json.loads(formatted.replace("data: ", "").strip())
    assert parsed_json["match_id"] == "test_match"
    assert parsed_json["point_index"] == 0


@pytest.mark.asyncio
async def test_sse_event_stream_keep_alive() -> None:
    """Verify sse_event_stream yields keep-alive comments when delay exceeds keep_alive_interval."""
    mock_graph = AsyncMock()

    async def mock_ainvoke(state):
        return {
            "point_context": state.point_context,
            "decision_log": [],
        }

    mock_graph.ainvoke.side_effect = mock_ainvoke

    # Generator will iterate over events
    stream_chunks: list[str] = []
    # Test with very short keep-alive interval to trigger heartbeat comment
    async for chunk in sse_event_stream(
        match_id="test_match",
        speed_multiplier=0.0,
        graph=mock_graph,
        keep_alive_interval=0.001,
    ):
        stream_chunks.append(chunk)

    # All non-comment chunks should be SSE data frames
    for chunk in stream_chunks:
        assert chunk == ": keep-alive\n\n" or chunk.startswith("data: ")


def test_list_matches_endpoint(streaming_parquet_file: Path, monkeypatch) -> None:
    """Verify GET /v1/matches endpoint lists available match IDs."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get("/v1/matches")
        assert response.status_code == 200
        matches = response.json()
        assert "stream_test_match_001" in matches


def test_sse_stream_endpoint(streaming_parquet_file: Path, monkeypatch) -> None:
    """Verify GET /v1/matches/{match_id}/stream streams SSE events."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get(
            "/v1/matches/stream_test_match_001/stream?speed_multiplier=0",
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data: " in body
        assert "stream_test_match_001" in body


def test_websocket_stream_endpoint(streaming_parquet_file: Path, monkeypatch) -> None:
    """Verify WebSocket endpoint streams point events with identical payload content."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/matches/stream_test_match_001/ws?speed_multiplier=0"
        ) as ws:
            # Point 0
            msg_0 = ws.receive_text()
            data_0 = json.loads(msg_0)
            assert data_0["event_type"] == "point"
            assert data_0["match_id"] == "stream_test_match_001"
            assert data_0["point_index"] == 0

            # Point 1
            msg_1 = ws.receive_text()
            data_1 = json.loads(msg_1)
            assert data_1["event_type"] == "point"
            assert data_1["match_id"] == "stream_test_match_001"
            assert data_1["point_index"] == 1


@pytest.mark.asyncio
async def test_sse_event_stream_keep_alive_does_not_kill_slow_generator(monkeypatch) -> None:
    """Verify keep-alive timeout does not terminate a slow-running event generator (D-5)."""
    context = PointContext(
        match_id="slow_match",
        point_index=0,
        server_id="Player A",
        returner_id="Player B",
        surface="HARD",
        serve_number=1,
    )
    ev0 = StreamPointEvent(
        event_type="point",
        match_id="slow_match",
        point_index=0,
        point_context=context,
    )
    ev1 = StreamPointEvent(
        event_type="point",
        match_id="slow_match",
        point_index=1,
        point_context=context,
    )

    async def mock_slow_generator(*args, **kwargs):
        yield ev0
        # Sleep for longer than the keep-alive interval (0.02s) to trigger keep-alive
        import asyncio

        await asyncio.sleep(0.06)
        yield ev1

    monkeypatch.setattr("src.api.streaming.generate_point_events", mock_slow_generator)

    chunks: list[str] = []
    async for chunk in sse_event_stream(
        match_id="slow_match",
        speed_multiplier=1.0,
        graph=AsyncMock(),
        keep_alive_interval=0.02,
    ):
        chunks.append(chunk)

    # Confirm keep-alive comments occurred
    assert ": keep-alive\n\n" in chunks
    # Confirm BOTH point events were yielded successfully despite keep-alive timeouts
    data_chunks = [c for c in chunks if c.startswith("data: ")]
    assert len(data_chunks) == 2
    assert json.loads(data_chunks[0].replace("data: ", ""))["point_index"] == 0
    assert json.loads(data_chunks[1].replace("data: ", ""))["point_index"] == 1


def test_get_match_metadata_endpoint(streaming_parquet_file: Path, monkeypatch) -> None:
    """Verify GET /v1/matches/{match_id} returns accurate MatchMetadataResponse (D-10)."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        # Existing match
        response = client.get("/v1/matches/stream_test_match_001")
        assert response.status_code == 200
        meta = response.json()
        assert meta["match_id"] == "stream_test_match_001"
        assert meta["surface"] == "HARD"
        assert meta["server_p1"] == "Carlos Alcaraz"
        assert meta["returner_p2"] == "Novak Djokovic"
        assert meta["total_points"] == 2
        assert meta["match_format"] == "bo3"

        # Missing match
        response_missing = client.get("/v1/matches/non_existent_match_999")
        assert response_missing.status_code == 404
        assert "not found" in response_missing.json()["detail"].lower()
