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

from pydantic import BaseModel, Field, model_validator


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
