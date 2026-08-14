"""Unit tests for Stage 4 Nash Equilibrium Solvers (2x2 closed-form and m x n LP)."""

import time

import pytest

from src.core.game_theory import (
    PayoffMatrix,
    _solve_2x2_analytical,
    _solve_mn_linprog,
    solve_nash_equilibrium,
)
from src.utils.exceptions import SolverException


def test_2x2_analytical_golden_value():
    """Verify 2x2 analytical solver against hand-calculated golden value and indifference."""
    # From game_theory_spec.md §2.3:
    # Pi = [[0.72, 0.58], [0.61, 0.75]]
    # D = 0.72 - 0.58 - 0.61 + 0.75 = 0.28
    # x1* = (0.75 - 0.61) / 0.28 = 0.50
    # y1* = (0.75 - 0.58) / 0.28 = 17/28 ≈ 0.607143
    # V = (0.72*0.75 - 0.58*0.61) / 0.28 = 0.1862 / 0.28 = 0.665
    matrix = [[0.72, 0.58], [0.61, 0.75]]
    x_opt, y_opt, v_opt = _solve_2x2_analytical(matrix)

    assert pytest.approx(x_opt[0], abs=1e-4) == 0.50
    assert pytest.approx(x_opt[1], abs=1e-4) == 0.50
    assert pytest.approx(y_opt[0], abs=1e-4) == 17.0 / 28.0
    assert pytest.approx(y_opt[1], abs=1e-4) == 11.0 / 28.0
    assert pytest.approx(v_opt, abs=1e-4) == 0.6650

    # Indifference check: Pi[0, :] @ y* == Pi[1, :] @ y* == V
    r0_payoff = matrix[0][0] * y_opt[0] + matrix[0][1] * y_opt[1]
    r1_payoff = matrix[1][0] * y_opt[0] + matrix[1][1] * y_opt[1]
    assert pytest.approx(r0_payoff, abs=1e-4) == v_opt
    assert pytest.approx(r1_payoff, abs=1e-4) == v_opt


def test_2x2_closed_form_matches_linprog():
    """Verify LP solver matches 2x2 closed-form analytical solver within high precision."""
    matrix = [[0.68, 0.52], [0.55, 0.74]]
    x_closed, y_closed, v_closed = _solve_2x2_analytical(matrix)
    x_lp, y_lp, v_lp = _solve_mn_linprog(matrix)

    assert pytest.approx(x_lp[0], abs=1e-4) == x_closed[0]
    assert pytest.approx(x_lp[1], abs=1e-4) == x_closed[1]
    assert pytest.approx(y_lp[0], abs=1e-4) == y_closed[0]
    assert pytest.approx(y_lp[1], abs=1e-4) == y_closed[1]
    assert pytest.approx(v_lp, abs=1e-4) == v_closed


def test_3x2_linprog_solver_and_dispatch():
    """Verify 3x2 matrix solver computes valid mixed strategy equilibrium via dispatch."""
    matrix_3x2 = [
        [0.70, 0.55],  # Wide
        [0.62, 0.62],  # Body
        [0.58, 0.72],  # T
    ]
    p_mat = PayoffMatrix(
        matrix=matrix_3x2,
        row_labels=["Wide", "Body", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[30, 30], [25, 25], [30, 30]],
        n_opp_total=170,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )

    x_opt, y_opt, v_opt = solve_nash_equilibrium(p_mat)

    assert len(x_opt) == 3
    assert len(y_opt) == 2
    assert pytest.approx(sum(x_opt), abs=1e-5) == 1.0
    assert pytest.approx(sum(y_opt), abs=1e-5) == 1.0
    assert all(0.0 <= p <= 1.0 for p in x_opt)
    assert all(0.0 <= p <= 1.0 for p in y_opt)
    assert 0.0 <= v_opt <= 1.0


def test_degenerate_game_raises_solver_exception():
    """Verify degenerate 2x2 matrix with D=0 raises SolverException (fail-loud D-6)."""
    # D = 0.6 - 0.6 - 0.6 + 0.6 = 0
    degenerate_matrix = [[0.60, 0.60], [0.60, 0.60]]
    with pytest.raises(SolverException, match="Degenerate 2x2 game"):
        _solve_2x2_analytical(degenerate_matrix)


def test_dominant_strategy_raises_solver_exception():
    """Verify 2x2 game with dominant pure strategy outside [0, 1] raises SolverException."""
    # D = 0.90 - 0.80 - 0.40 + 0.50 = 0.20 != 0, but y1* = (0.50 - 0.80)/0.20 = -1.50 < 0
    dominant_matrix = [[0.90, 0.80], [0.40, 0.50]]
    with pytest.raises(SolverException, match="outside valid probability simplex"):
        _solve_2x2_analytical(dominant_matrix)


def test_solver_timing_sanity_under_5ms():
    """Verify solver execution latency is well under latency budget (< 5ms without coverage)."""
    p_mat = PayoffMatrix(
        matrix=[[0.70, 0.55], [0.62, 0.62], [0.58, 0.72]],
        row_labels=["Wide", "Body", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[30, 30], [25, 25], [30, 30]],
        n_opp_total=170,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
    )

    # Warm-up call
    solve_nash_equilibrium(p_mat)

    t0 = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        solve_nash_equilibrium(p_mat)
    elapsed = (time.perf_counter() - t0) / iterations

    # Budget is 1,000ms. In production it runs in <0.5ms; allow 25ms for CI / coverage trace
    assert elapsed < 0.025, f"Solver too slow: {elapsed * 1000:.2f}ms"
