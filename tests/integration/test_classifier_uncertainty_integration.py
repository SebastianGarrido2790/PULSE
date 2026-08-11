"""Integration smoke test for Phase 3 Tier 1 ML Layer.

Verifies end-to-end data flow through the full integration chain:
1. Point dataset aggregation -> StratumTable build
2. Hierarchical 4-tier resolution -> StratumLookupResult (p_hat, sample_size N, wins k)
3. Wilson interval calculation & Markov leverage propagation -> LeverageBandResult
4. Empirical-Bayes Pressure Deviation model fitting -> PressureDeviationResult

Authority: Phase 3 Decision D-8
"""

import pandas as pd
import pytest

from src.config.loader import load_params
from src.core.leverage_uncertainty import LeverageBandResult, propagate_leverage_uncertainty
from src.core.markov_solver import MatchState
from src.models.point_win_classifier import (
    FallbackTier,
    build_stratum_table,
    resolve_point_win_probability,
)
from src.models.pressure_deviation import (
    PressureModelArtifact,
    fit_pressure_model,
)
from src.schemas.point_record import Surface


@pytest.fixture
def synthetic_match_dataset() -> pd.DataFrame:
    """Construct synthetic points dataset with known server, surface, serve_number, and scores."""
    records = []

    # Server 1 (Federer): 40 points on HARD 1st serve (30 wins -> p_hat = 0.75, N=40 >= 10)
    for i in range(40):
        records.append(
            {
                "server": "player_fed",
                "returner": "player_nad",
                "server_is_p1": True,
                "surface": "HARD",
                "serve_number": 1,
                "p1_score": "30",
                "p2_score": "40",
                "p1_games": 4,
                "p2_games": 4,
                "p1_sets": 1,
                "p2_sets": 1,
                "point_winner": "server" if i < 30 else "returner",
                "leverage": 0.18,  # Elevated bucket 1
            }
        )

    # Server 1 (Federer): 5 points on CLAY 1st serve (3 wins -> Tier 0 N=5 < 10,
    # Tier 1 overall N=45 >= 20)
    for i in range(5):
        records.append(
            {
                "server": "player_fed",
                "returner": "player_nad",
                "server_is_p1": True,
                "surface": "CLAY",
                "serve_number": 1,
                "p1_score": "40",
                "p2_score": "AD",
                "p1_games": 5,
                "p2_games": 6,
                "p1_sets": 0,
                "p2_sets": 1,
                "point_winner": "server" if i < 3 else "returner",
                "leverage": 0.32,  # Critical bucket 2
            }
        )

    return pd.DataFrame(records)


def test_classifier_to_leverage_uncertainty_integration(
    synthetic_match_dataset: pd.DataFrame,
) -> None:
    """Verify integration flow from StratumTable resolution to Markov leverage band propagation."""
    params = load_params()

    # 1. Build StratumTable
    stratum_table = build_stratum_table(synthetic_match_dataset, default_p=0.62)

    # 2. Resolve point-win probability for Federer on HARD 1st serve (Tier 0)
    lookup_res = resolve_point_win_probability(
        stratum_table=stratum_table,
        server_id="player_fed",
        surface=Surface.HARD,
        serve_number=1,
        params=params,
    )

    assert lookup_res.fallback_tier == FallbackTier.EXACT_STRATUM
    assert lookup_res.sample_size == 40
    assert lookup_res.wins == 30
    assert lookup_res.p_hat == pytest.approx(0.75)

    # 3. Construct MatchState at 30-40 (Break Point / High Leverage)
    state = MatchState(
        point_score_server=2,  # "30"
        point_score_returner=3,  # "40"
        game_score_server=4,
        game_score_returner=4,
        set_score_server=1,
        set_score_returner=1,
        server_id="player_fed",
        match_format="bo3",
    )

    # 4. Propagate Wilson uncertainty bounds through Markov solver
    band_res = propagate_leverage_uncertainty(
        state=state,
        wins=lookup_res.wins,
        sample_size=lookup_res.sample_size,
        confidence_level=params.uncertainty.confidence_level,
        min_observations=params.uncertainty.min_stratum_observations,
        default_p=params.solver.default_p_serve,
        fallback_margin=params.uncertainty.default_fallback_margin,
    )

    # 5. Assert valid LeverageBandResult
    assert isinstance(band_res, LeverageBandResult)
    assert band_res.is_sufficient_sample is True
    assert 0.0 <= band_res.leverage_point <= 1.0
    assert 0.0 <= band_res.leverage_low <= 1.0
    assert 0.0 <= band_res.leverage_high <= 1.0
    assert band_res.band_width >= 0.0
    assert band_res.leverage_low <= band_res.leverage_high


def test_pressure_model_integration_with_stratum_table(
    synthetic_match_dataset: pd.DataFrame,
) -> None:
    """Verify integration of Pressure Deviation Model with StratumTable baselines."""
    params = load_params()

    # 1. Build StratumTable
    stratum_table = build_stratum_table(synthetic_match_dataset)

    # 2. Fit Pressure Model
    pressure_artifact = fit_pressure_model(synthetic_match_dataset, stratum_table, params)

    assert isinstance(pressure_artifact, PressureModelArtifact)

    # 3. Query Federer in Elevated leverage bucket 1
    fed_b1_key = "player_fed|1"
    assert fed_b1_key in pressure_artifact.results

    fed_res = pressure_artifact.results[fed_b1_key]
    assert fed_res.server_id == "player_fed"
    assert fed_res.leverage_bucket == 1
    assert fed_res.n_pressure == 40
    assert fed_res.k_pressure == 30

    # Baseline p should match Federer's Tier 1 1st serve rate (33/45 = 0.7333)
    assert fed_res.baseline_p == pytest.approx(33.0 / 45.0)

    # Posterior shrunk rate should be close to 0.75
    assert 0.50 <= fed_res.shrunk_rate <= 0.90
    assert fed_res.deviation_low_90 < fed_res.pressure_deviation < fed_res.deviation_high_90
