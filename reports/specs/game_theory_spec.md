# Game Theory Module — Mathematical Specification

**Component:** `src/core/game_theory.py`  
**Spec File:** `reports/specs/game_theory_spec.md`  
**Version:** 1.0.0  
**Date:** 2026-07-31  
**Status:** ✅ Approved (Phase 2 — D-1)  
**Authority:** ADR-003 (`system_design.md`), Project constitution §2, Phase 2 Decision D-1 (`phase2_implementation_plan_and_decisions.md`)

> **Purpose.** This document is the authoritative written contract for `src/core/game_theory.py`. It defines the game-theoretic model of the serve–return interaction, the exact Nash equilibrium calculation method, the exploitation deviation metric, and the sample-size sufficiency gate that must guard every exploitation recommendation. Any implementation that deviates from these definitions, for any reason, is wrong; the formula is not adjusted to match the implementation.

---

## 1. Scope & Constraints

### 1.1 What This Module Computes

The game theory module models the serve–return exchange as a **simultaneous-move, zero-sum game** between two players:

- The **server** chooses a serve direction (e.g., Wide, Body, T).
- The **returner** chooses a court position (e.g., Cover Wide, Cover T).

Given empirical payoff estimates (point-win rates per direction × positioning combination), the module computes:

1. The **Nash equilibrium mixed strategy** for both players — the optimal, opponent-proof serve direction mix.
2. The **exploitation deviation** — how much the specific opponent's observed positioning bias departs from the equilibrium response, and how much expected value is available from exploiting that bias.
3. A **sufficiency gate** that suppresses any exploitation signal when the opponent's historical sample size is below a configured threshold.

### 1.2 What This Module Is Not

- **Not a model.** The payoff matrix cells are derived from empirical historical data, not learned end-to-end. The module is pure optimisation over provided inputs.
- **Not an LLM.** No natural-language reasoning here. The output is a structured `ExploitResult` object consumed downstream by `TacticalOutputNode`.
- **Not a recommendation engine.** The module computes a mathematical signal; the advisory output is assembled by `TacticalOutputNode`.

### 1.3 Non-Negotiable Constraints

| Constraint                                          | Value                                                                   | Source                                                 |
| --------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------ |
| Sample-size gate                                    | Suppress exploit if `N_opp < params.thresholds.exploit_min_sample_size` | ADR-003                                                |
| "Insufficient data" is a valid, complete output     | Not a fallback to be papered over                                       | Project constitution §0.1 (Sufficiency Gate invariant) |
| Exact linear programming for general m x n matrices | `scipy.optimize.linprog`                                                | Project constitution §2                                |
| Closed-form 2x2 solution for 2x2 payoff matrices    | Direct algebraic formula — no LP overhead                               | §3.2 of this spec                                      |
| No hardcoded thresholds                             | All gates via `params.yaml`                                             | Project constitution §5                                |
| `SolverException` raised on invalid inputs          | Never silently ignored                                                  | Project constitution §6                                |

---

## 2. Game-Theoretic Model

### 2.1 Payoff Matrix Definition

The serve–return interaction at each point is modelled as a two-player, zero-sum, simultaneous-move game.

**Players:**

- Row player: **Server** — chooses a serve direction from a finite action set $A_S = \{a_1, a_2, \ldots, a_m\}$ (e.g., Wide, Body, T for $m=3$).
- Column player: **Returner** — chooses a court position from $A_R = \{b_1, b_2, \ldots, b_n\}$ (e.g., Cover Wide, Cover T for $n=2$).

**Payoff entry $\pi_{ij}$:** The probability the server wins the point when the server chooses action $a_i$ and the returner chooses action $b_j$. Estimated from historical charted data.

**Payoff matrix $\Pi$:**

```
Pi is an (m x n) matrix where:
  Pi[i][j] = P(server wins point | server direction i, returner position j)
```

Since the game is zero-sum, the returner's payoff matrix is $-\Pi$ (returner minimises server's win probability).

### 2.2 Worked Example (2×2 Case)

Standard two-direction simplification (Wide vs. T, Cover Wide vs. Cover T):

```
              Cover Wide   Cover T
  Serve Wide  [ pi_11       pi_12  ]
  Serve T     [ pi_21       pi_22  ]
```

Example values (illustrative, not hardcoded):

```
              Cover Wide   Cover T
  Serve Wide  [ 0.72        0.58  ]   <- Server wins more going Wide vs. Cover Wide
  Serve T     [ 0.61        0.75  ]   <- Server wins more going T vs. Cover T
```

---

## 3. Nash Equilibrium Computation

### 3.1 Definition

A Nash equilibrium in mixed strategies is a pair $(x^*, y^*)$ where:

- $x^* \in \Delta^m$ is the server's mixed strategy (probability vector over $A_S$).
- $y^* \in \Delta^n$ is the returner's mixed strategy (probability vector over $A_R$).

At equilibrium, neither player can unilaterally improve their expected payoff by changing strategy.

**Minimax theorem (Von Neumann).** For any finite two-player zero-sum game:

```
max_{x in Delta_m} min_{y in Delta_n} x^T Pi y  =  min_{y in Delta_n} max_{x in Delta_m} x^T Pi y  =  V
```

where $V$ is the **game value** (the equilibrium expected payoff for the server).

### 3.2 Closed-Form Solution for 2×2 Zero-Sum Games

For $m = n = 2$ (two directions, two positions), the equilibrium has an exact algebraic solution with no LP required:

Let the payoff matrix be:

```
Pi = [[a, b],
      [c, d]]
```

**Server's equilibrium mix $x^*$:**

```
Denominator: D = (a - b - c + d)
x1* = (d - c) / D        # probability of serving direction 1 (Wide)
x2* = 1 - x1*            # probability of serving direction 2 (T)
```

**Returner's equilibrium mix $y^*$:**

```
y1* = (d - b) / D        # probability of positioning 1 (Cover Wide)
y2* = 1 - y1*            # probability of positioning 2 (Cover T)
```

**Game value $V$:**

```
V = (a*d - b*c) / D
```

**Degenerate case guard.** If $D = 0$, the game has a dominant-strategy equilibrium. One action dominates the other for at least one player; the pure-strategy solution applies. The implementation must detect and handle this case (raise `SolverException` with a clear message indicating dominant strategy — do not silently produce `NaN`).

**Validation properties (unit-tested in `tests/unit/test_game_theory.py`):**

```
x1* + x2* = 1.0             (probabilities sum to 1)
y1* + y2* = 1.0             (probabilities sum to 1)
x1* in [0, 1]               (valid probability)
y1* in [0, 1]               (valid probability)
```

**Indifference check:**

```
At equilibrium, the server is indifferent between actions:
  Pi[0,:] @ y* = Pi[1,:] @ y* = V   (to within 1e-9 tolerance)
```

### 3.3 General m×n Case via Linear Programming

For payoff matrices with $m > 2$ or $n > 2$, the module falls back to `scipy.optimize.linprog` (exact LP, not heuristic).

**Server's LP (maximise game value V):**

```
Primal variables: x in R^m (serve mix), V in R (game value)

Maximise: V
Subject to:
  Pi^T x >= V * ones(n)    (for each returner action, server's expected payoff >= V)
  sum(x) = 1               (probability simplex)
  x >= 0                   (non-negative)
```

**Returner's LP (minimise game value V, dual):**

```
Variables: y in R^n (return mix), V in R

Minimise: V
Subject to:
  Pi y <= V * ones(m)      (for each server action, returner's expected loss <= V)
  sum(y) = 1
  y >= 0
```

> **Implementation note:** Use `scipy.optimize.linprog` with `method='highs'` (exact simplex with HiGHS solver, the scipy default for LP since 1.9.0). Do not use `'revised simplex'` or `'interior-point'` methods — HiGHS is more numerically stable for this scale of problem.

**Validation property:**

```
The LP-derived equilibrium game value V must equal the 2x2 closed-form V to within 1e-9
when both methods are applied to the same 2x2 payoff matrix.
```

---

## 4. Exploitation Deviation Metric

### 4.1 Definition

The **exploitation deviation** $\delta$ measures the expected-value gain the server can capture by responding optimally to the specific returner's observed positioning bias, rather than playing the Nash equilibrium mix.

**Observed returner mix $\hat{y}$:** The empirical frequency of each returner positioning action, estimated from $N_{\text{opp}}$ historical charted points against this specific opponent.

```
y_hat[j] = (count of times returner chose position j) / N_opp
```

**Server's best response to $\hat{y}$:**

```
x_BR = argmax_{x in Delta_m} x^T Pi y_hat
     = a pure strategy (the serve direction maximising expected payoff against y_hat)
```

**Exploitation deviation:**

```
delta = (x_BR^T Pi y_hat) - V
      = u(x_BR, y_hat) - u(x_star, y_star)
```

where $u(\cdot)$ denotes expected payoff and $V$ is the equilibrium game value.

**Properties:**

```
delta >= 0   always (best response can never be worse than equilibrium)
delta = 0    when the opponent plays their equilibrium strategy exactly
delta > 0    when the opponent's observed mix departs from equilibrium
```

### 4.2 Expected-Value Gain Reporting

The module reports:

- `delta`: The raw exploitation deviation.
- `best_response_action`: The specific serve direction (e.g., "Wide") that maximises expected value against the observed `y_hat`.
- `expected_value_if_exploiting`: $x_{\text{BR}}^T \Pi \hat{y}$ — the expected point-win rate if the server plays the best response.
- `equilibrium_value`: $V$ — the baseline expected point-win rate at Nash equilibrium.

---

## 5. Sample-Size Sufficiency Gate

### 5.1 Gate Definition

The exploitation deviation $\delta$ must **not be computed or reported** if the opponent's historical observation count is below the minimum threshold:

```
N_opp < params.thresholds.exploit_min_sample_size
```

where `exploit_min_sample_size` is sourced from `params.yaml` (never hardcoded).

### 5.2 Behaviour Below the Gate

When `N_opp < exploit_min_sample_size`:

- The module returns an `ExploitResult` with `sufficient_data=False` and all exploitation metrics set to `None`.
- No `SolverException` is raised — this is an expected, valid state, not an error.
- The caller (`StrategyExploitNode`) surfaces a "Insufficient opponent data" advisory rather than suppressing output entirely.

### 5.3 Per-Cell Minimum Count

The payoff matrix cell $\pi_{ij}$ requires a minimum of observations for the estimate to be reliable. If any cell has fewer than `params.thresholds.exploit_min_sample_size` observations, the overall `sufficient_data` flag is `False`.

> **Implementation note:** Cell-level and aggregate-level sufficiency are checked independently. A matrix with 100 observations in one cell and 2 in another must still gate as insufficient.

### 5.4 Observation Count Tracking

Observation counts per (server_id, surface, serve_number, direction, returner_position) stratum are tracked externally (in the data layer / `PointRecord` schema). The game theory module receives these counts as inputs via the `PayoffMatrix` Pydantic model — it does not query the database directly.

---

## 6. Python Interface Contract

### 6.1 Input Models

```python
from pydantic import BaseModel, Field
import numpy as np
from typing import Literal


class PayoffMatrix(BaseModel):
    """Empirical payoff matrix for the serve-return game.

    Attributes:
        matrix: (m x n) matrix where matrix[i][j] = P(server wins | direction i, position j).
        row_labels: Serve direction labels (length m), e.g., ["Wide", "Body", "T"].
        col_labels: Returner position labels (length n), e.g., ["Cover Wide", "Cover T"].
        observation_counts: (m x n) matrix of observation counts per cell.
        n_opp_total: Total observations for this opponent in this stratum.
        server_id: Serving player identifier.
        returner_id: Returning player identifier.
        surface: Surface on which data was collected.
        serve_number: Serve number (1 or 2).
    """

    matrix: list[list[float]]
    row_labels: list[str]
    col_labels: list[str]
    observation_counts: list[list[int]]
    n_opp_total: int = Field(ge=0)
    server_id: str
    returner_id: str
    surface: Literal["HARD", "CLAY", "GRASS"]
    serve_number: int = Field(ge=1, le=2)
```

### 6.2 Output Model

```python
class ExploitResult(BaseModel):
    """Game-theory module output for one serve-return matchup.

    Attributes:
        sufficient_data: False if N_opp < exploit_min_sample_size. When False,
            all exploitation fields are None — the sufficiency gate has fired.
        equilibrium_value: Nash equilibrium game value V (server's expected win rate).
        server_equilibrium_mix: Server's Nash equilibrium strategy vector.
        returner_equilibrium_mix: Returner's Nash equilibrium strategy vector.
        observed_returner_mix: Empirical returner positioning frequencies (y_hat).
        best_response_action: The serve direction that maximises EV against observed y_hat.
        expected_value_if_exploiting: Server's expected win rate using best response.
        delta: Exploitation deviation = expected_value_if_exploiting - equilibrium_value.
        n_opp_total: Observation count used (for confidence display in TacticalOutputNode).
        payoff_matrix: The PayoffMatrix input (carried for logging).
    """

    sufficient_data: bool
    equilibrium_value: float | None = Field(default=None, ge=0.0, le=1.0)
    server_equilibrium_mix: list[float] | None = None
    returner_equilibrium_mix: list[float] | None = None
    observed_returner_mix: list[float] | None = None
    best_response_action: str | None = None
    expected_value_if_exploiting: float | None = Field(default=None, ge=0.0, le=1.0)
    delta: float | None = Field(default=None, ge=0.0)
    n_opp_total: int
    payoff_matrix: PayoffMatrix
```

### 6.3 Public Function Signature

```python
def compute_exploit(
    payoff: PayoffMatrix,
    min_sample_size: int,
) -> ExploitResult:
    """Compute the Nash equilibrium and exploitation deviation for a serve-return matchup.

    Applies the sample-size sufficiency gate first. If the gate fires (N_opp
    below min_sample_size), returns ExploitResult(sufficient_data=False) without
    computing the equilibrium — this is a valid, complete output, not an error.

    For 2x2 payoff matrices, uses the exact closed-form algebraic solution.
    For larger matrices, falls back to scipy.optimize.linprog with method='highs'.

    Args:
        payoff: Empirical payoff matrix with observation counts and labels.
        min_sample_size: Minimum N_opp required to compute exploitation metrics.
            Sourced from params.yaml by the caller; not hardcoded here.

    Returns:
        ExploitResult. If sufficient_data=False, all exploitation fields are None.

    Raises:
        SolverException: If the payoff matrix is degenerate (D=0 in 2x2 case),
            the LP is infeasible, or the matrix contains values outside [0, 1].
    """
    ...
```

---

## 7. Error & Edge-Case Contracts

| Input Condition                                  | Required Behaviour                                                    |
| ------------------------------------------------ | --------------------------------------------------------------------- |
| `n_opp_total < min_sample_size`                  | Return `ExploitResult(sufficient_data=False)`, no exception           |
| Any `observation_counts[i][j] < min_sample_size` | Return `ExploitResult(sufficient_data=False)`                         |
| `matrix[i][j] < 0` or `matrix[i][j] > 1`         | Raise `SolverException` (invalid probability)                         |
| 2x2 with degenerate denominator `D = 0`          | Raise `SolverException` with explicit message about dominant strategy |
| LP returns infeasible or unbounded status        | Raise `SolverException` with LP status in message                     |
| `row_labels` length != `matrix` rows             | `ValidationError` from Pydantic on `PayoffMatrix`                     |

---

## 8. Validation Properties (Unit Tests)

Tests in `tests/unit/test_game_theory.py` (Phase 5 implementation) must verify:

| Test                                           | Property Verified                                                                   |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| `test_equilibrium_mix_sums_to_one`             | `sum(x*) = 1.0`, `sum(y*) = 1.0`                                                    |
| `test_server_indifference_at_equilibrium`      | `Pi[i,:] @ y* == V` for all i (within 1e-9)                                         |
| `test_returner_indifference_at_equilibrium`    | `x* @ Pi[:,j] == V` for all j (within 1e-9)                                         |
| `test_delta_non_negative`                      | `delta >= 0` always                                                                 |
| `test_lp_matches_closed_form_on_2x2`           | LP and closed-form agree to within 1e-9                                             |
| `test_sufficiency_gate_fires_below_threshold`  | `sufficient_data=False` when `N_opp < min_sample_size`                              |
| `test_cell_level_gate`                         | `sufficient_data=False` when any cell has fewer than `min_sample_size` observations |
| `test_symmetric_game_has_uniform_equilibrium`  | Symmetric payoff matrix -> 50/50 mix for both players                               |
| `test_exploit_result_all_none_when_gate_fires` | All exploitation fields are `None` when `sufficient_data=False`                     |

---

## 9. Relationship to Other Components

| Component                       | Relationship                                                                                                                      |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `src/core/markov_solver.py`     | Independent — no dependency. The game theory module operates on per-point historical distributions, not on the live Markov state. |
| `src/graph/strategy_exploit.py` | Consumer — calls `compute_exploit()` and decides whether to surface the signal based on `sufficient_data`.                        |
| `src/schemas/point_record.py`   | Upstream — provides the `serve_direction` and observation count data that populates `PayoffMatrix`.                               |
| `params.yaml`                   | Configuration source — `exploit_min_sample_size` must be read by the caller and passed as `min_sample_size`.                      |
| `src/utils/exceptions.py`       | `SolverException` is raised for all hard failure cases (§7 above).                                                                |

---

## 10. File-Size Ceiling

`src/core/game_theory.py` must not exceed **1,000 lines** (project constitution §5.1). Comfortable estimate for this scope: 250–350 lines including docstrings. The LP integration via `scipy.optimize.linprog` adds no more than ~30 lines; the bulk is the closed-form 2×2 solver, Pydantic models, and validation logic.

---

_End of Game Theory Module Specification._
