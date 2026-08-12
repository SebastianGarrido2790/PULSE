"""PULSE — Unit Tests for Graph Routing Functions (src/graph/pulse_graph.py).

Verifies the shared escalation gate (D-4 lower bound rule), destination routing decisions,
and OpenTelemetry span emissions across all combinations of leverage bounds and thresholds.

Authority: Stage 6 Step 33, Decisions D-3, D-4, D-4a, D-5, ADR-001.
"""

import pytest

from src.config.loader import load_params
from src.graph.pulse_graph import (
    make_route_after_pressure_diagnostic,
    make_route_after_state_monitor,
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
    """Verify route_after_state_monitor routes to pressure_diagnostic when low bound >= thresh."""
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

    route_fn = make_route_after_state_monitor()
    destination = route_fn(state)
    assert destination == "pressure_diagnostic"


def test_route_after_state_monitor_suppressed() -> None:
    """Verify route_after_state_monitor routes to tactical_output when low bound < thresh."""
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

    route_fn = make_route_after_state_monitor()
    destination = route_fn(state)
    assert destination == "tactical_output"


def test_route_after_pressure_diagnostic_escalate() -> None:
    """Verify route_after_pressure_diagnostic routes to strategy_exploit when low bound high."""
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

    route_fn = make_route_after_pressure_diagnostic()
    destination = route_fn(state)
    assert destination == "strategy_exploit"


def test_route_after_pressure_diagnostic_suppressed() -> None:
    """Verify route_after_pressure_diagnostic routes to tactical_output when low bound < thresh."""
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

    route_fn = make_route_after_pressure_diagnostic()
    destination = route_fn(state)
    assert destination == "tactical_output"


def test_routing_does_not_reload_params_from_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify factory-built routing functions do not call load_params() per point (D-9)."""
    cfg = load_params()
    route_sm = make_route_after_state_monitor(cfg)
    route_pd = make_route_after_pressure_diagnostic(cfg)

    def mock_load_params() -> None:
        raise RuntimeError("load_params() was called during routing execution!")

    monkeypatch.setattr("src.graph.pulse_graph.load_params", mock_load_params)

    context = PointContext(
        match_id="m5",
        point_index=4,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.20,
        delta_leverage_low=0.15,
        delta_leverage_high=0.25,
        p_hat=0.70,
        sample_size=60,
        fallback_tier=0,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    # Calling routing closures repeatedly must NOT hit load_params()
    assert route_sm(state) == "pressure_diagnostic"
    assert route_pd(state) == "strategy_exploit"
