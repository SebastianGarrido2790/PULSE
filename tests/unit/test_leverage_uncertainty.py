"""Unit tests for src/core/leverage_uncertainty.py (Wilson interval & leverage band propagation)."""

import pytest

from src.core.leverage_uncertainty import (
    compute_wilson_interval,
    propagate_leverage_uncertainty,
)
from src.core.markov_solver import MatchState


def test_compute_wilson_interval_sufficient_sample() -> None:
    """Verify Wilson interval computation for a sufficient sample (N=100, k=65)."""
    interval = compute_wilson_interval(wins=65, sample_size=100, confidence_level=0.95)

    assert interval.is_sufficient_sample is True
    assert interval.p_hat == 0.65
    assert 0.55 < interval.p_low < 0.65
    assert 0.65 < interval.p_high < 0.75


def test_compute_wilson_interval_insufficient_sample() -> None:
    """Verify fallback behavior for an insufficient sample size (N=5 < 10)."""
    interval = compute_wilson_interval(wins=3, sample_size=5, min_observations=10, default_p=0.62)

    assert interval.is_sufficient_sample is False
    assert interval.p_hat == 0.62
    assert interval.p_low < 0.62 < interval.p_high


def test_propagate_leverage_uncertainty() -> None:
    """Verify leverage confidence band propagation through Markov solver."""
    state = MatchState(
        point_score_server=2,  # "30"
        point_score_returner=2,  # "30"
        game_score_server=4,
        game_score_returner=4,
        set_score_server=0,
        set_score_returner=0,
        server_id="server_1",
        match_format="bo3",
    )

    result = propagate_leverage_uncertainty(
        state=state,
        wins=60,
        sample_size=100,
        confidence_level=0.95,
        min_observations=10,
    )

    assert result.is_sufficient_sample is True
    assert result.p_hat == 0.60
    assert 0.0 <= result.leverage_low <= result.leverage_high <= 1.0
    assert result.band_width == pytest.approx(result.leverage_high - result.leverage_low, abs=1e-9)
    assert result.solver_result_point.leverage == result.leverage_point
