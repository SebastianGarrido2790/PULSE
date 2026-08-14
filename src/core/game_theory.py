"""PULSE — Minimax Exploitation & Tactical Game Theory Solver (src/core/game_theory.py).

Provides deterministic game-theoretic models for serve-return interactions:
1. Pydantic v2 domain contracts: PayoffMatrix and ExploitResult (game_theory_spec.md §6).
2. Closed-form 2x2 analytical Nash equilibrium solver (§3.2).
3. scipy.optimize.linprog fallback for general m x n zero-sum matrix games (§3.3).
4. Best-response deviation & EV-shift computation (§4).
5. Two-level sample-size sufficiency gating (§5).

Authority: game_theory_spec.md, ADR-003, Project Constitution §0.1, §2.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator
from scipy.optimize import linprog

from src.config.loader import Params
from src.utils.exceptions import GameTheorySolverException


class PayoffMatrix(BaseModel):
    """Empirical payoff matrix for the serve-return zero-sum matrix game.

    Attributes:
        matrix: (m x n) matrix where matrix[i][j] = P(server wins | direction i, position j).
        row_labels: Serve direction labels (length m), e.g., ["Wide", "Body", "T"].
        col_labels: Returner position labels (length n), e.g., ["Cover Wide", "Cover T"].
        observation_counts: (m x n) matrix of observation counts per cell.
        n_opp_total: Total observations for this opponent in this stratum.
        server_id: Serving player identifier.
        returner_id: Returning player identifier.
        surface: Surface on which data was collected ("HARD", "CLAY", "GRASS").
        serve_number: Serve attempt number (1 or 2).
    """

    matrix: list[list[float]] = Field(..., description="(m x n) empirical win probability matrix")
    row_labels: list[str] = Field(..., description="Serve direction labels (length m)")
    col_labels: list[str] = Field(..., description="Returner position labels (length n)")
    observation_counts: list[list[int]] = Field(..., description="(m x n) cell observation counts")
    n_opp_total: int = Field(..., ge=0, description="Total observations for opponent in stratum")
    server_id: str = Field(..., description="Serving player identifier")
    returner_id: str = Field(..., description="Returning player identifier")
    surface: Literal["HARD", "CLAY", "GRASS"] = Field(..., description="Court surface type")
    serve_number: int = Field(..., ge=1, le=2, description="Serve attempt number (1 or 2)")

    @model_validator(mode="after")
    def validate_matrix_dimensions_and_probabilities(self) -> "PayoffMatrix":
        """Validate matrix dimensions against row/col labels and enforce probability bounds."""
        n_rows = len(self.row_labels)
        n_cols = len(self.col_labels)

        if len(self.matrix) != n_rows:
            raise ValueError(
                f"Matrix row count ({len(self.matrix)}) does not match row_labels count ({n_rows})"
            )

        if len(self.observation_counts) != n_rows:
            raise ValueError(
                f"Observation counts row count ({len(self.observation_counts)}) "
                f"does not match row_labels count ({n_rows})"
            )

        for i in range(n_rows):
            if len(self.matrix[i]) != n_cols:
                raise ValueError(
                    f"Matrix row {i} length ({len(self.matrix[i])}) "
                    f"does not match col_labels count ({n_cols})"
                )
            if len(self.observation_counts[i]) != n_cols:
                raise ValueError(
                    f"Observation counts row {i} length ({len(self.observation_counts[i])}) "
                    f"does not match col_labels count ({n_cols})"
                )
            for j in range(n_cols):
                val = self.matrix[i][j]
                if val < 0.0 or val > 1.0:
                    raise ValueError(
                        f"Payoff matrix entry [{i}][{j}] = {val} is "
                        "outside valid probability range [0.0, 1.0]"
                    )
        return self


class ExploitResult(BaseModel):
    """Game-theory module output payload for one serve-return matchup.

    Attributes:
        sufficient_data: False if N_opp < min_sample_size or cell counts < min. When False,
            all exploitation fields are None — the sufficiency gate has fired.
        equilibrium_value: Nash equilibrium game value V (server's expected win rate).
        server_equilibrium_mix: Server's Nash equilibrium strategy vector x*.
        returner_equilibrium_mix: Returner's Nash equilibrium strategy vector y*.
        observed_returner_mix: Empirical returner positioning frequencies (y_hat).
        best_response_action: Serve direction maximizing EV against observed y_hat.
        expected_value_if_exploiting: Server's expected win rate using best response.
        delta: Exploitation deviation = expected_value_if_exploiting - equilibrium_value.
        n_opp_total: Observation count used (for confidence display in TacticalOutputNode).
        payoff_matrix: The PayoffMatrix input payload (carried for logging/traceability).
    """

    sufficient_data: bool = Field(..., description="True if N_opp and cell counts >= min threshold")
    equilibrium_value: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Nash game value V"
    )
    server_equilibrium_mix: list[float] | None = Field(
        default=None, description="Server Nash mix x*"
    )
    returner_equilibrium_mix: list[float] | None = Field(
        default=None, description="Returner Nash mix y*"
    )
    observed_returner_mix: list[float] | None = Field(
        default=None, description="Observed returner mix y_hat"
    )
    best_response_action: str | None = Field(
        default=None, description="Best response serve direction label"
    )
    expected_value_if_exploiting: float | None = Field(
        default=None, ge=0.0, le=1.0, description="EV under best response"
    )
    delta: float | None = Field(default=None, ge=0.0, description="Exploitation gain delta")
    n_opp_total: int = Field(..., ge=0, description="Total opponent observation count")
    payoff_matrix: PayoffMatrix = Field(..., description="Input PayoffMatrix payload")


def _solve_2x2_analytical(
    matrix: list[list[float]],
) -> tuple[list[float], list[float], float]:
    """Compute Nash equilibrium for 2x2 zero-sum matrix game via exact algebraic formula.

    Formula (game_theory_spec.md §3.2):
        Pi = [[a, b], [c, d]]
        D = a - b - c + d
        x1* = (d - c) / D, x2* = 1 - x1*
        y1* = (d - b) / D, y2* = 1 - y1*
        V = (a * d - b * c) / D

    Args:
        matrix: 2x2 payoff matrix [[a, b], [c, d]].

    Returns:
        tuple[list[float], list[float], float]: (server_mix, returner_mix, game_value).

    Raises:
        GameTheorySolverException: If determinant D is zero or game has dominant pure strategy.
    """
    a = matrix[0][0]
    b = matrix[0][1]
    c = matrix[1][0]
    d = matrix[1][1]

    denom = a - b - c + d

    # Degenerate case guard (D-6)
    if abs(denom) < 1e-12:
        raise GameTheorySolverException(
            f"Degenerate 2x2 game: denominator D={denom:.6e} is zero or near-zero "
            "(game has dominant strategy equilibrium; pure strategy applies)"
        )

    x1 = (d - c) / denom
    x2 = 1.0 - x1
    y1 = (d - b) / denom
    y2 = 1.0 - y1
    v = (a * d - b * c) / denom

    # Bounds check on mixed strategies: valid probabilities must lie in [0, 1]
    if x1 < -1e-9 or x1 > 1.0 + 1e-9 or y1 < -1e-9 or y1 > 1.0 + 1e-9:
        raise GameTheorySolverException(
            f"Degenerate 2x2 game: algebraic equilibrium x*=[{x1:.4f}, {x2:.4f}], "
            f"y*=[{y1:.4f}, {y2:.4f}] falls outside valid probability simplex [0, 1] "
            "(dominant pure strategy present)"
        )

    x1_clamped = float(np.clip(x1, 0.0, 1.0))
    x2_clamped = 1.0 - x1_clamped
    y1_clamped = float(np.clip(y1, 0.0, 1.0))
    y2_clamped = 1.0 - y1_clamped
    v_clamped = float(np.clip(v, 0.0, 1.0))

    return (
        [round(x1_clamped, 6), round(x2_clamped, 6)],
        [round(y1_clamped, 6), round(y2_clamped, 6)],
        round(v_clamped, 6),
    )


def _solve_mn_linprog(
    matrix: list[list[float]],
) -> tuple[list[float], list[float], float]:
    """Compute Nash equilibrium for general m x n zero-sum game via exact linear programming.

    Uses scipy.optimize.linprog with method='highs' (game_theory_spec.md §3.3).

    Args:
        matrix: (m x n) payoff matrix.

    Returns:
        tuple[list[float], list[float], float]: (server_mix, returner_mix, game_value).

    Raises:
        GameTheorySolverException: If linear program fails to converge or find feasible solution.
    """
    pi_arr = np.array(matrix, dtype=np.float64)
    m, n = pi_arr.shape

    # 1. Solve Server's LP (primal): max V s.t. Pi^T x >= V*1, sum(x)=1, x>=0
    # Min -V with variables z = [x_0, ..., x_{m-1}, V] in R^{m+1}
    c_primal = np.zeros(m + 1, dtype=np.float64)
    c_primal[-1] = -1.0

    # Constraints: V - Pi^T x <= 0  ->  [-pi_0j, -pi_1j, ..., -pi_{m-1}j, 1.0] * z <= 0
    A_ub_primal = np.zeros((n, m + 1), dtype=np.float64)
    for j in range(n):
        A_ub_primal[j, :m] = -pi_arr[:, j]
        A_ub_primal[j, m] = 1.0
    b_ub_primal = np.zeros(n, dtype=np.float64)

    A_eq_primal = np.zeros((1, m + 1), dtype=np.float64)
    A_eq_primal[0, :m] = 1.0
    b_eq_primal = np.array([1.0], dtype=np.float64)

    bounds_primal = [(0.0, 1.0) for _ in range(m)] + [(0.0, 1.0)]

    res_primal = linprog(
        c_primal,
        A_ub=A_ub_primal,
        b_ub=b_ub_primal,
        A_eq=A_eq_primal,
        b_eq=b_eq_primal,
        bounds=bounds_primal,
        method="highs",
    )

    if not res_primal.success:
        raise GameTheorySolverException(
            f"Linear programming solver failed for primal game: {res_primal.message}"
        )

    # 2. Solve Returner's LP (dual): min V s.t. Pi y <= V*1, sum(y)=1, y>=0
    # Min V with variables w = [y_0, ..., y_{n-1}, V] in R^{n+1}
    c_dual = np.zeros(n + 1, dtype=np.float64)
    c_dual[-1] = 1.0

    # Constraints: Pi y - V <= 0  ->  [pi_i0, pi_i1, ..., pi_i{n-1}, -1.0] * w <= 0
    A_ub_dual = np.zeros((m, n + 1), dtype=np.float64)
    for i in range(m):
        A_ub_dual[i, :n] = pi_arr[i, :]
        A_ub_dual[i, n] = -1.0
    b_ub_dual = np.zeros(m, dtype=np.float64)

    A_eq_dual = np.zeros((1, n + 1), dtype=np.float64)
    A_eq_dual[0, :n] = 1.0
    b_eq_dual = np.array([1.0], dtype=np.float64)

    bounds_dual = [(0.0, 1.0) for _ in range(n)] + [(0.0, 1.0)]

    res_dual = linprog(
        c_dual,
        A_ub=A_ub_dual,
        b_ub=b_ub_dual,
        A_eq=A_eq_dual,
        b_eq=b_eq_dual,
        bounds=bounds_dual,
        method="highs",
    )

    if not res_dual.success:
        raise GameTheorySolverException(
            f"Linear programming solver failed for dual game: {res_dual.message}"
        )

    x_raw = res_primal.x[:m]
    y_raw = res_dual.x[:n]
    v_raw = float(res_primal.x[m])

    # Normalize vectors to ensure exact simplex sum = 1.0
    x_sum = float(np.sum(x_raw))
    x_opt = (
        [round(float(val) / x_sum, 6) for val in x_raw] if x_sum > 0 else [round(1.0 / m, 6)] * m
    )

    y_sum = float(np.sum(y_raw))
    y_opt = (
        [round(float(val) / y_sum, 6) for val in y_raw] if y_sum > 0 else [round(1.0 / n, 6)] * n
    )

    v_val = round(float(np.clip(v_raw, 0.0, 1.0)), 6)

    return x_opt, y_opt, v_val


def solve_nash_equilibrium(
    payoff_matrix: PayoffMatrix,
) -> tuple[list[float], list[float], float]:
    """Compute mixed-strategy Nash equilibrium for a PayoffMatrix.

    Dispatches to 2x2 closed-form analytical solver if matrix is (2x2),
    or scipy.optimize.linprog (method='highs') if (m > 2 or n > 2).

    Args:
        payoff_matrix: Validated PayoffMatrix instance.

    Returns:
        tuple[list[float], list[float], float]: (server_mix x*, returner_mix y*, game_value V).

    Raises:
        GameTheorySolverException: If input validation fails, game is degenerate, or LP fails.
    """
    matrix = payoff_matrix.matrix
    m = len(matrix)
    if m < 2:
        raise GameTheorySolverException(f"Payoff matrix must have at least 2 rows (got {m})")

    n = len(matrix[0])
    if n < 2:
        raise GameTheorySolverException(f"Payoff matrix must have at least 2 columns (got {n})")

    # Boundary validation check (Step 22)
    for i in range(m):
        for j in range(n):
            val = matrix[i][j]
            if val < 0.0 or val > 1.0:
                raise GameTheorySolverException(
                    f"Payoff matrix entry [{i}][{j}] = {val} is outside [0.0, 1.0]"
                )

    if m == 2 and n == 2:
        return _solve_2x2_analytical(matrix)
    return _solve_mn_linprog(matrix)


def compute_exploit(
    payoff_matrix: PayoffMatrix,
    params: Params,
) -> ExploitResult:
    """Compute minimax exploit result and best-response deviation for a serve-return matchup.

    Orchestration (game_theory_spec.md §4, §5):
    1. Two-level sample size sufficiency check (D-4):
       - If n_opp_total < exploit_min_sample_size OR any observation_counts[i][j] < min_cell_obs:
         Returns ExploitResult with sufficient_data=False and all exploitation fields None.
    2. If sufficient:
       - Computes Nash equilibrium strategy mixes (x*, y*) and game value V.
       - Computes observed returner mix y_hat from column observation sums.
       - Computes server expected values under each serve direction against y_hat.
       - Finds best response pure action x_BR = argmax_i (Pi @ y_hat)_i.
       - Calculates exploitation gain delta = max(0.0, expected_value_if_exploiting - V).

    Args:
        payoff_matrix: Input PayoffMatrix data contract.
        params: PULSE parameters containing thresholds and model settings.

    Returns:
        ExploitResult: Structured payload containing sufficiency status, equilibrium,
            and exploit metrics.

    Raises:
        GameTheorySolverException: If underlying Nash equilibrium computation fails.
    """
    n_opp_total = payoff_matrix.n_opp_total
    min_opp_sample = params.thresholds.exploit_min_sample_size
    min_cell_obs = params.models.game_theory_min_observations_per_cell

    # 1. Two-level Sufficiency Check (D-4)
    # Check total opponent sample size
    if n_opp_total < min_opp_sample:
        return ExploitResult(
            sufficient_data=False,
            n_opp_total=n_opp_total,
            payoff_matrix=payoff_matrix,
        )

    # Check per-cell observation counts
    for row in payoff_matrix.observation_counts:
        for count in row:
            if count < min_cell_obs:
                return ExploitResult(
                    sufficient_data=False,
                    n_opp_total=n_opp_total,
                    payoff_matrix=payoff_matrix,
                )

    # 2. Solve Nash Equilibrium
    server_mix, returner_mix, v_opt = solve_nash_equilibrium(payoff_matrix)

    # 3. Compute Observed Returner Positioning Mix (y_hat)
    # y_hat[j] = sum_i(observation_counts[i][j]) / total_observations
    obs_counts = payoff_matrix.observation_counts
    m = len(obs_counts)
    n = len(obs_counts[0])

    col_sums = [sum(obs_counts[i][j] for i in range(m)) for j in range(n)]
    total_obs = sum(col_sums)

    if total_obs > 0:
        y_hat = [round(float(col_sums[j]) / float(total_obs), 6) for j in range(n)]
    else:
        y_hat = [round(1.0 / n, 6)] * n

    # 4. Compute Server Best-Response Pure Strategy & Expected Value against y_hat
    # EV_i = sum_j(Pi[i][j] * y_hat[j])
    matrix = payoff_matrix.matrix
    action_evs: list[float] = []
    for i in range(m):
        ev_i = sum(matrix[i][j] * y_hat[j] for j in range(n))
        action_evs.append(ev_i)

    best_action_idx = int(np.argmax(action_evs))
    best_action_label = payoff_matrix.row_labels[best_action_idx]
    ev_exploiting = round(float(action_evs[best_action_idx]), 6)

    # 5. Exploitation Gain Delta (D-3, must satisfy delta >= 0.0 by definition)
    raw_delta = ev_exploiting - v_opt
    delta = round(max(0.0, float(raw_delta)), 6)

    return ExploitResult(
        sufficient_data=True,
        equilibrium_value=v_opt,
        server_equilibrium_mix=server_mix,
        returner_equilibrium_mix=returner_mix,
        observed_returner_mix=y_hat,
        best_response_action=best_action_label,
        expected_value_if_exploiting=ev_exploiting,
        delta=delta,
        n_opp_total=n_opp_total,
        payoff_matrix=payoff_matrix,
    )
