"""Unit tests for src/models/point_win_classifier.py (Hierarchical Empirical Stratum Estimator)."""

from pathlib import Path

import pandas as pd
import pytest

from src.config.loader import load_params
from src.models.point_win_classifier import (
    FallbackTier,
    StratumTable,
    build_stratum_table,
    load_stratum_table,
    resolve_point_win_probability,
    save_stratum_table,
    split_points_data,
)
from src.schemas.point_record import Surface
from src.utils.exceptions import ModelInferenceError


@pytest.fixture
def sample_points_df() -> pd.DataFrame:
    """Construct a synthetic points DataFrame with known win/loss records."""
    records = []

    # Player1 on HARD 1st serve: 15 points, 10 wins -> p_hat = 10/15 = 0.6667 (Tier 0 >= 10)
    for i in range(15):
        records.append(
            {
                "server": "player_1",
                "surface": "HARD",
                "serve_number": 1,
                "point_winner": "server" if i < 10 else "returner",
            }
        )

    # Player1 on CLAY 1st serve: 5 points, 4 wins -> Tier 0 sample_size = 5 (< 10)
    for i in range(5):
        records.append(
            {
                "server": "player_1",
                "surface": "CLAY",
                "serve_number": 1,
                "point_winner": "server" if i < 4 else "returner",
            }
        )
    # Player1 total 1st serve: 15 + 5 = 20 points, 10 + 4 = 14 wins -> Tier 1 (player overall) >= 20

    # Population HARD 2nd serve: 60 points, 30 wins -> Tier 2 (surface pop) >= 50
    for i in range(60):
        records.append(
            {
                "server": f"pop_player_{i % 5}",
                "surface": "HARD",
                "serve_number": 2,
                "point_winner": "server" if i < 30 else "returner",
            }
        )

    return pd.DataFrame(records)


def test_split_points_data(sample_points_df: pd.DataFrame) -> None:
    """Verify train/test data splitting ratio and determinism."""
    train_df, test_df = split_points_data(sample_points_df, train_ratio=0.8, random_state=42)

    assert len(train_df) + len(test_df) == len(sample_points_df)
    assert len(train_df) == 64
    assert len(test_df) == 16


def test_build_stratum_table(sample_points_df: pd.DataFrame) -> None:
    """Verify building StratumTable aggregates correct wins, sample sizes, and p_hat."""
    table = build_stratum_table(sample_points_df, default_p=0.62)

    assert isinstance(table, StratumTable)

    # Tier 0 check: player_1|HARD|1
    t0_entry = table.tier0_exact.get("player_1|HARD|1")
    assert t0_entry is not None
    assert t0_entry.sample_size == 15
    assert t0_entry.wins == 10
    assert t0_entry.p_hat == pytest.approx(10.0 / 15.0)

    # Tier 1 check: player_1|1
    t1_entry = table.tier1_player.get("player_1|1")
    assert t1_entry is not None
    assert t1_entry.sample_size == 20
    assert t1_entry.wins == 14
    assert t1_entry.p_hat == pytest.approx(14.0 / 20.0)


def test_resolve_tier0_exact(sample_points_df: pd.DataFrame) -> None:
    """Verify Tier 0 resolution when stratum sample_size >= min_stratum_observations (10)."""
    table = build_stratum_table(sample_points_df)
    params = load_params()

    res = resolve_point_win_probability(
        table, server_id="player_1", surface=Surface.HARD, serve_number=1, params=params
    )

    assert res.fallback_tier == FallbackTier.EXACT_STRATUM
    assert res.sample_size == 15
    assert res.wins == 10
    assert res.p_hat == pytest.approx(10.0 / 15.0)


def test_resolve_tier1_player_overall(sample_points_df: pd.DataFrame) -> None:
    """Verify Tier 1 resolution when stratum N < 10 but overall player N >= 20."""
    table = build_stratum_table(sample_points_df)
    params = load_params()

    # Query player_1 on CLAY 1st serve (stratum N=5 < 10, player overall N=20 >= 20)
    res = resolve_point_win_probability(
        table, server_id="player_1", surface="CLAY", serve_number=1, params=params
    )

    assert res.fallback_tier == FallbackTier.PLAYER_OVERALL
    assert res.sample_size == 20
    assert res.wins == 14
    assert res.p_hat == pytest.approx(14.0 / 20.0)


def test_resolve_tier2_surface_population(sample_points_df: pd.DataFrame) -> None:
    """Verify Tier 2 resolution for an unknown player on HARD 2nd serve (N >= 50)."""
    table = build_stratum_table(sample_points_df)
    params = load_params()

    res = resolve_point_win_probability(
        table, server_id="unknown_player", surface="HARD", serve_number=2, params=params
    )

    assert res.fallback_tier == FallbackTier.SURFACE_POPULATION
    assert res.sample_size == 60
    assert res.wins == 30
    assert res.p_hat == pytest.approx(0.50)


def test_resolve_tier3_global_default(sample_points_df: pd.DataFrame) -> None:
    """Verify Tier 3 resolution for unknown player and unknown stratum."""
    table = build_stratum_table(sample_points_df)
    params = load_params()

    res = resolve_point_win_probability(
        table, server_id="unknown_player", surface="GRASS", serve_number=2, params=params
    )

    assert res.fallback_tier == FallbackTier.GLOBAL_DEFAULT
    assert res.sample_size == 0
    assert res.wins == 0
    assert res.p_hat == params.solver.default_p_serve


def test_save_and_load_stratum_table(sample_points_df: pd.DataFrame, tmp_path: Path) -> None:
    """Verify persisting and loading StratumTable artifact JSON."""
    table = build_stratum_table(sample_points_df)
    artifact_dir = tmp_path / "models" / "point_win_classifier"

    saved_path = save_stratum_table(table, artifact_dir)
    assert saved_path.exists()

    loaded_table = load_stratum_table(artifact_dir)
    assert loaded_table.global_default_p == table.global_default_p
    assert len(loaded_table.tier0_exact) == len(table.tier0_exact)
    loaded_entry = loaded_table.tier0_exact["player_1|HARD|1"]
    orig_entry = table.tier0_exact["player_1|HARD|1"]
    assert loaded_entry.p_hat == orig_entry.p_hat


def test_load_stratum_table_missing_file(tmp_path: Path) -> None:
    """Verify loading from non-existent artifact path raises ModelInferenceError."""
    with pytest.raises(ModelInferenceError) as exc_info:
        load_stratum_table(tmp_path / "missing")

    assert "StratumTable artifact not found" in str(exc_info.value)
