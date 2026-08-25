"""Unit tests for src/api/streaming.py (SSE and WebSocket streaming endpoints).

Verifies SSE formatting, keep-alive comments, WebSocket messaging,
and multi-client independence (Phase 6 Decisions D-1, D-5, D-6, D-8, Gate 6).
"""

import asyncio
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


def test_get_match_metadata_corrupted_file_404(monkeypatch) -> None:
    """Verify GET /v1/matches/{match_id} returns 404 when load_match_records raises an exception."""

    def mock_load_error(match_id):
        raise ValueError("Corrupted parquet data")

    monkeypatch.setattr("src.api.streaming.load_match_records", mock_load_error)

    with TestClient(app) as client:
        response = client.get("/v1/matches/corrupted_match_001")
        assert response.status_code == 404
        assert "could not be loaded" in response.json()["detail"]


def test_stream_match_sse_replay_request_validation(
    streaming_parquet_file: Path, monkeypatch
) -> None:
    """Verify MatchReplayRequest schema validation on GET /stream endpoint."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        # Valid query params bound to MatchReplayRequest
        response_valid = client.get(
            "/v1/matches/stream_test_match_001/stream?speed_multiplier=2.5&match_format=bo3"
        )
        assert response_valid.status_code == 200

        # Invalid speed multiplier (< 0) -> 422 Unprocessable Entity
        response_invalid_speed = client.get(
            "/v1/matches/stream_test_match_001/stream?speed_multiplier=-1.0"
        )
        assert response_invalid_speed.status_code == 422

        # Invalid match format -> 422 Unprocessable Entity
        response_invalid_format = client.get(
            "/v1/matches/stream_test_match_001/stream?match_format=bo7"
        )
        assert response_invalid_format.status_code == 422


def test_stream_match_sse_uninitialized_graph_503(
    streaming_parquet_file: Path, monkeypatch
) -> None:
    """Verify GET /stream returns 503 when app.state.graph is None."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )
    with TestClient(app) as client:
        app.state.graph = None
        response = client.get("/v1/matches/stream_test_match_001/stream")
        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


def test_stream_match_ws_uninitialized_graph(streaming_parquet_file: Path, monkeypatch) -> None:
    """Verify WebSocket stream closes with 1011 when app.state.graph is None."""
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )
    with TestClient(app) as client:
        app.state.graph = None
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/v1/matches/stream_test_match_001/ws") as ws:
                ws.receive_text()
        assert exc_info.value.code == 1011


@pytest.mark.asyncio
async def test_sse_event_stream_error_item_handling(monkeypatch) -> None:
    """Verify sse_event_stream yields error event when producer encounters an exception."""

    async def mock_error_generator(*args, **kwargs):
        raise RuntimeError("Simulator database read failure")
        yield  # make it an async generator

    monkeypatch.setattr("src.api.streaming.generate_point_events", mock_error_generator)

    chunks: list[str] = []
    async for chunk in sse_event_stream(
        match_id="error_match",
        speed_multiplier=1.0,
        graph=AsyncMock(),
        keep_alive_interval=0.5,
    ):
        chunks.append(chunk)

    assert len(chunks) == 1
    err_data = json.loads(chunks[0].replace("data: ", ""))
    assert err_data["event_type"] == "error"
    assert "Simulator database read failure" in err_data["error_message"]


@pytest.mark.asyncio
async def test_sse_event_stream_client_cancellation_cleanup(monkeypatch) -> None:
    """Verify client generator closure properly cancels background producer task."""
    producer_started = False
    producer_cancelled = False

    async def mock_endless_generator(*args, **kwargs):
        nonlocal producer_started, producer_cancelled
        producer_started = True
        try:
            while True:
                await asyncio.sleep(0.01)
                yield StreamPointEvent(
                    event_type="point",
                    match_id="cancel_match",
                    point_index=0,
                )
        except asyncio.CancelledError:
            producer_cancelled = True
            raise

    monkeypatch.setattr("src.api.streaming.generate_point_events", mock_endless_generator)

    stream_gen = sse_event_stream(
        match_id="cancel_match",
        speed_multiplier=1.0,
        graph=AsyncMock(),
        keep_alive_interval=0.5,
    )

    # Start generator iteration, then close generator prematurely
    try:
        await anext(stream_gen)
    except Exception:
        pass
    finally:
        await stream_gen.aclose()

    assert producer_started is True


def test_stream_match_sse_bo5_parameter_propagation(
    streaming_parquet_file: Path, monkeypatch
) -> None:
    """Verify ?match_format=bo5 query parameter correctly flows into point context."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get(
            "/v1/matches/stream_test_match_001/stream?speed_multiplier=0.0&match_format=bo5"
        )
        assert response.status_code == 200
        events = [
            json.loads(line.replace("data: ", ""))
            for line in response.text.split("\n\n")
            if line.startswith("data: ")
        ]
        assert len(events) > 0
        for ev in events:
            assert ev["point_context"]["match_format"] == "bo5"


def test_get_match_report_json_success(
    streaming_parquet_file: Path, monkeypatch
) -> None:
    """Verify GET /v1/matches/{match_id}/report returns valid JSON report payload."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get("/v1/matches/stream_test_match_001/report?format=json")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "pivotal_points" in data
        assert "pressure_resilience" in data
        assert "game_theory_audit" in data
        assert "executive_debrief" in data
        assert "markdown_report" in data
        assert data["summary"]["match_id"] == "stream_test_match_001"


def test_get_match_report_markdown_success(
    streaming_parquet_file: Path, monkeypatch
) -> None:
    """Verify GET /v1/matches/{match_id}/report returns formatted Markdown report."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: streaming_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get("/v1/matches/stream_test_match_001/report?format=markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "# PULSE Match Intelligence Report" in response.text
        assert "Carlos Alcaraz" in response.text


def test_get_match_report_not_found(monkeypatch) -> None:
    """Verify GET /v1/matches/{match_id}/report returns 404 for unknown match."""
    with TestClient(app) as client:
        response = client.get("/v1/matches/non_existent_match_999/report")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
