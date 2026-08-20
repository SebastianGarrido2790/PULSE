"""Unit tests for src/simulator/replay.py (shared async generator and match replay).

Verifies end-to-end replay, point-by-point ordering, persistence integration,
and fail-loud mid-stream exception handling (Phase 6 Decisions D-1, D-2, D-4, D-6, D-13, Gate 4).
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from src.api.schemas import StreamPointEvent
from src.graph.state import PointContext, PulseGraphState
from src.simulator.replay import (
    generate_point_events,
    get_available_matches,
    load_match_records,
    run_cli,
)
from src.utils.persistence import get_decision_logs, init_db


@pytest.fixture
def sample_parquet_file(tmp_path: Path) -> Path:
    """Create a small hermetic points parquet file with 3 points for testing."""
    parquet_path = tmp_path / "test_points.parquet"
    data = [
        {
            "match_id": "test_replay_match_001",
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
            "match_id": "test_replay_match_001",
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
        {
            "match_id": "test_replay_match_001",
            "point_id": "pt_2",
            "server": "Carlos Alcaraz",
            "returner": "Novak Djokovic",
            "server_is_p1": True,
            "surface": "HARD",
            "serve_number": 1,
            "serve_direction": "body",
            "p1_score": "15",
            "p2_score": "15",
            "p1_games": 0,
            "p2_games": 0,
            "p1_sets": 0,
            "p2_sets": 0,
            "rally_length": 2,
            "point_winner": "server",
            "break_point": False,
            "set_point": False,
            "match_point": False,
        },
    ]
    df = pd.DataFrame(data)
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def test_load_match_records_and_available_matches(sample_parquet_file: Path) -> None:
    """Verify loading records and discovering available match IDs from parquet."""
    matches = get_available_matches(parquet_path=sample_parquet_file)
    assert matches == ["test_replay_match_001"]

    records = load_match_records("test_replay_match_001", parquet_path=sample_parquet_file)
    assert len(records) == 3
    assert records[0].point_id == "pt_0"
    assert records[1].point_id == "pt_1"
    assert records[2].point_id == "pt_2"


@pytest.mark.asyncio
async def test_generate_point_events_end_to_end(
    sample_parquet_file: Path,
    tmp_path: Path,
) -> None:
    """Verify full end-to-end replay generation with mock graph and SQLite persistence."""
    db_file = tmp_path / "replay_test.db"
    await init_db(db_file)

    # Mock compiled graph to simulate fast deterministic returns
    mock_graph = AsyncMock()

    async def mock_ainvoke(state: PulseGraphState) -> dict:
        return {
            "point_context": state.point_context,
            "leverage_result": None,
            "pressure_result": None,
            "exploit_result": None,
            "tactical_output": None,
            "decision_log": [
                {"node": "StateMonitorNode", "fired": True, "reason": "Test state monitor"},
            ],
        }

    mock_graph.ainvoke.side_effect = mock_ainvoke

    events: list[StreamPointEvent] = []
    async for event in generate_point_events(
        match_id="test_replay_match_001",
        speed_multiplier=0.0,  # Instant replay (no delay)
        graph=mock_graph,
        parquet_path=sample_parquet_file,
        db_path=db_file,
    ):
        events.append(event)

    # Assert exact point count (3 points -> 3 events)
    assert len(events) == 3
    for idx, ev in enumerate(events):
        assert ev.event_type == "point"
        assert ev.match_id == "test_replay_match_001"
        assert ev.point_index == idx
        assert isinstance(ev.point_context, PointContext)
        assert len(ev.decision_log) == 1

    # Verify persistence layer recorded all 3 points
    persisted_logs = await get_decision_logs("test_replay_match_001", db_path=db_file)
    assert len(persisted_logs) == 3


@pytest.mark.asyncio
async def test_generate_point_events_forced_mid_stream_failure(
    sample_parquet_file: Path,
    tmp_path: Path,
) -> None:
    """Verify fail-loud behavior: error event emitted and stream terminated on exception (D-13)."""
    db_file = tmp_path / "failure_test.db"
    await init_db(db_file)

    mock_graph = AsyncMock()
    call_count = 0

    async def mock_ainvoke_with_error(state: PulseGraphState) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated solver divergence error at point 1")
        return {
            "point_context": state.point_context,
            "decision_log": [],
        }

    mock_graph.ainvoke.side_effect = mock_ainvoke_with_error

    events: list[StreamPointEvent] = []
    async for event in generate_point_events(
        match_id="test_replay_match_001",
        speed_multiplier=0.0,
        graph=mock_graph,
        parquet_path=sample_parquet_file,
        db_path=db_file,
    ):
        events.append(event)

    # Point 0 succeeded, Point 1 threw exception -> total 2 events yielded (1 point, 1 error)
    assert len(events) == 2
    assert events[0].event_type == "point"
    assert events[0].point_index == 0

    assert events[1].event_type == "error"
    assert events[1].point_index == 1
    assert "Simulated solver divergence error" in str(events[1].error_message)


@pytest.mark.asyncio
async def test_generate_point_events_missing_match_error(
    sample_parquet_file: Path,
    tmp_path: Path,
) -> None:
    """Verify error event emitted when requesting an unknown match ID."""
    db_file = tmp_path / "missing_test.db"
    await init_db(db_file)

    events: list[StreamPointEvent] = []
    async for event in generate_point_events(
        match_id="non_existent_match",
        speed_multiplier=0.0,
        parquet_path=sample_parquet_file,
        db_path=db_file,
    ):
        events.append(event)

    assert len(events) == 1
    assert events[0].event_type == "error"
    assert "not found in points dataset" in str(events[0].error_message)


def test_run_cli_list_matches(sample_parquet_file: Path, monkeypatch, capsys) -> None:
    """Verify run_cli --list-matches prints available matches."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: sample_parquet_file,
    )
    monkeypatch.setattr("sys.argv", ["simulator.replay", "--list-matches"])

    run_cli()
    captured = capsys.readouterr()
    assert "Available matches (1):" in captured.out
    assert "test_replay_match_001" in captured.out


def test_run_cli_replay_match(sample_parquet_file: Path, monkeypatch, capsys) -> None:
    """Verify run_cli replaying a match outputs JSON event payloads."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: sample_parquet_file,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "simulator.replay",
            "--match-id",
            "test_replay_match_001",
            "--speed-multiplier",
            "0",
        ],
    )

    run_cli()
    captured = capsys.readouterr()
    assert "test_replay_match_001" in captured.out
    assert '"point_index": 0' in captured.out
    assert '"point_index": 1' in captured.out
    assert '"point_index": 2' in captured.out


def test_run_cli_missing_match_id(monkeypatch) -> None:
    """Verify run_cli exits with error code when --match-id is omitted."""
    monkeypatch.setattr("sys.argv", ["simulator.replay"])

    with pytest.raises(SystemExit) as exc_info:
        run_cli()
    assert exc_info.value.code == 1
