"""PULSE — Unit Tests for TacticalOutputNode (src/graph/tactical_output.py).

Verifies signal payload assembly (FR-7), LLM narrative synthesis on escalated points,
deterministic fallback on LLM failure, and zero LLM calls on routine points (D-7).

Authority: Stage 7 Step 40, FR-7, Phase 4 Decision D-7, D-7a, D-2b.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.graph.state import (
    LeverageResult,
    PointContext,
    PulseGraphState,
)
from src.graph.tactical_output import make_tactical_output_node
from src.models.pressure_deviation import PressureDeviationResult


@pytest.fixture
def base_context() -> PointContext:
    """Provide a fixture PointContext."""
    return PointContext(
        match_id="match_test_008",
        point_index=20,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )


@pytest.fixture
def sample_leverage() -> LeverageResult:
    """Provide a fixture LeverageResult."""
    return LeverageResult(
        delta_leverage=0.18,
        delta_leverage_low=0.12,
        delta_leverage_high=0.24,
        p_hat=0.68,
        sample_size=40,
        fallback_tier=0,
    )


@pytest.fixture
def sample_pressure() -> PressureDeviationResult:
    """Provide a fixture PressureDeviationResult."""
    return PressureDeviationResult(
        server_id="alcaraz_c",
        leverage_bucket=1,
        k_pressure=15,
        n_pressure=25,
        baseline_p=0.68,
        shrunk_rate=0.60,
        pressure_deviation=-0.08,
        deviation_low_90=-0.14,
        deviation_high_90=-0.02,
        alpha_prior=2.0,
        beta_prior=2.0,
        is_prior_estimated=True,
        is_sufficient_sample=True,
    )


@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_tactical_output_escalated_success(
    mock_llm: AsyncMock,
    base_context: PointContext,
    sample_leverage: LeverageResult,
    sample_pressure: PressureDeviationResult,
) -> None:
    """Verify escalated point invokes LLM and populates narrative successfully."""
    mock_llm.return_value = "Alcaraz serve win rate drops by 8.0% under elevated leverage."
    node_fn = make_tactical_output_node()

    state = PulseGraphState(
        point_context=base_context,
        leverage_result=sample_leverage,
        pressure_result=sample_pressure,
    )

    update = await node_fn(state)

    assert mock_llm.call_count == 1
    res = update["tactical_output"]
    assert res.escalated is True
    assert res.is_llm_fallback is False
    assert res.narrative == "Alcaraz serve win rate drops by 8.0% under elevated leverage."
    assert "leverage_result" in res.raw_payload
    assert "pressure_result" in res.raw_payload


@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_tactical_output_escalated_llm_failure_fallback(
    mock_llm: AsyncMock,
    base_context: PointContext,
    sample_leverage: LeverageResult,
    sample_pressure: PressureDeviationResult,
) -> None:
    """Verify LLM failure falls back cleanly to structured-payload passthrough narrative."""
    mock_llm.return_value = None  # Simulates API error, missing key, or timeout
    node_fn = make_tactical_output_node()

    state = PulseGraphState(
        point_context=base_context,
        leverage_result=sample_leverage,
        pressure_result=sample_pressure,
    )

    update = await node_fn(state)

    assert mock_llm.call_count == 1
    res = update["tactical_output"]
    assert res.escalated is True
    assert res.is_llm_fallback is True
    assert "Escalated point" in res.narrative
    assert "leverage_result" in res.raw_payload


@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_tactical_output_routine_zero_llm_calls(
    mock_llm: AsyncMock,
    base_context: PointContext,
    sample_leverage: LeverageResult,
) -> None:
    """Verify routine non-escalated point makes ZERO LLM calls (cost story guard)."""
    node_fn = make_tactical_output_node()

    state = PulseGraphState(
        point_context=base_context,
        leverage_result=sample_leverage,
        pressure_result=None,
        exploit_result=None,
    )

    update = await node_fn(state)

    assert mock_llm.call_count == 0  # Crucial cost story assertion
    res = update["tactical_output"]
    assert res.escalated is False
    assert res.is_llm_fallback is False
    assert "Routine point" in res.narrative
    assert "leverage_result" in res.raw_payload
    assert "pressure_result" not in res.raw_payload
