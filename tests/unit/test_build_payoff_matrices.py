"""Unit tests for PayoffMatrix data layer and construction logic (Stage 2 / Gate 2)."""

import pandas as pd
import pytest

from scripts.build_payoff_matrices import (
    build_payoff_matrix_for_stratum,
    fit_beta_prior_mom,
)
from src.config.loader import load_params
from src.core.game_theory import PayoffMatrix


@pytest.fixture
def sample_stratum_df_sufficient() -> pd.DataFrame:
    """Provide a synthetic DataFrame with sufficient charted points for 3x2 matrix."""
    rows = []
    # 40 wide points (24 server wins, 16 returner wins)
    for _ in range(24):
        rows.append({
            "serve_direction": "wide",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(16):
        rows.append({
            "serve_direction": "wide",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })
    # 60 body points (>= 50 threshold for 3x2)
    for _ in range(35):
        rows.append({
            "serve_direction": "body",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(25):
        rows.append({
            "serve_direction": "body",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })
    # 40 T points
    for _ in range(26):
        rows.append({
            "serve_direction": "T",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(14):
        rows.append({
            "serve_direction": "T",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })

    return pd.DataFrame(rows)


@pytest.fixture
def sample_stratum_df_sparse_body() -> pd.DataFrame:
    """Provide a synthetic DataFrame with sparse body points resulting in 2x2 matrix."""
    rows = []
    # 30 wide points
    for _ in range(20):
        rows.append({
            "serve_direction": "wide",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(10):
        rows.append({
            "serve_direction": "wide",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })
    # 5 body points (< 50 threshold)
    for _ in range(3):
        rows.append({
            "serve_direction": "body",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(2):
        rows.append({
            "serve_direction": "body",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })
    # 30 T points
    for _ in range(18):
        rows.append({
            "serve_direction": "T",
            "point_winner": "server",
            "surface": "HARD",
            "serve_number": 1,
        })
    for _ in range(12):
        rows.append({
            "serve_direction": "T",
            "point_winner": "returner",
            "surface": "HARD",
            "serve_number": 1,
        })

    return pd.DataFrame(rows)


def test_build_payoff_matrix_3x2_sufficient(sample_stratum_df_sufficient: pd.DataFrame):
    """Verify matrix construction includes Body row when body count >= 50 threshold."""
    params = load_params()
    matrix = build_payoff_matrix_for_stratum(
        df_stratum=sample_stratum_df_sufficient,
        returner_id="sinner_j",
        server_id="alcaraz_c",
        surface="HARD",
        serve_number=1,
        params=params,
        prior_alpha=2.0,
        prior_beta=2.0,
    )
    assert matrix is not None
    assert isinstance(matrix, PayoffMatrix)
    assert matrix.row_labels == ["Wide", "Body", "T"]
    assert matrix.col_labels == ["Cover Wide", "Cover T"]
    assert len(matrix.matrix) == 3
    assert len(matrix.matrix[0]) == 2
    assert matrix.n_opp_total == 140


def test_build_payoff_matrix_2x2_sparse_body(sample_stratum_df_sparse_body: pd.DataFrame):
    """Verify matrix construction collapses to 2x2 when body count < 50 threshold."""
    params = load_params()
    matrix = build_payoff_matrix_for_stratum(
        df_stratum=sample_stratum_df_sparse_body,
        returner_id="medvedev_d",
        server_id="alcaraz_c",
        surface="HARD",
        serve_number=1,
        params=params,
        prior_alpha=2.0,
        prior_beta=2.0,
    )
    assert matrix is not None
    assert isinstance(matrix, PayoffMatrix)
    assert matrix.row_labels == ["Wide", "T"]
    assert matrix.col_labels == ["Cover Wide", "Cover T"]
    assert len(matrix.matrix) == 2
    assert len(matrix.matrix[0]) == 2


def test_build_payoff_matrix_empty_stratum_returns_none():
    """Verify empty stratum returns None as explicit insufficient-data marker."""
    params = load_params()
    empty_df = pd.DataFrame({
        "serve_direction": [],
        "point_winner": [],
        "surface": [],
        "serve_number": [],
    })
    matrix = build_payoff_matrix_for_stratum(
        df_stratum=empty_df,
        returner_id="unknown_player",
        server_id="alcaraz_c",
        surface="CLAY",
        serve_number=2,
        params=params,
        prior_alpha=2.0,
        prior_beta=2.0,
    )
    assert matrix is None


def test_fit_beta_prior_mom_calculation():
    """Verify Method-of-Moments Beta prior fitting and fallback handling."""
    # Synthetic win rates around 0.65 with known variance
    rates = [0.60, 0.65, 0.70, 0.62, 0.68, 0.64, 0.66, 0.63, 0.67, 0.65]
    alpha, beta = fit_beta_prior_mom(rates)
    assert alpha > 0.0
    assert beta > 0.0
    # Mean of Beta distribution alpha / (alpha + beta) should be close to 0.65
    implied_mean = alpha / (alpha + beta)
    assert abs(implied_mean - 0.65) < 0.05

    # Small list (< 10 items) returns fallback priors
    fallback_alpha, fallback_beta = fit_beta_prior_mom(
        [0.6, 0.7], fallback_alpha=3.0, fallback_beta=3.0
    )
    assert fallback_alpha == 3.0
    assert fallback_beta == 3.0
