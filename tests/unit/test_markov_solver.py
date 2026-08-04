"""CI-blocking unit test suite for src/core/markov_solver.py.

Golden-value tests comparing closed-form Markov solver output against exact textbook
combinatorial formulas and reference values within 1e-9 tolerance.

Authority: ADR-002, markov_solver_spec.md v1.0.1, Phase 2 Decision D-5
"""

import pytest

from src.core.markov_solver import (
    MatchState,
    compute_leverage,
    compute_match_win_probability_from_state,
    game_prob_from_state,
    game_win_probability,
    next_server,
    set_win_probability,
    t_tail,
    tiebreak_win_probability,
)
from src.utils.exceptions import SolverException


@pytest.mark.solver
def test_game_prob_golden_values() -> None:
    """Verify game win probability g(p) matches exact closed-form golden values."""
    assert game_win_probability(0.5) == pytest.approx(0.500000000000, abs=1e-9)
    assert game_win_probability(0.6) == pytest.approx(0.735729230769, abs=1e-9)
    assert game_win_probability(0.7) == pytest.approx(0.900788965517, abs=1e-9)


@pytest.mark.solver
def test_deuce_recurrence_golden_values() -> None:
    """Verify deuce win probability d(p) matches exact formula p^2 / (p^2 + (1-p)^2)."""
    for p in [0.55, 0.60, 0.65, 0.70, 0.75]:
        expected_d = (p**2) / (p**2 + (1.0 - p) ** 2)
        actual_d = game_prob_from_state(p, s_server=3, s_returner=3)  # 40-40 Deuce
        assert actual_d == pytest.approx(expected_d, abs=1e-9)


@pytest.mark.solver
def test_game_prob_invalid_inputs() -> None:
    """Verify invalid p_serve raises SolverException."""
    with pytest.raises(SolverException):
        game_win_probability(0.0)
    with pytest.raises(SolverException):
        game_win_probability(1.0)
    with pytest.raises(SolverException):
        game_win_probability(-0.1)


@pytest.mark.solver
def test_next_server_sequence() -> None:
    """Verify 1-2-2-2... tiebreak serve alternation order."""
    expected = ["A", "B", "B", "A", "A", "B", "B", "A", "A", "B", "B", "A", "A"]
    for idx, exp in enumerate(expected, start=1):
        assert next_server(idx) == exp


@pytest.mark.solver
def test_t_tail_golden_values() -> None:
    """Verify exact closed-form deuce tail t_tail(p_A, p_B) golden values (§3.2)."""
    assert t_tail(0.50, 0.50) == pytest.approx(0.5000000000, abs=1e-9)
    assert t_tail(0.65, 0.65) == pytest.approx(0.7752293578, abs=1e-9)
    assert t_tail(0.70, 0.60) == pytest.approx(0.7777777778, abs=1e-9)
    assert t_tail(0.55, 0.72) == pytest.approx(0.7586206897, abs=1e-9)


@pytest.mark.solver
def test_tiebreak_golden_values() -> None:
    """Verify 7-point tiebreak win probabilities match spec v1.0.1 golden values."""
    assert tiebreak_win_probability(0.50, 0.50) == pytest.approx(0.5000000000, abs=1e-9)
    assert tiebreak_win_probability(0.65, 0.65) == pytest.approx(0.8865740699, abs=1e-9)
    assert tiebreak_win_probability(0.70, 0.60) == pytest.approx(0.8881752146, abs=1e-9)
    assert tiebreak_win_probability(0.55, 0.55) == pytest.approx(0.6541507672, abs=1e-9)
    assert tiebreak_win_probability(0.80, 0.55) == pytest.approx(0.9317126785, abs=1e-9)


@pytest.mark.solver
def test_set_win_probability_boundary_states() -> None:
    """Verify set win probability bounds for dominant scores and symmetry."""
    # 5-0 lead
    prob_dominant = set_win_probability(0.70, 0.60)
    assert prob_dominant > 0.85

    # Symmetry when both players win 50% serve
    prob_even = set_win_probability(0.50, 0.50)
    assert prob_even == pytest.approx(0.5, abs=1e-9)


@pytest.mark.solver
def test_match_win_probability_bo3_and_bo5() -> None:
    """Verify Best-of-3 and Best-of-5 match win probabilities from initial states."""
    state_bo3 = MatchState(
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=0,
        set_score_returner=0,
        match_format="bo3",
    )
    p_bo3 = compute_match_win_probability_from_state(state_bo3, p_serve=0.60)
    assert 0.5 < p_bo3 < 1.0

    state_bo5 = MatchState(
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=0,
        set_score_returner=0,
        match_format="bo5",
    )
    p_bo5 = compute_match_win_probability_from_state(state_bo5, p_serve=0.60)
    assert p_bo5 > p_bo3  # Amplification effect: BO5 amplifies point-level edge more than BO3


@pytest.mark.solver
def test_compute_leverage_in_progress_state() -> None:
    """Verify compute_leverage on standard 30-30 in-progress score state."""
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

    result = compute_leverage(state, p_serve=0.62)

    assert 0.0 < result.match_win_prob < 1.0
    assert result.match_win_prob_if_won > result.match_win_prob_if_lost
    assert result.leverage > 0.0
    assert result.leverage == pytest.approx(
        result.match_win_prob_if_won - result.match_win_prob_if_lost, abs=1e-9
    )


@pytest.mark.solver
def test_leverage_symmetry_at_equal_skill() -> None:
    """Verify point leverage symmetry when p_serve = 0.5."""
    state_server_serving = MatchState(
        point_score_server=2,
        point_score_returner=2,
        game_score_server=3,
        game_score_returner=3,
        set_score_server=0,
        set_score_returner=0,
        match_format="bo3",
    )
    result = compute_leverage(state_server_serving, p_serve=0.50)
    assert result.match_win_prob == pytest.approx(0.5, abs=1e-9)
    assert result.leverage > 0.0


@pytest.mark.solver
def test_terminal_state_exception() -> None:
    """Verify compute_match_win_probability_from_state raises SolverException on terminal state."""
    state = MatchState(
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=2,  # BO3 match already won
        set_score_returner=0,
        match_format="bo3",
    )

    with pytest.raises(SolverException):
        compute_match_win_probability_from_state(state, p_serve=0.62)
