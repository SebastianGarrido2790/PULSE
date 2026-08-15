"""PULSE — Consolidated Unit Tests for Game Theory Module (tests/unit/test_game_theory.py).

Implements the authoritative validation property tests from game_theory_spec.md §8:
1. test_equilibrium_mix_sums_to_one
2. test_server_indifference_at_equilibrium
3. test_returner_indifference_at_equilibrium
4. test_delta_non_negative
5. test_lp_matches_closed_form_on_2x2
6. test_sufficiency_gate_fires_below_threshold
7. test_cell_level_gate
8. test_symmetric_game_has_uniform_equilibrium
9. test_exploit_result_all_none_when_gate_fires

Authority: game_theory_spec.md §8, Phase 5 Execution Workflow Stage 8.
"""

import pytest

from src.config.loader import load_params
from src.core.game_theory import (
    PayoffMatrix,
    _solve_2x2_analytical,
    _solve_mn_linprog,
    compute_exploit,
    solve_nash_equilibrium,
)


@pytest.fixture
def standard_2x2_matrix() -> PayoffMatrix:
    """Provide a standard 2x2 PayoffMatrix fixture (spec §2.3)."""
    return PayoffMatrix(
        matrix=[[0.72, 0.58], [0.61, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[30, 20], [20, 30]],
        n_opp_total=100,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )


@pytest.fixture
def standard_3x2_matrix() -> PayoffMatrix:
    """Provide a standard 3x2 PayoffMatrix fixture."""
    return PayoffMatrix(
        matrix=[[0.70, 0.55], [0.62, 0.62], [0.58, 0.72]],
        row_labels=["Wide", "Body", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[25, 20], [30, 25], [20, 30]],
        n_opp_total=150,
        server_id="alcaraz_c",
        returner_id="medvedev_d",
        surface="HARD",
        serve_number=1,
    )


def test_equilibrium_mix_sums_to_one(
    standard_2x2_matrix: PayoffMatrix, standard_3x2_matrix: PayoffMatrix
):
    """Property 1: sum(x*) == 1.0 and sum(y*) == 1.0 on equilibrium strategy vectors."""
    # 2x2 case
    x2, y2, _ = solve_nash_equilibrium(standard_2x2_matrix)
    assert pytest.approx(sum(x2), abs=1e-5) == 1.0
    assert pytest.approx(sum(y2), abs=1e-5) == 1.0
    assert all(0.0 <= p <= 1.0 for p in x2)
    assert all(0.0 <= p <= 1.0 for p in y2)

    # 3x2 case
    x3, y3, _ = solve_nash_equilibrium(standard_3x2_matrix)
    assert pytest.approx(sum(x3), abs=1e-5) == 1.0
    assert pytest.approx(sum(y3), abs=1e-5) == 1.0
    assert all(0.0 <= p <= 1.0 for p in x3)
    assert all(0.0 <= p <= 1.0 for p in y3)


def test_server_indifference_at_equilibrium(standard_2x2_matrix: PayoffMatrix):
    """Property 2: Server indifference condition Pi[i, :] @ y* == V for all active i."""
    matrix = standard_2x2_matrix.matrix
    _, y_opt, v_opt = solve_nash_equilibrium(standard_2x2_matrix)

    # For each row i: Pi[i, :] @ y* == V
    for i in range(len(matrix)):
        ev_row = sum(matrix[i][j] * y_opt[j] for j in range(len(y_opt)))
        assert pytest.approx(ev_row, abs=1e-4) == v_opt


def test_returner_indifference_at_equilibrium(standard_2x2_matrix: PayoffMatrix):
    """Property 3: Returner indifference condition x* @ Pi[:, j] == V for all active j."""
    matrix = standard_2x2_matrix.matrix
    x_opt, _, v_opt = solve_nash_equilibrium(standard_2x2_matrix)

    # For each column j: sum_i(x_opt[i] * Pi[i][j]) == V
    for j in range(len(matrix[0])):
        ev_col = sum(x_opt[i] * matrix[i][j] for i in range(len(x_opt)))
        assert pytest.approx(ev_col, abs=1e-4) == v_opt


def test_delta_non_negative(standard_2x2_matrix: PayoffMatrix, standard_3x2_matrix: PayoffMatrix):
    """Property 4: Exploitation deviation delta >= 0 always holds by minimax definition."""
    params = load_params()

    # 2x2 exploit
    res2 = compute_exploit(standard_2x2_matrix, params)
    assert res2.sufficient_data is True
    assert res2.delta is not None
    assert res2.expected_value_if_exploiting is not None
    assert res2.equilibrium_value is not None
    assert res2.delta >= 0.0
    assert res2.expected_value_if_exploiting >= res2.equilibrium_value - 1e-6

    # 3x2 exploit
    res3 = compute_exploit(standard_3x2_matrix, params)
    assert res3.sufficient_data is True
    assert res3.delta is not None
    assert res3.expected_value_if_exploiting is not None
    assert res3.equilibrium_value is not None
    assert res3.delta >= 0.0
    assert res3.expected_value_if_exploiting >= res3.equilibrium_value - 1e-6


def test_lp_matches_closed_form_on_2x2():
    """Property 5: Linear programming solver and 2x2 closed-form algebraic formula agree."""
    matrix = [[0.68, 0.52], [0.55, 0.74]]
    x_closed, y_closed, v_closed = _solve_2x2_analytical(matrix)
    x_lp, y_lp, v_lp = _solve_mn_linprog(matrix)

    assert pytest.approx(x_lp[0], abs=1e-4) == x_closed[0]
    assert pytest.approx(x_lp[1], abs=1e-4) == x_closed[1]
    assert pytest.approx(y_lp[0], abs=1e-4) == y_closed[0]
    assert pytest.approx(y_lp[1], abs=1e-4) == y_closed[1]
    assert pytest.approx(v_lp, abs=1e-4) == v_closed


def test_sufficiency_gate_fires_below_threshold():
    """Property 6: sufficient_data=False when N_opp < min_sample_size threshold."""
    params = load_params()
    insufficient_n_matrix = PayoffMatrix(
        matrix=[[0.72, 0.58], [0.61, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[5, 5], [5, 5]],
        n_opp_total=20,  # < 30 threshold
        server_id="alcaraz_c",
        returner_id="sparse_opp",
        surface="HARD",
        serve_number=1,
    )

    result = compute_exploit(insufficient_n_matrix, params)
    assert result.sufficient_data is False


def test_cell_level_gate():
    """Property 7: sufficient_data=False when any cell has fewer than min_cell_obs."""
    params = load_params()
    insufficient_cell_matrix = PayoffMatrix(
        matrix=[[0.72, 0.58], [0.61, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[20, 20], [3, 20]],  # cell [1][0] has 3 < 5 min_cell_obs
        n_opp_total=63,  # >= 30 threshold
        server_id="alcaraz_c",
        returner_id="sparse_cell_opp",
        surface="HARD",
        serve_number=1,
    )

    result = compute_exploit(insufficient_cell_matrix, params)
    assert result.sufficient_data is False


def test_symmetric_game_has_uniform_equilibrium():
    """Property 8: Symmetric payoff matrix produces 50/50 uniform mixed equilibrium."""
    symmetric_matrix = PayoffMatrix(
        matrix=[[0.70, 0.50], [0.50, 0.70]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[20, 20], [20, 20]],
        n_opp_total=80,
        server_id="server_a",
        returner_id="returner_b",
        surface="HARD",
        serve_number=1,
    )

    x_opt, y_opt, v_opt = solve_nash_equilibrium(symmetric_matrix)

    assert pytest.approx(x_opt[0], abs=1e-5) == 0.50
    assert pytest.approx(x_opt[1], abs=1e-5) == 0.50
    assert pytest.approx(y_opt[0], abs=1e-5) == 0.50
    assert pytest.approx(y_opt[1], abs=1e-5) == 0.50
    assert pytest.approx(v_opt, abs=1e-5) == 0.60


def test_exploit_result_all_none_when_gate_fires():
    """Property 9: All exploitation fields are None when sufficient_data=False."""
    params = load_params()
    gated_matrix = PayoffMatrix(
        matrix=[[0.72, 0.58], [0.61, 0.75]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[2, 2], [2, 2]],
        n_opp_total=8,
        server_id="alcaraz_c",
        returner_id="gated_opp",
        surface="HARD",
        serve_number=1,
    )

    result = compute_exploit(gated_matrix, params)

    assert result.sufficient_data is False
    assert result.equilibrium_value is None
    assert result.server_equilibrium_mix is None
    assert result.returner_equilibrium_mix is None
    assert result.observed_returner_mix is None
    assert result.best_response_action is None
    assert result.expected_value_if_exploiting is None
    assert result.delta is None
    assert result.n_opp_total == 8
