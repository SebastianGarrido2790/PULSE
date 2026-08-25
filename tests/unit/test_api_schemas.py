"""Unit tests for src/api/schemas.py (API request, response, and streaming contracts)."""

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    GameTheoryExploitAudit,
    HealthCheckResponse,
    MatchMetadataResponse,
    MatchReplayRequest,
    MatchReportResponse,
    MatchSummaryStats,
    PivotalPointEntry,
    PlayerPressureMetrics,
    ServeDirectionBreakdown,
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


def test_pivotal_point_entry_validation() -> None:
    """Verify PivotalPointEntry validation and probability bounds."""
    pt = PivotalPointEntry(
        point_index=15,
        set_num=2,
        game_score="4-3",
        point_score="30-40",
        server_id="Carlos Alcaraz",
        returner_id="Novak Djokovic",
        point_winner_id="Novak Djokovic",
        point_winner_role="returner",
        delta_leverage=0.28,
        leverage_low=0.22,
        leverage_high=0.35,
        p_hat_server=0.64,
        match_win_prob_before=0.55,
        is_break_point=True,
        impact_narrative="Break Point converted by Novak Djokovic.",
    )

    assert pt.point_index == 15
    assert pt.is_break_point is True
    assert pt.delta_leverage == 0.28

    with pytest.raises(ValidationError):
        PivotalPointEntry(
            point_index=-1,
            set_num=0,
            game_score="0-0",
            point_score="0-0",
            server_id="P1",
            returner_id="P2",
            point_winner_id="P1",
            point_winner_role="server",
            delta_leverage=1.5,
            leverage_low=0.0,
            leverage_high=1.0,
            p_hat_server=0.5,
            match_win_prob_before=0.5,
            impact_narrative="invalid",
        )


def test_player_pressure_metrics_validation() -> None:
    """Verify PlayerPressureMetrics schema constraints."""
    press = PlayerPressureMetrics(
        player_id="Carlos Alcaraz",
        total_points=120,
        routine_points_count=90,
        routine_win_rate=0.68,
        elevated_points_count=20,
        elevated_win_rate=0.70,
        critical_points_count=10,
        critical_win_rate=0.80,
        pressure_shift_delta_p=0.12,
        resilience_assessment="Elevated / Clutch (+Win Rate under Pressure)",
    )

    assert press.player_id == "Carlos Alcaraz"
    assert press.pressure_shift_delta_p == 0.12


def test_match_report_response_serialization() -> None:
    """Verify MatchReportResponse full model serialization and roundtrip."""
    summary = MatchSummaryStats(
        match_id="test_001",
        surface="HARD",
        player_1="Alex De Minaur",
        player_2="Alexander Zverev",
        winner="Alex De Minaur",
        final_score="6-4, 6-3",
        total_points=120,
        p1_points_won=70,
        p2_points_won=50,
        p1_win_pct=0.583,
        p2_win_pct=0.417,
        mean_delta_leverage=0.038,
        max_delta_leverage=0.34,
        high_leverage_point_count=14,
        break_point_count=8,
        break_points_converted=4,
    )

    pt = PivotalPointEntry(
        point_index=45,
        set_num=1,
        game_score="5-4",
        point_score="40-30",
        server_id="Alex De Minaur",
        returner_id="Alexander Zverev",
        point_winner_id="Alex De Minaur",
        point_winner_role="server",
        delta_leverage=0.34,
        leverage_low=0.28,
        leverage_high=0.40,
        p_hat_server=0.70,
        match_win_prob_before=0.85,
        is_set_point=True,
        impact_narrative="Set Point converted.",
    )

    press = PlayerPressureMetrics(
        player_id="Alex De Minaur",
        total_points=120,
        routine_points_count=95,
        routine_win_rate=0.57,
        elevated_points_count=15,
        elevated_win_rate=0.60,
        critical_points_count=10,
        critical_win_rate=0.70,
        pressure_shift_delta_p=0.13,
        resilience_assessment="Elevated / Clutch",
    )

    gt = GameTheoryExploitAudit(
        server_id="Alex De Minaur",
        returner_id="Alexander Zverev",
        court_side="all",
        realized_serve_mix=ServeDirectionBreakdown(
            wide_count=20,
            body_count=5,
            t_count=25,
            total_charted=50,
            wide_pct=0.40,
            body_pct=0.10,
            t_pct=0.50,
        ),
        nash_serve_mix={"wide": 0.50, "t": 0.50},
        returner_bias={"wide": 0.50, "t": 0.50},
        exploit_gain_delta_ev=0.0,
        sample_size=50,
        sufficiency_gated=False,
    )

    response = MatchReportResponse(
        summary=summary,
        pivotal_points=[pt],
        pressure_resilience=[press],
        game_theory_audit=[gt],
        executive_debrief="Solid tactical execution in decisive moments.",
        markdown_report="# Full Report",
    )

    json_str = response.model_dump_json()
    reloaded = MatchReportResponse.model_validate_json(json_str)

    assert reloaded.summary.match_id == "test_001"
    assert len(reloaded.pivotal_points) == 1
    assert reloaded.pivotal_points[0].is_set_point is True
    assert reloaded.markdown_report == "# Full Report"

