"""Unit tests for src/config/loader.py (params.yaml configuration loader)."""

from pathlib import Path

import pytest

from src.config.loader import Params, load_params
from src.utils.exceptions import ConfigException


def test_load_params_default() -> None:
    """Verify loading default params.yaml returns a valid, typed Params instance."""
    params = load_params()

    assert isinstance(params, Params)
    assert params.thresholds.leverage_escalation == 0.10
    assert params.uncertainty.min_stratum_observations == 10
    assert params.uncertainty.min_player_observations == 20
    assert params.uncertainty.min_surface_observations == 50
    assert params.solver.tolerance == 1.0e-9
    assert params.models.point_win_classifier == "hierarchical_stratum_estimator"
    assert params.models.pressure_prior_min_players_per_bucket == 15
    assert params.models.pressure_leverage_buckets == [0.10, 0.25]
    assert params.models.game_theory_anticipation_boost == 0.12
    assert params.models.game_theory_positioning_penalty == 0.05


def test_load_params_file_not_found(tmp_path: Path) -> None:
    """Verify loading a non-existent file path raises ConfigException."""
    non_existent = tmp_path / "missing_params.yaml"

    with pytest.raises(ConfigException) as exc_info:
        load_params(non_existent)

    assert "Configuration file not found" in str(exc_info.value)


def test_load_params_invalid_yaml(tmp_path: Path) -> None:
    """Verify loading an unparseable YAML file raises ConfigException."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("thresholds: [invalid yaml syntax", encoding="utf-8")

    with pytest.raises(ConfigException) as exc_info:
        load_params(bad_yaml)

    assert "Failed to parse YAML file" in str(exc_info.value)


def test_load_params_validation_error(tmp_path: Path) -> None:
    """Verify loading a YAML missing required keys raises ConfigException."""
    incomplete_yaml = tmp_path / "incomplete.yaml"
    incomplete_yaml.write_text("thresholds:\n  leverage_escalation: 0.10\n", encoding="utf-8")

    with pytest.raises(ConfigException) as exc_info:
        load_params(incomplete_yaml)

    assert "Configuration validation failed" in str(exc_info.value)
