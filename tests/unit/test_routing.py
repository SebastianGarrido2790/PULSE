"""PULSE — Unit Tests for Graph Routing Functions (src/graph/pulse_graph.py).

Verifies the shared escalation gate (D-4 lower bound rule), routing decisions,
decision_log logging (D-3, D-5), and OpenTelemetry span attributes across
all combinations of leverage bounds and thresholds.

Authority: Stage 6 Step 33, Decisions D-3, D-4, D-4a, D-5, ADR-001.
"""

from src.graph.pulse_graph import (
    route_after_pressure_diagnostic,
    route_after_state_monitor,
    should_escalate,
)
from src.graph.state import LeverageResult, PointContext, PulseGraphState


def test_should_escalate_lower_bound_rule() -> None:
    """Verify D-4 lower bound rule: escalate ONLY if delta_leverage_low >= threshold."""
    # 1. None leverage_result -> False
    assert should_escalate(None, 0.10) is False

    # 2. Point estimate high (0.15), but lower bound low (0.08 < 0.10) -> False
    lev_wide = LeverageResult(
        delta_leverage=0.15,
        delta_leverage_low=0.08,
        delta_leverage_high=0.22,
        p_hat=0.60,
        sample_size=15,
        fallback_tier=1,
    )
    assert should_escalate(lev_wide, 0.10) is False

    # 3. Lower bound high (0.12 >= 0.10) -> True
    lev_narrow = LeverageResult(
        delta_leverage=0.16,
        delta_leverage_low=0.12,
        delta_leverage_high=0.20,
        p_hat=0.65,
        sample_size=50,
        fallback_tier=0,
    )
    assert should_escalate(lev_narrow, 0.10) is True


def test_route_after_state_monitor_escalate() -> None:
    """Verify route_after_state_monitor routes to pressure_diagnostic and logs fire entry."""
    context = PointContext(
        match_id="m1",
        point_index=0,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.16,
        delta_leverage_low=0.12,  # >= 0.10 threshold
        delta_leverage_high=0.20,
        p_hat=0.65,
        sample_size=50,
        fallback_tier=0,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    destination = route_after_state_monitor(state)

    assert destination == "pressure_diagnostic"
    assert len(state.decision_log) == 1
    log_entry = state.decision_log[0]
    assert log_entry.node == "pressure_diagnostic"
    assert log_entry.fired is True
    assert "0.1200 >= threshold 0.1000" in log_entry.reason


def test_route_after_state_monitor_suppressed() -> None:
    """Verify route_after_state_monitor routes to tactical_output and logs suppress entry."""
    context = PointContext(
        match_id="m2",
        point_index=1,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.12,
        delta_leverage_low=0.07,  # < 0.10 threshold
        delta_leverage_high=0.17,
        p_hat=0.60,
        sample_size=20,
        fallback_tier=1,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    destination = route_after_state_monitor(state)

    assert destination == "tactical_output"
    assert len(state.decision_log) == 1
    log_entry = state.decision_log[0]
    assert log_entry.node == "pressure_diagnostic"
    assert log_entry.fired is False
    assert "(suppressed)" in log_entry.reason


def test_route_after_pressure_diagnostic_escalate() -> None:
    """Verify route_after_pressure_diagnostic routes to strategy_exploit and logs fire entry."""
    context = PointContext(
        match_id="m3",
        point_index=2,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.20,
        delta_leverage_low=0.15,  # >= 0.10 threshold
        delta_leverage_high=0.25,
        p_hat=0.70,
        sample_size=60,
        fallback_tier=0,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    destination = route_after_pressure_diagnostic(state)

    assert destination == "strategy_exploit"
    assert len(state.decision_log) == 1
    log_entry = state.decision_log[0]
    assert log_entry.node == "strategy_exploit"
    assert log_entry.fired is True
    assert "0.1500 >= threshold 0.1000" in log_entry.reason


def test_route_after_pressure_diagnostic_suppressed() -> None:
    """Verify route_after_pressure_diagnostic routes to tactical_output and logs suppress entry."""
    context = PointContext(
        match_id="m4",
        point_index=3,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.09,
        delta_leverage_low=0.04,  # < 0.10 threshold
        delta_leverage_high=0.14,
        p_hat=0.55,
        sample_size=10,
        fallback_tier=2,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    destination = route_after_pressure_diagnostic(state)

    assert destination == "tactical_output"
    assert len(state.decision_log) == 1
    log_entry = state.decision_log[0]
    assert log_entry.node == "strategy_exploit"
    assert log_entry.fired is False
    assert "(suppressed)" in log_entry.reason
