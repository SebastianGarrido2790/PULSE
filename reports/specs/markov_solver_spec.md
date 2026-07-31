# Markov Solver — Mathematical Specification

**Component:** `src/core/markov_solver.py`  
**Spec File:** `reports/specs/markov_solver_spec.md`  
**Version:** 1.0.0  
**Date:** 2026-07-31  
**Status:** ✅ Approved (Phase 2 — D-1)  
**Authority:** ADR-002 (`system_design.md`), Phase 2 Decision D-3 (`phase2_implementation_plan_and_decisions.md`)

> **Purpose.** This document is the authoritative written contract for `src/core/markov_solver.py`. It defines every mathematical formula the implementation must reproduce exactly, states the floating-point precision requirement, and specifies the Python function signatures and Pydantic I/O contracts the implementation must expose. Any implementation that deviates from these formulas, for any reason, is wrong by definition; the formula is not adjusted to match the implementation.

---

## 1. Scope & Constraints

### 1.1 What This Solver Is

The closed-form Markov solver is the system's **mathematical ground truth**. It answers one question at any point in a match:

> _Given that the server wins any individual point with probability $p$, what is the probability that the server wins the match from the current score state?_

From this, leverage, the impact of the current point on match-win probability, is derived exactly. No machine-learning model, approximation, or simulation participates in this computation. The solver is purely deterministic, pure-Python arithmetic.

### 1.2 What This Solver Is Not

- **Not a model.** $p$ is an input, not a parameter learned here. The Tier 1 classifier (`src/models/point_win_classifier.py`) estimates $p$.
- **Not a simulation.** No Monte Carlo sampling. All outputs are exact.
- **Not network-accessible.** Runs in-process within the LangGraph runtime. No network hop.

### 1.3 Non-Negotiable Constraints

| Constraint                                                           | Value                                   | Source                                  |
| -------------------------------------------------------------------- | --------------------------------------- | --------------------------------------- |
| Floating-point tolerance (solver vs. theory)                         | < 1e-9 (absolute)                       | ADR-002                                 |
| Maximum latency per solver call                                      | < 1 ms                                  | `params.yaml: latency.state_monitor_ms` |
| No hardcoded thresholds in `markov_solver.py`                        | All config via `params.yaml`            | Project constitution §5                 |
| `SolverException` raised on invalid input — never silently defaulted | —                                       | Project constitution §6 (Resilience)    |
| No mutable global state                                              | Solver functions are pure and stateless | Reproducibility invariant               |

---

## 2. Tennis Scoring Hierarchy

A tennis match decomposes into a strict four-level hierarchy. The solver mirrors this structure exactly:

```
Match  ->  Sets  ->  Games  ->  Points
```

Each level is won-by-two-with-a-ceiling (except where noted) and introduces compounding non-linearity. The IID assumption at the point level — that the server wins every point independently with probability `p` — is the sole input driving all four levels.

---

## 3. Mathematical Formulations

### 3.1 Game Win Probability `g(p)`

**Definition.** The probability that the server wins a game, given serve-win probability `p` at the point level.

A standard game is won by the first player to reach 4 points with a lead of at least 2 (win-by-two, entering Deuce at 3-3).

**Deuce sub-formula.** At Deuce (3-3), the probability of winning from deuce is:

```
d(p) = p^2 / (p^2 + (1-p)^2)
```

**Full game formula.** Accounting for all paths to 4-0, 4-1, 4-2, and all Deuce paths:

```
g(p) = p^4 * C(3,0) * (1-p)^0
     + p^4 * C(4,1) * (1-p)^1
     + p^4 * C(5,2) * (1-p)^2
     + C(6,3) * p^3 * (1-p)^3 * d(p)
```

Which simplifies to the closed-form:

```
g(p) = p^4 * (15 - 34*p + 28*p^2 - 8*p^3) / (1 - 2*p*(1-p))
```

**Derivation note.** The denominator `1 - 2*p*(1-p)` equals `p^2 + (1-p)^2`, the normalising constant of the geometric Deuce series. The numerator collects the three non-Deuce paths plus the Deuce entry coefficient.

**Validation golden values:**

| p   | g(p) exact (12 d.p.) |
| --- | -------------------- |
| 0.5 | 0.500000000000       |
| 0.6 | 0.735728640000       |
| 0.7 | 0.900756020000       |
| 1.0 | 1.000000000000       |
| 0.0 | 0.000000000000       |

---

### 3.2 Tiebreak Win Probability `t(p_A, p_B)`

**Definition.** The probability that Player A (serving first in the tiebreak) wins a 7-point tiebreak, given:

- `p_A`: probability A wins a point when A is serving.
- `p_B`: probability A wins a point when B is serving (i.e., `1 - q_B` where `q_B` is B's serve-win rate).

**Approved implementation method (Sub-Option A1 — Exact Alternating Serve Sequence).** The serve alternation in a standard 7-point tiebreak follows:

```
Point 1:    A serves 1 point
Points 2-3: B serves 2 points
Points 4-5: A serves 2 points
Points 6-7: B serves 2 points
Points 8-9: A serves 2 points
...         (continuing with 2 serves each)
At 6-6:     each player serves 2 in sequence until one leads by 2.
```

**Implementation specification.** The tiebreak win probability is computed by state-space recursion over state (i, j) — points won by A and B respectively — with explicit tracking of whose serve it is at each state.

Define `T(i, j, server)` as the probability A wins the tiebreak from state (i, j) with `server` in {A, B}:

**Terminal states:**

```
T(7, j, *) = 1.0   for j <= 5  (A wins 7-j, lead >= 2)
T(i, 7, *) = 0.0   for i <= 5  (B wins 7-i, lead >= 2)
```

**Deuce at 6-6 — two-serve sub-game:**

```
At (6, 6): A serves points (6+1) and (6+2), B serves points (6+3) and (6+4) ...
T(6, 6, server) resolves via the infinite geometric deuce series:
  P(A wins from deuce | A serves first) = (p_A * p_A) / (p_A*p_A + (1-p_A)*(1-p_A))
  [where deuce alternates 2 serves at a time]
```

**Recursive case:**

```
T(i, j, A) = p_A * T(i+1, j, next_server(i+j+1))
           + (1 - p_A) * T(i, j+1, next_server(i+j+1))

T(i, j, B) = p_B * T(i+1, j, next_server(i+j+1))
           + (1 - p_B) * T(i, j+1, next_server(i+j+1))
```

where `next_server(total_points_played)` follows the 1-2-2-2... alternation rule.

> **Implementation note:** The recursion is finite and must be memoised (e.g., `functools.lru_cache`). The returned value for every (i, j, server) triple must match the combinatorial expansion to within 1e-9.

**Validation golden values:**

| p_A  | p_B  | t(p_A, p_B)                                            |
| ---- | ---- | ------------------------------------------------------ |
| 0.65 | 0.65 | 0.5 (symmetry check)                                   |
| 0.70 | 0.60 | computed at test-write time from independent expansion |

**10-point match tiebreak (Champions Tiebreak).** The same state-space recursion applies with terminal condition at 10 (margin >= 2) instead of 7. A `match_tiebreak: bool` flag in the function signature controls which terminal is used.

---

### 3.3 Set Win Probability `S(p_A, p_B)`

**Definition.** The probability that Player A wins a set given:

- `g_A = g(p_A)`: probability A wins a game when A is serving.
- `g_B = 1 - g(1 - p_B)`: probability A wins a game when B is serving.

A set is won by the first player to reach 6 games with a 2-game lead, entering a tiebreak at 6-6.

**Implementation specification.** State-space recursion over (i, j, server_flag) with server alternating each game:

```
S(6, j, *) = 1.0   for j <= 4       (A wins, not triggering tiebreak)
S(i, 6, *) = 0.0   for i <= 4       (B wins)
S(7, 5, *) = 1.0   (A wins 7-5)
S(5, 7, *) = 0.0   (B wins 5-7)
S(6, 6, *) = t(p_A, p_B)            (tiebreak)
```

**Recursive case:**

```
S(i, j, A_serves) = g_A * S(i+1, j, B_serves) + (1 - g_A) * S(i, j+1, B_serves)
S(i, j, B_serves) = g_B * S(i+1, j, A_serves) + (1 - g_B) * S(i, j+1, A_serves)
```

> **Implementation note:** Server alternates every game. The `server_flag` in the initial call is derived from the match's current serving player and total games played.

**Validation golden values:**

| Score (A-B) | p_A, p_B   | Expected range  |
| ----------- | ---------- | --------------- |
| 5-0         | 0.70, 0.60 | > 0.99          |
| 0-5         | 0.70, 0.60 | < 0.01          |
| 6-6         | 0.65, 0.65 | = t(0.65, 0.65) |

---

### 3.4 Match Win Probability `M(p_A, p_B, sets_A, sets_B, format)`

**Definition.** The probability that Player A wins the match from the current set score.

Two match formats are supported:

| Format          | Win condition   | `format` param |
| --------------- | --------------- | -------------- |
| Best-of-3 (BO3) | First to 2 sets | `"bo3"`        |
| Best-of-5 (BO5) | First to 3 sets | `"bo5"`        |

**Closed-form (BO3).** From set score (sets_A, sets_B), let S = S(p_A, p_B):

State-space recursion over (s_A, s_B):

```
M(2, s_B) = 1.0    for s_B in {0, 1}
M(s_A, 2) = 0.0    for s_A in {0, 1}
M(s_A, s_B) = S * M(s_A+1, s_B) + (1-S) * M(s_A, s_B+1)
```

**Closed-form (BO5).** Same pattern with terminal at 3:

```
M(3, s_B) = 1.0    for s_B in {0, 1, 2}
M(s_A, 3) = 0.0    for s_A in {0, 1, 2}
M(s_A, s_B) = S * M(s_A+1, s_B) + (1-S) * M(s_A, s_B+1)
```

> **Implementation note:** S (set win probability) is re-used across the match recursion. Set win probability itself carries serve-alternation complexity at the within-set level; match-level computation treats each set as a Bernoulli trial with probability S. This is the standard IID-across-sets assumption of the Markov model.

**Third-set/Fifth-set tiebreak rule.** When `deciding_set_tiebreak=True`, the final set (the one that would push either player to 2 or 3 sets) uses `t(p_A, p_B, match_tiebreak=True)` instead of `S`.

**Boundary conditions:**

| State                                  | Value     |
| -------------------------------------- | --------- |
| sets_A == 2 (BO3) or sets_A == 3 (BO5) | M = 1.0   |
| sets_B == 2 (BO3) or sets_B == 3 (BO5) | M = 0.0   |
| All in-progress states                 | 0 < M < 1 |

---

### 3.5 Point Leverage `delta_L(s)`

**Definition.** The increase in A's match-win probability if A wins the current point minus A's match-win probability if A loses the current point, at score state `s`.

```
delta_L(s) = P(Match Win | A wins point at s, p_A, p_B)
           - P(Match Win | A loses point at s, p_A, p_B)
```

Each term is computed by advancing the point score one step (won or lost) and calling the full `M()` hierarchy from that new state.

**Properties enforced in unit tests:**

| Property                                 | Formal statement                                                          |
| ---------------------------------------- | ------------------------------------------------------------------------- |
| Non-negativity                           | delta_L(s) >= 0 for all states                                            |
| Strict positivity at non-terminal states | delta_L(s) > 0 if match is in progress                                    |
| Zero at terminal states                  | delta_L(s) = 0 when M = 1 or M = 0                                        |
| Symmetry                                 | For p_A = p_B = 0.5, delta_L is symmetric when A and B labels are swapped |

---

## 4. Score State Representation

All score state inputs use the canonical internal integer encoding:

```
MatchState:
    point_score_server:   int  # 0="0", 1="15", 2="30", 3="40", 4="AD"
    point_score_returner: int  # same encoding
    game_score_server:    int  # 0-7 (7 = tiebreak in progress)
    game_score_returner:  int  # 0-7
    set_score_server:     int  # 0-2 (BO3) or 0-3 (BO5)
    set_score_returner:   int  # 0-2 (BO3) or 0-3 (BO5)
    server_id:            str  # player identifier (logging only, not used in math)
    match_format:         Literal["bo3", "bo5"]
    deciding_set_tiebreak: bool
```

Score string-to-integer conversion ("0" -> 0, "15" -> 1, "30" -> 2, "40" -> 3, "AD" -> 4) is the responsibility of `src/schemas/point_record.py`, not the solver.

---

## 5. Python Interface Contract

### 5.1 Input Model (`MatchState`)

```python
from pydantic import BaseModel, Field
from typing import Literal


class MatchState(BaseModel):
    """Fully described current match state for Markov solver input.

    Attributes:
        point_score_server: Server's point score in the current game.
            Encoding: 0="0", 1="15", 2="30", 3="40", 4="AD".
        point_score_returner: Returner's point score (same encoding).
        game_score_server: Server's game count in current set (0-6; 7 = tiebreak).
        game_score_returner: Returner's game count in current set (0-6; 7 = tiebreak).
        set_score_server: Server's set count (0-2 for BO3, 0-3 for BO5).
        set_score_returner: Returner's set count.
        server_id: Identifier of the current server. Used for logging only.
        match_format: "bo3" or "bo5".
        deciding_set_tiebreak: If True, the deciding set is a 10-point match tiebreak.
    """

    point_score_server: int = Field(ge=0, le=4)
    point_score_returner: int = Field(ge=0, le=4)
    game_score_server: int = Field(ge=0, le=7)
    game_score_returner: int = Field(ge=0, le=7)
    set_score_server: int = Field(ge=0, le=3)
    set_score_returner: int = Field(ge=0, le=3)
    server_id: str
    match_format: Literal["bo3", "bo5"] = "bo3"
    deciding_set_tiebreak: bool = False
```

### 5.2 Output Model (`SolverResult`)

```python
class SolverResult(BaseModel):
    """Solver output for a single score state and serve probability.

    Attributes:
        match_win_prob: P(server wins match | current state, p_serve).
        match_win_prob_if_won: P(server wins match | server wins this point).
        match_win_prob_if_lost: P(server wins match | server loses this point).
        leverage: delta_L = match_win_prob_if_won - match_win_prob_if_lost.
        p_serve: The serve-win probability used as input.
        state: The MatchState used as input.
    """

    match_win_prob: float = Field(ge=0.0, le=1.0)
    match_win_prob_if_won: float = Field(ge=0.0, le=1.0)
    match_win_prob_if_lost: float = Field(ge=0.0, le=1.0)
    leverage: float = Field(ge=0.0, le=1.0)
    p_serve: float = Field(ge=0.0, le=1.0)
    state: MatchState
```

### 5.3 Public Function Signature

```python
def compute_leverage(state: MatchState, p_serve: float) -> SolverResult:
    """Compute match-win probability and point leverage for a given score state.

    This is the primary public entry point of the Markov solver. It evaluates
    the full hierarchy (point -> game -> set -> match) twice — once advancing
    the current point as won by the server, once as lost — and returns the
    difference as leverage (delta_L).

    Args:
        state: Fully described current match state.
        p_serve: Probability the current server wins any individual point.
            Must be strictly in the open interval (0, 1).

    Returns:
        SolverResult containing match_win_prob, leverage, and both conditional
        match-win probabilities used to derive it.

    Raises:
        SolverException: If p_serve is not strictly in (0, 1), or if state
            encodes a terminal match (sets already decided).
    """
    ...
```

---

## 6. Error & Edge-Case Contracts

| Input Condition                                              | Required Behaviour                                                            |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `p_serve == 0.0` or `p_serve == 1.0`                         | Raise `SolverException` (degenerate denominator in game formula)              |
| `p_serve < 0.0` or `p_serve > 1.0`                           | Raise `SolverException`                                                       |
| Match already decided (e.g., `set_score_server == 2` in BO3) | Raise `SolverException` — caller must not pass terminal states                |
| Invalid score state (e.g., `point_score_server > 4`)         | Pydantic `ValidationError` raised by `MatchState` before the solver is called |

Never silently clamp, default, or substitute a value for an invalid input. A wrong leverage value is worse than a visible error (project constitution §6).

---

## 7. Precision & Reproducibility Requirements

- All arithmetic uses Python native `float` (IEEE 754 double precision, 64-bit).
- No `numpy` or external linear algebra in `markov_solver.py` — only pure Python arithmetic and the `math` stdlib.
- Memoised recursion via `functools.lru_cache` is permitted and recommended for tiebreak and set state-space computations.
- Two calls with identical `(state, p_serve)` arguments must return bit-identical results (pure functions, no random seeds, no global mutable state).
- The CI gate assertion standard: `pytest.approx(expected, abs=1e-9)` must pass on all golden-value tests in `tests/unit/test_markov_solver.py`.

---

## 8. File-Size Ceiling

`src/core/markov_solver.py` must not exceed **1,000 lines** (project constitution §5.1). Comfortable estimate for this scope: 300–450 lines including docstrings. If internal helpers grow the file beyond the ceiling, extract a `_markov_helpers.py` sibling module and update `ALLOWLIST` in `scripts/check_file_size.py` only if justified.

---

## 9. Validation Cross-Reference

Tests in `tests/unit/test_markov_solver.py` (Phase 2 Step 7) that directly verify the formulas in this spec:

| Test Name (target)               | Formula Section Verified                   |
| -------------------------------- | ------------------------------------------ |
| `test_game_prob_symmetry`        | §3.1 — g(0.5) = 0.5                        |
| `test_game_prob_golden_values`   | §3.1 — exact value table                   |
| `test_deuce_recurrence`          | §3.1 — d(p) = p^2 / (p^2 + (1-p)^2)        |
| `test_tiebreak_symmetry`         | §3.2 — t(p, p) = 0.5 for equal players     |
| `test_tiebreak_golden_values`    | §3.2 — independent combinatorial expansion |
| `test_set_prob_boundary_states`  | §3.3 — 5-0 and 0-5 boundary values         |
| `test_match_prob_terminal`       | §3.4 — terminal states return 1.0 / 0.0    |
| `test_leverage_non_negative`     | §3.5 — delta_L(s) >= 0 for all states      |
| `test_leverage_zero_at_terminal` | §3.5 — delta_L = 0 after match decided     |
| `test_leverage_symmetry`         | §3.5 — symmetry at p_A = p_B = 0.5         |

---

_End of Markov Solver Specification._
