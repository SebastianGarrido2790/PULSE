"""PULSE — Unit Tests for PressureDiagnosticNode (src/graph/pressure_diagnostic.py).

Verifies node execution in isolation with fixture PressureModelArtifact containers for both
found player-bucket records and sparse-player miss cases.

Authority: Stage 4 Step 23, FR-4, Decisions D-2b, D-6.
"""

import pytest

from src.graph.pressure_diagnostic import make_pressure_diagnostic_node
from src.graph.state import LeverageResult, PointContext, PulseGraphState
from src.models.pressure_deviation import (
    PressureBucketPrior,
    PressureDeviationResult,
    PressureModelArtifact,
)
from src.utils.exceptions import ModelInferenceError


@pytest.fixture
def mock_pressure_artifact() -> PressureModelArtifact:
    """Provide a fixture PressureModelArtifact container."""
    priors = {
        0: PressureBucketPrior(
            leverage_bucket=0, alpha_0=2.0, beta_0=2.0, is_prior_estimated=False, player_count=10
        ),
        1: PressureBucketPrior(
            leverage_bucket=1, alpha_0=2.0, beta_0=2.0, is_prior_estimated=False, player_count=10
        ),
        2: PressureBucketPrior(
            leverage_bucket=2, alpha_0=2.0, beta_0=2.0, is_prior_estimated=False, player_count=10
        ),
    }
    dev_res = PressureDeviationResult(
        server_id="alcaraz_c",
        leverage_bucket=1,  # Elevated bucket [0.10, 0.25)
        k_pressure=15,
        n_pressure=20,
        baseline_p=0.70,
        shrunk_rate=0.7083,
        pressure_deviation=0.0083,
        deviation_low_90=-0.05,
        deviation_high_90=0.07,
        alpha_prior=2.0,
        beta_prior=2.0,
        is_prior_estimated=True,
        is_sufficient_sample=True,
    )
    results = {"alcaraz_c|1": dev_res}
    return PressureModelArtifact(priors=priors, results=results)


@pytest.mark.asyncio
async def test_pressure_diagnostic_node_found(
    mock_pressure_artifact: PressureModelArtifact,
) -> None:
    """Verify PressureDiagnosticNode populates pressure_result when player key exists."""
    node_fn = make_pressure_diagnostic_node(mock_pressure_artifact)

    context = PointContext(
        match_id="match_test_003",
        point_index=10,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.18,  # Maps to bucket 1 [0.10, 0.25)
        delta_leverage_low=0.12,
        delta_leverage_high=0.24,
        p_hat=0.70,
        sample_size=50,
        fallback_tier=0,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    update = await node_fn(state)

    assert "pressure_result" in update
    res = update["pressure_result"]
    assert res is not None
    assert res.server_id == "alcaraz_c"
    assert res.leverage_bucket == 1
    assert res.pressure_deviation == pytest.approx(0.0083, abs=1e-4)


@pytest.mark.asyncio
async def test_pressure_diagnostic_node_miss(
    mock_pressure_artifact: PressureModelArtifact,
) -> None:
    """Verify PressureDiagnosticNode returns None on sparse-player miss without error."""
    node_fn = make_pressure_diagnostic_node(mock_pressure_artifact)

    context = PointContext(
        match_id="match_test_004",
        point_index=2,
        server_id="sparse_player_xyz",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    leverage = LeverageResult(
        delta_leverage=0.18,
        delta_leverage_low=0.12,
        delta_leverage_high=0.24,
        p_hat=0.62,
        sample_size=5,
        fallback_tier=3,
    )
    state = PulseGraphState(point_context=context, leverage_result=leverage)

    update = await node_fn(state)

    assert "pressure_result" in update
    assert update["pressure_result"] is None


@pytest.mark.asyncio
async def test_pressure_diagnostic_missing_leverage_result(
    mock_pressure_artifact: PressureModelArtifact,
) -> None:
    """Verify ModelInferenceError is raised if leverage_result is missing from graph state."""
    node_fn = make_pressure_diagnostic_node(mock_pressure_artifact)

    context = PointContext(
        match_id="match_test_005",
        point_index=0,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    state = PulseGraphState(point_context=context, leverage_result=None)

    with pytest.raises(ModelInferenceError, match="executed without leverage_result"):
        await node_fn(state)
