"""Unit tests for Game Theory Pydantic contracts and validators (Stage 1 / Gate 1)."""

import pytest
from pydantic import ValidationError

from src.config.loader import load_params
from src.core.game_theory import ExploitResult, PayoffMatrix


def test_payoff_matrix_valid_instantiation():
    """Verify valid PayoffMatrix instantiation and property access."""
    payoff = PayoffMatrix(
        matrix=[[0.70, 0.55], [0.60, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[20, 15], [18, 22]],
        n_opp_total=75,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )
    assert payoff.n_opp_total == 75
    assert payoff.surface == "HARD"
    assert len(payoff.matrix) == 2
    assert len(payoff.col_labels) == 2


def test_payoff_matrix_invalid_dimensions():
    """Verify model_validator raises ValidationError when matrix shape does not match labels."""
    with pytest.raises(ValidationError, match="Matrix row count"):
        PayoffMatrix(
            matrix=[[0.70, 0.55]],  # 1 row instead of 2
            row_labels=["Wide", "T"],
            col_labels=["Cover Wide", "Cover T"],
            observation_counts=[[20, 15], [18, 22]],
            n_opp_total=75,
            server_id="alcaraz_c",
            returner_id="sinner_j",
            surface="HARD",
            serve_number=1,
        )

    with pytest.raises(ValidationError, match="does not match col_labels count"):
        PayoffMatrix(
            matrix=[[0.70], [0.60, 0.75]],  # row 0 has length 1 instead of 2
            row_labels=["Wide", "T"],
            col_labels=["Cover Wide", "Cover T"],
            observation_counts=[[20, 15], [18, 22]],
            n_opp_total=75,
            server_id="alcaraz_c",
            returner_id="sinner_j",
            surface="HARD",
            serve_number=1,
        )


def test_payoff_matrix_invalid_probability_bounds():
    """Verify model_validator raises error when matrix contains entries outside [0.0, 1.0]."""
    with pytest.raises(ValidationError, match="outside valid probability range"):
        PayoffMatrix(
            matrix=[[1.2, 0.55], [0.60, 0.75]],  # 1.2 > 1.0
            row_labels=["Wide", "T"],
            col_labels=["Cover Wide", "Cover T"],
            observation_counts=[[20, 15], [18, 22]],
            n_opp_total=75,
            server_id="alcaraz_c",
            returner_id="sinner_j",
            surface="HARD",
            serve_number=1,
        )


def test_exploit_result_valid_instantiation():
    """Verify valid ExploitResult instantiation for both sufficient and insufficient data states."""
    payoff = PayoffMatrix(
        matrix=[[0.70, 0.55], [0.60, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[20, 15], [18, 22]],
        n_opp_total=75,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )

    # Insufficient data result
    insufficient = ExploitResult(
        sufficient_data=False,
        n_opp_total=20,
        payoff_matrix=payoff,
    )
    assert insufficient.sufficient_data is False
    assert insufficient.equilibrium_value is None
    assert insufficient.delta is None

    # Sufficient data result
    sufficient = ExploitResult(
        sufficient_data=True,
        equilibrium_value=0.65,
        server_equilibrium_mix=[0.5, 0.5],
        returner_equilibrium_mix=[0.5, 0.5],
        observed_returner_mix=[0.6, 0.4],
        best_response_action="Wide",
        expected_value_if_exploiting=0.70,
        delta=0.05,
        n_opp_total=75,
        payoff_matrix=payoff,
    )
    assert sufficient.sufficient_data is True
    assert sufficient.delta == 0.05
    assert sufficient.best_response_action == "Wide"


def test_params_loader_game_theory_keys():
    """Verify loader.py successfully loads the new game theory keys from params.yaml."""
    params = load_params()
    assert params.thresholds.game_theory_3x3_min_sample_size == 50
    assert params.models.game_theory_prior_alpha == 2.0
    assert params.models.game_theory_prior_beta == 2.0
    assert params.models.game_theory_min_observations_per_cell == 5
