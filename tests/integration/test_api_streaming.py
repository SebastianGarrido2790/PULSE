"""PULSE — Integration Tests for API Streaming & Persistence (Phase 6).

Verifies end-to-end integration across the API streaming stack:
1. SSE streaming against real/fixture match with full SQLite persistence audit verification.
2. WebSocket stream content parity vs SSE stream (proving D-1 single-source-of-truth).
3. Forced mid-stream failure handling (D-13 fail-loud behavior).

Authority: Phase 6 Decisions D-1, D-4, D-5, D-6, D-8, D-12, D-13, Gate 8.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config.loader import load_params
from src.simulator.replay import generate_point_events
from src.utils.persistence import get_decision_logs, get_tactical_outputs, init_db


@pytest.fixture
def integration_parquet_file(tmp_path: Path) -> Path:
    """Create a multi-point hermetic fixture match dataset for integration tests."""
    parquet_path = tmp_path / "integration_points.parquet"
    data = [
        {
            "match_id": "integ_match_2026",
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
            "rally_length": 3,
            "point_winner": "server",
            "break_point": False,
            "set_point": False,
            "match_point": False,
        },
        {
            "match_id": "integ_match_2026",
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
            "rally_length": 5,
            "point_winner": "returner",
            "break_point": False,
            "set_point": False,
            "match_point": False,
        },
        {
            "match_id": "integ_match_2026",
            "point_id": "pt_2",
            "server": "Carlos Alcaraz",
            "returner": "Novak Djokovic",
            "server_is_p1": True,
            "surface": "HARD",
            "serve_number": 1,
            "serve_direction": "wide",
            "p1_score": "30",
            "p2_score": "40",
            "p1_games": 4,
            "p2_games": 4,
            "p1_sets": 1,
            "p2_sets": 1,
            "rally_length": 8,
            "point_winner": "server",
            "break_point": True,
            "set_point": False,
            "match_point": False,
        },
    ]
    df = pd.DataFrame(data)
    df.to_parquet(parquet_path, index=False)
    return parquet_path


@pytest.fixture
def mock_llm_narrative():
    """Mock narrative LLM to keep integration tests fast and deterministic."""
    with patch(
        "src.graph.tactical_output.call_narrative_llm",
        new_callable=AsyncMock,
        return_value="Exploit T serve under high pressure breakpoint.",
    ) as mock:
        yield mock


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sse_streaming_and_persistence_parity(
    integration_parquet_file: Path,
    mock_llm_narrative: AsyncMock,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Verify SSE streaming delivers exact events and populates SQLite persistence one-to-one."""
    db_file = tmp_path / "integ_session.db"
    await init_db(db_file)

    cfg = load_params()
    cfg.api.db_path = str(db_file)
    monkeypatch.setattr("src.config.loader.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.main.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.streaming.load_params", lambda: cfg)
    monkeypatch.setattr("src.simulator.replay.load_params", lambda: cfg)
    monkeypatch.setattr("src.utils.persistence.load_params", lambda: cfg)
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: integration_parquet_file,
    )

    with TestClient(app) as client:
        response = client.get(
            "/v1/matches/integ_match_2026/stream?speed_multiplier=0",
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE lines: data: {...}\n\n
        sse_events: list[dict] = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                sse_events.append(json.loads(line.replace("data: ", "")))

        assert len(sse_events) == 3
        for idx, ev in enumerate(sse_events):
            assert ev["event_type"] == "point"
            assert ev["match_id"] == "integ_match_2026"
            assert ev["point_index"] == idx
            assert ev["leverage_result"] is not None

        # Compare directly with library generator events
        gen_events: list[dict] = []
        async for gen_ev in generate_point_events(
            match_id="integ_match_2026",
            speed_multiplier=0.0,
            graph=app.state.graph,
            parquet_path=integration_parquet_file,
            db_path=db_file,
            params=cfg,
        ):
            gen_events.append(json.loads(gen_ev.model_dump_json()))

        assert len(sse_events) == len(gen_events)
        for sse_ev, gen_ev in zip(sse_events, gen_events, strict=True):
            assert sse_ev["match_id"] == gen_ev["match_id"]
            assert sse_ev["point_index"] == gen_ev["point_index"]
            assert sse_ev["event_type"] == gen_ev["event_type"]

        # Verify SQLite persistence layer recorded points
        persisted_logs = await get_decision_logs("integ_match_2026", db_path=db_file)
        assert len(persisted_logs) >= 3

        persisted_outputs = await get_tactical_outputs("integ_match_2026", db_path=db_file)
        assert len(persisted_outputs) >= 3


@pytest.mark.integration
def test_websocket_and_sse_content_parity(
    integration_parquet_file: Path,
    mock_llm_narrative: AsyncMock,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Verify WebSocket stream and SSE stream produce identical content payloads (D-1)."""
    db_file = tmp_path / "integ_ws_session.db"
    cfg = load_params()
    cfg.api.db_path = str(db_file)
    monkeypatch.setattr("src.config.loader.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.main.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.streaming.load_params", lambda: cfg)
    monkeypatch.setattr("src.simulator.replay.load_params", lambda: cfg)
    monkeypatch.setattr("src.utils.persistence.load_params", lambda: cfg)
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: integration_parquet_file,
    )

    with TestClient(app) as client:
        # 1. Collect SSE events
        sse_response = client.get(
            "/v1/matches/integ_match_2026/stream?speed_multiplier=0",
            headers={"Accept": "text/event-stream"},
        )
        assert sse_response.status_code == 200

        sse_payloads: list[dict] = []
        for line in sse_response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                sse_payloads.append(json.loads(line.replace("data: ", "")))

        # 2. Collect WebSocket events
        ws_payloads: list[dict] = []
        with client.websocket_connect("/v1/matches/integ_match_2026/ws?speed_multiplier=0") as ws:
            while len(ws_payloads) < len(sse_payloads):
                msg = ws.receive_text()
                ws_payloads.append(json.loads(msg))

        # 3. Assert direct 1-to-1 payload equivalence
        assert len(ws_payloads) == len(sse_payloads)
        for ws_ev, sse_ev in zip(ws_payloads, sse_payloads, strict=True):
            assert ws_ev["match_id"] == sse_ev["match_id"]
            assert ws_ev["point_index"] == sse_ev["point_index"]
            assert ws_ev["event_type"] == sse_ev["event_type"]
            assert ws_ev["point_context"] == sse_ev["point_context"]


@pytest.mark.integration
def test_mid_stream_failure_integration(
    integration_parquet_file: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Verify fail-loud behavior on forced mid-stream exception (D-13)."""
    db_file = tmp_path / "integ_err_session.db"
    cfg = load_params()
    cfg.api.db_path = str(db_file)
    monkeypatch.setattr("src.config.loader.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.main.load_params", lambda: cfg)
    monkeypatch.setattr("src.api.streaming.load_params", lambda: cfg)
    monkeypatch.setattr("src.simulator.replay.load_params", lambda: cfg)
    monkeypatch.setattr("src.utils.persistence.load_params", lambda: cfg)
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: integration_parquet_file,
    )

    with TestClient(app) as client:
        call_count = 0
        original_ainvoke = app.state.graph.ainvoke

        async def mock_failing_ainvoke(state):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Forced Markov solver divergence exception")
            return await original_ainvoke(state)

        monkeypatch.setattr(app.state.graph, "ainvoke", mock_failing_ainvoke)

        response = client.get(
            "/v1/matches/integ_match_2026/stream?speed_multiplier=0",
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200

        events: list[dict] = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                events.append(json.loads(line.replace("data: ", "")))

        # Point 0 succeeded, Point 1 threw exception -> total 2 events
        assert len(events) == 2
        assert events[0]["event_type"] == "point"
        assert events[0]["point_index"] == 0

        assert events[1]["event_type"] == "error"
        assert events[1]["point_index"] == 1
        assert "Forced Markov solver divergence exception" in events[1]["error_message"]
