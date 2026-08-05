"""Unit tests for src/models/pressure_deviation.py (Empirical-Bayes Shrinkage Estimator)."""

from pathlib import Path

import pandas as pd
import pytest

from src.config.loader import load_params
from src.models.point_win_classifier import build_stratum_table
from src.models.pressure_deviation import (
    PressureDeviationResult,
    PressureModelArtifact,
    assign_leverage_bucket,
    compute_player_pressure_deviation,
    fit_bucket_prior,
    fit_pressure_model,
    load_pressure_artifact,
    save_pressure_artifact,
)
from src.utils.exceptions import ModelInferenceError


def test_assign_leverage_bucket() -> None:
    """Verify assigning leverage values delta_L to discrete leverage buckets."""
    assert assign_leverage_bucket(0.02) == 0  # Routine
    assert assign_leverage_bucket(0.099) == 0
    assert assign_leverage_bucket(0.10) == 1  # Elevated
    assert assign_leverage_bucket(0.20) == 1
    assert assign_leverage_bucket(0.249) == 1
    assert assign_leverage_bucket(0.25) == 2  # Critical
    assert assign_leverage_bucket(0.85) == 2


def test_fit_bucket_prior_sufficient_players() -> None:
    """Verify Method of Moments prior fitting when player count >= min_players (15)."""
    # 20 players with rates centered around 0.65 with realistic variance
    rates = [0.60, 0.62, 0.65, 0.68, 0.70, 0.58, 0.64, 0.66, 0.61, 0.69] * 2
    params = load_params()

    alpha_0, beta_0, is_est = fit_bucket_prior(rates, params)

    assert is_est is True
    assert alpha_0 > 0.0
    assert beta_0 > 0.0
    # Prior mean alpha / (alpha + beta) should be close to sample mean ~0.643
    prior_mean = alpha_0 / (alpha_0 + beta_0)
    assert prior_mean == pytest.approx(sum(rates) / len(rates), abs=0.02)


def test_fit_bucket_prior_sparse_fallback() -> None:
    """Verify sparse bucket (M < 15 players) falls back to fixed config prior (2.0, 2.0)."""
    rates = [0.65, 0.70, 0.60]  # Only 3 players < 15
    params = load_params()

    alpha_0, beta_0, is_est = fit_bucket_prior(rates, params)

    assert is_est is False
    assert alpha_0 == params.models.pressure_prior_alpha  # 2.0
    assert beta_0 == params.models.pressure_prior_beta  # 2.0


def test_fit_bucket_prior_zero_variance_fallback() -> None:
    """Verify zero variance sample falls back to fixed config prior."""
    rates = [0.65] * 20  # Identical rates -> variance = 0
    params = load_params()

    alpha_0, beta_0, is_est = fit_bucket_prior(rates, params)

    assert is_est is False
    assert alpha_0 == 2.0
    assert beta_0 == 2.0


def test_compute_player_pressure_deviation_shrinkage_invariant() -> None:
    """Verify posterior update math, shrinkage-direction invariant, and credible bounds."""
    params = load_params()

    # Player with k=8, N=10 (raw rate 0.80), baseline=0.60,
    # prior Alpha=10, Beta=5 (prior mean=0.6667)
    res = compute_player_pressure_deviation(
        server_id="player_1",
        leverage_bucket=1,
        k_pressure=8,
        n_pressure=10,
        baseline_p=0.60,
        alpha_0=10.0,
        beta_0=5.0,
        is_prior_estimated=True,
        params=params,
    )

    assert isinstance(res, PressureDeviationResult)
    # alpha_post = 10 + 8 = 18; beta_post = 5 + (10 - 8) = 7
    # shrunk_rate = 18 / 25 = 0.72
    assert res.shrunk_rate == pytest.approx(18.0 / 25.0)
    assert res.pressure_deviation == pytest.approx((18.0 / 25.0) - 0.60)

    # Invariant: shrunk_rate 0.72 must lie between prior_mean 0.6667 and raw_rate 0.80
    assert 0.6667 <= res.shrunk_rate <= 0.80

    # 90% credible interval bounds must span around shrunk_rate - baseline_p
    assert res.deviation_low_90 < res.pressure_deviation < res.deviation_high_90
    assert res.is_sufficient_sample is True


def test_fit_pressure_model_end_to_end() -> None:
    """Verify fitting full pressure model on synthetic point records."""
    records = []
    # 30 points for player_1 across Routine (0.05), Elevated (0.15), and Critical (0.35)
    for i in range(30):
        records.append({
            "server": "player_1",
            "surface": "HARD",
            "serve_number": 1,
            "point_winner": "server" if i % 2 == 0 else "returner",
            "leverage": 0.05 if i < 10 else (0.15 if i < 20 else 0.35),
        })

    df = pd.DataFrame(records)
    stratum_table = build_stratum_table(df)

    artifact = fit_pressure_model(df, stratum_table)

    assert isinstance(artifact, PressureModelArtifact)
    assert len(artifact.priors) == 3
    assert "player_1|0" in artifact.results
    assert "player_1|1" in artifact.results
    assert "player_1|2" in artifact.results


def test_save_and_load_pressure_artifact(tmp_path: Path) -> None:
    """Verify saving and loading PressureModelArtifact JSON."""
    records = [{
        "server": "player_1",
        "surface": "HARD",
        "serve_number": 1,
        "point_winner": "server",
        "leverage": 0.15,
    }]
    df = pd.DataFrame(records)
    stratum_table = build_stratum_table(df)
    artifact = fit_pressure_model(df, stratum_table)

    artifact_dir = tmp_path / "models" / "pressure_deviation"
    saved_path = save_pressure_artifact(artifact, artifact_dir)
    assert saved_path.exists()

    loaded = load_pressure_artifact(artifact_dir)
    assert len(loaded.priors) == len(artifact.priors)
    assert len(loaded.results) == len(artifact.results)


def test_load_pressure_artifact_missing_file(tmp_path: Path) -> None:
    """Verify loading from non-existent directory raises ModelInferenceError."""
    with pytest.raises(ModelInferenceError) as exc_info:
        load_pressure_artifact(tmp_path / "missing")

    assert "PressureModelArtifact not found" in str(exc_info.value)
