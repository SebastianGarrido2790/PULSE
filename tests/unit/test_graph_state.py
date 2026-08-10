"""PULSE — Unit Tests for Graph State Schema (src/graph/state.py).

Verifies validation, field constraints, default values, and serialization of PulseGraphState.

Authority: Phase 4 Decisions D-2, D-2a, D-2b.
"""

import pytest
from pydantic import ValidationError

from src.graph.state import (
    DecisionLogEntry,
    ExploitResult,
    LeverageResult,
    PointContext,
    PulseGraphState,
    TacticalOutputResult,
)
from src.models.pressure_deviation import PressureDeviationResult


def test_pulse_graph_state_construction() -> None:
    """Verify clean instantiation of PulseGraphState with required and optional fields."""
    context = PointContext(
        match_id="match_001",
        point_index=12,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.18,
        delta_leverage_low=0.12,
        delta_leverage_high=0.24,
        p_hat=0.65,
        sample_size=45,
        fallback_tier=0,
    )

    state = PulseGraphState(
        point_context=context,
        leverage_result=leverage,
    )

    assert state.point_context.match_id == "match_001"
    assert state.leverage_result is not None
    assert state.leverage_result.delta_leverage == 0.18
    assert state.pressure_result is None
    assert state.exploit_result is None
    assert state.tactical_output is None
    assert state.decision_log == []


def test_pulse_graph_state_full_payload() -> None:
    """Verify instantiation with all optional triggered node payloads populated."""
    context = PointContext(
        match_id="match_002",
        point_index=45,
        server_id="djokovic_n",
        returner_id="medvedev_d",
        surface="CLAY",
        serve_number=2,
    )
    leverage = LeverageResult(
        delta_leverage=0.28,
        delta_leverage_low=0.22,
        delta_leverage_high=0.35,
        p_hat=0.52,
        sample_size=35,
        fallback_tier=1,
    )
    pressure = PressureDeviationResult(
        server_id="djokovic_n",
        leverage_bucket=2,
        k_pressure=18,
        n_pressure=30,
        baseline_p=0.55,
        shrunk_rate=0.58,
        pressure_deviation=0.03,
        deviation_low_90=-0.02,
        deviation_high_90=0.08,
        alpha_prior=2.0,
        beta_prior=2.0,
        is_prior_estimated=True,
        is_sufficient_sample=True,
    )
    exploit = ExploitResult(
        status="module_not_yet_implemented",
        opponent_id="medvedev_d",
        sample_size=42,
        is_sufficient_sample=True,
        recommendation=None,
    )
    tactical = TacticalOutputResult(
        narrative="High leverage point on 2nd serve. Server shows +3% pressure deviation.",
        escalated=True,
        raw_payload={"delta_leverage": 0.28, "pressure_deviation": 0.03},
        is_llm_fallback=False,
    )
    log_entry = DecisionLogEntry(
        node="PressureDiagnosticNode",
        fired=True,
        reason="Leverage lower bound 0.22 >= threshold 0.10",
    )

    state = PulseGraphState(
        point_context=context,
        leverage_result=leverage,
        pressure_result=pressure,
        exploit_result=exploit,
        tactical_output=tactical,
        decision_log=[log_entry],
    )

    assert state.pressure_result is not None
    assert state.pressure_result.pressure_deviation == 0.03
    assert state.exploit_result is not None
    assert state.exploit_result.status == "module_not_yet_implemented"
    assert state.tactical_output is not None
    assert state.tactical_output.escalated is True
    assert len(state.decision_log) == 1
    assert state.decision_log[0].fired is True


def test_pulse_graph_state_invalid_bounds() -> None:
    """Verify validation errors when out-of-range values are passed to sub-models."""
    with pytest.raises(ValidationError):
        PointContext(
            match_id="m1",
            point_index=0,
            server_id="p1",
            returner_id="p2",
            surface="HARD",
            serve_number=3,  # Invalid serve_number (must be 1 or 2)
        )

    with pytest.raises(ValidationError):
        LeverageResult(
            delta_leverage=1.5,  # Invalid leverage > 1.0
            delta_leverage_low=0.1,
            delta_leverage_high=0.2,
            p_hat=0.5,
            sample_size=10,
            fallback_tier=0,
        )
