"""Unit tests for src/api/schemas.py (API request, response, and streaming contracts)."""

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    HealthCheckResponse,
    MatchMetadataResponse,
    MatchReplayRequest,
    StreamPointEvent,
)
from src.graph.state import (
    DecisionLogEntry,
    LeverageResult,
    PointContext,
    TacticalOutputResult,
)


@pytest.fixture
def sample_point_context() -> PointContext:
    """Fixture providing a valid PointContext instance."""
    return PointContext(
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_index=0,
        server_id="Carlos Alcaraz",
        returner_id="Novak Djokovic",
        surface="GRASS",
        serve_number=1,
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=0,
        set_score_returner=0,
        match_format="bo3",
    )


def test_stream_point_event_minimal(sample_point_context: PointContext) -> None:
    """Verify StreamPointEvent validation with minimal required attributes."""
    event = StreamPointEvent(
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_index=0,
        point_context=sample_point_context,
    )

    assert event.event_type == "point"
    assert event.match_id == "2023-wimbledon-f-alcaraz-djokovic"
    assert event.point_index == 0
    assert event.tactical_output is None
    assert event.leverage_result is None
    assert event.pressure_result is None
    assert event.exploit_result is None
    assert event.decision_log == []
    assert event.error_message is None


def test_stream_point_event_full(sample_point_context: PointContext) -> None:
    """Verify StreamPointEvent validation with full payload including tactical output."""
    leverage = LeverageResult(
        delta_leverage=0.14,
        delta_leverage_low=0.10,
        delta_leverage_high=0.18,
        p_hat=0.65,
        sample_size=45,
        fallback_tier=0,
    )
    tactical = TacticalOutputResult(
        narrative="Critical break point: returner shifts deep wide.",
        escalated=True,
        raw_payload={"delta_L": 0.14},
        is_llm_fallback=False,
    )
    decision = DecisionLogEntry(
        node="PressureDiagnosticNode",
        fired=True,
        reason="Leverage delta 0.14 >= 0.10 threshold",
    )

    event = StreamPointEvent(
        event_type="point",
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_index=42,
        point_context=sample_point_context,
        tactical_output=tactical,
        leverage_result=leverage,
        decision_log=[decision],
    )

    assert event.event_type == "point"
    assert event.point_index == 42
    assert event.tactical_output is not None
    assert event.tactical_output.escalated is True
    assert event.leverage_result is not None
    assert event.leverage_result.delta_leverage == 0.14
    assert len(event.decision_log) == 1
    assert event.decision_log[0].node == "PressureDiagnosticNode"


def test_stream_point_event_error_variant(sample_point_context: PointContext) -> None:
    """Verify StreamPointEvent when used for mid-stream error signaling."""
    event = StreamPointEvent(
        event_type="error",
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_index=5,
        point_context=sample_point_context,
        error_message="Markov solver convergence failure at point 5",
    )

    assert event.event_type == "error"
    assert event.error_message == "Markov solver convergence failure at point 5"


def test_match_replay_request_defaults_and_validation() -> None:
    """Verify MatchReplayRequest defaults and validation rules."""
    req_default = MatchReplayRequest()
    assert req_default.speed_multiplier == 1.0
    assert req_default.match_format == "bo3"

    req_custom = MatchReplayRequest(speed_multiplier=5.0, match_format="bo5")
    assert req_custom.speed_multiplier == 5.0
    assert req_custom.match_format == "bo5"

    with pytest.raises(ValidationError):
        MatchReplayRequest(speed_multiplier=-1.0)


def test_match_metadata_response() -> None:
    """Verify MatchMetadataResponse creation and field validation."""
    meta = MatchMetadataResponse(
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        total_points=240,
        server_p1="Carlos Alcaraz",
        returner_p2="Novak Djokovic",
        surface="GRASS",
        match_format="bo3",
    )

    assert meta.match_id == "2023-wimbledon-f-alcaraz-djokovic"
    assert meta.total_points == 240
    assert meta.surface == "GRASS"

    with pytest.raises(ValidationError):
        MatchMetadataResponse(
            match_id="test",
            total_points=-5,
            server_p1="P1",
            returner_p2="P2",
            surface="HARD",
        )


def test_health_check_response() -> None:
    """Verify HealthCheckResponse defaults and serialization."""
    health = HealthCheckResponse(
        status="healthy",
        graph_ready=True,
        version="0.1.0",
        artifacts_loaded=["stratum_table", "pressure_model", "payoff_matrix"],
    )

    assert health.status == "healthy"
    assert health.graph_ready is True
    assert len(health.artifacts_loaded) == 3
