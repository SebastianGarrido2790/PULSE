# Architectural Finding & Deliberation Report: Game-Theoretic Exploit Module

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Component:** Phase 5 — Game-Theoretic Exploit Module (`src/core/game_theory.py`, `scripts/build_payoff_matrices.py`, `src/graph/strategy_exploit.py`)  
**Topic:** Returner-Strategy Column Modeling, Server Population Pooling, and LP Duality Invariants  
**Date:** 2026-08-16  
**Status:** Resolved (Option A Implemented & Verified)

---

## 1. Executive Summary & Core Findings

During comprehensive post-implementation verification of Phase 5, an in-depth audit of [`scripts/build_payoff_matrices.py`](/scripts/build_payoff_matrices.py), [`artifacts/models/game_theory/payoff_matrices.json`](/artifacts/models/game_theory/payoff_matrices.json), and [`reports/docs/evaluations/game_theory_report.md`](/reports/docs/evaluations/game_theory_report.md) revealed three structural findings that warrant explicit architectural deliberation and formal documentation.

### Finding 1: The Returner-Strategy Axis Uses a Parameterized Heuristic Offset Rather Than Empirical Positioning Data

In `scripts/build_payoff_matrices.py` (`build_payoff_matrix_for_stratum()`), the two columns (`Cover Wide` vs `Cover T`) are constructed by applying fixed scalar offsets to the empirical serve-direction win rate $w_{\text{raw}}$:

```python
delta_mismatch = 0.12
pi_wide_cover_wide = float(np.clip(w_raw - 0.05, 0.05, 0.95))
pi_wide_cover_t = float(np.clip(w_raw + delta_mismatch, 0.05, 0.95))
```

- For every opponent across all 2,139 strata in `payoff_matrices.json`, the gap between columns on Wide and T rows is identically $0.17$ ($0.12 - (-0.05)$).
- On the Body row (for $3\times 2$ matrices), both columns receive the exact same value ($b_{\text{raw}}, b_{\text{raw}}$), rendering the returner's choice irrelevant.
- The `observation_counts` matrix splits direction counts symmetrically ($n_{\text{cell}} = n_{\text{direction}} // 2$), duplicating identical pairs into both columns.
- **Impact:** Opponent return-positioning bias is not directly observed in the charting data; the matrix variation across opponents is driven entirely by the server win rates $w_{\text{raw}}$ against that opponent, with a synthetic anticipation advantage superimposed upon it.

### Finding 2: `server_id` is a Population-Level Placeholder (`population_server`)

`scripts/build_payoff_matrices.py` groups charted points solely by `(returner_id, surface, serve_number)` and tags all exported matrices with `server_id="population_server"`.

- This is a defensible engineering aggregation to avoid severe data sparsity in player-vs-player matchups.
- However, [`reports/docs/evaluations/game_theory_report.md`](../evaluations/game_theory_report.md) §4.2 presented an example payload with `"server_id": "Carlos Alcaraz"`, creating an undocumented discrepancy between the evaluation documentation and the deployed DVC artifact.

### Finding 3: Unused Strong Duality Verification in General LP Solver

In `src/core/game_theory.py` (`_solve_mn_linprog()`), the primal (server maximin) and dual (returner minimax) linear programs are solved independently via `scipy.optimize.linprog(method='highs')`.

- The function extracts $V = \text{res\_primal.x}[m]$ but does not cross-check against $- \text{res\_dual.x}[n]$.
- By Von Neumann's Minimax Theorem (Strong Duality), $V_{\text{primal}} = V_{\text{dual}}$ must hold identically. Adding an explicit tolerance check ($|V_{\text{primal}} - V_{\text{dual}}| < 1\times 10^{-5}$) provides an internal mathematical safety invariant for all $3\times 2$ matrices where closed-form algebraic solutions do not exist.

---

## 2. Why Did This Occur? (Data Reality vs. Academic Formulation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            THE DOMAIN DILEMMA                               │
├──────────────────────────────────────┬──────────────────────────────────────┤
│      Match Charting Project (MCP)    │       Academic Game Theory           │
│              Data Reality            │        Theoretical Model             │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • Human chartists record strokes     │ • Models simultaneous serve-return   │
│   and shot outcomes.                 │   anticipation (e.g. Walker-Wooders) │
│ • Observes: serve direction (4/5/6), │ • Requires: returner latent pre-     │
│   return stroke (f/b/r), error,      │   serve spatial stance / intention   │
│   and point winner.                  │   ("Cover Wide" vs "Cover T").       │
│ • DOES NOT OBSERVE: optical spatial  │ • Result: Theoretical off-diagonal   │
│   pre-serve stance / "cheating"      │   anticipation advantage parameter   │
│   positioning coordinates.           │   must be assumed or parameterized.  │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

1. **The Dataset Boundary:** The Match Charting Project dataset (`points.parquet`, 547,478 points) records trajectory-level event notation (serve placement, return stroke, outcome). It does not include Hawk-Eye or optical camera player-tracking coordinates indicating where the returner was physically standing prior to ball contact.
2. **Academic Game Theory Lineage:** In foundational sports economics literature (e.g., _Walker & Wooders 2001_, "Minimax Play at Wimbledon"; _Chiappori, Levitt & Groseclose 2002_; _Hsu, Huang & Tang 2007_), tennis serve-and-return is formulated as a stylized $2\times 2$ simultaneous matrix game. In these models, empirical serve win rates establish the diagonal baselines, while an assumed or calibrated anticipation advantage parameter ($\Delta$) models the returner guessing correctly versus incorrectly.
3. **The Governance Issue:** While the stylized model is standard in literature, hardcoding $+0.12 / -0.05$ inside the extraction script and presenting the matrix as purely empirical without explicit parameterization or schema disclosure violated PULSE's **Honest Governance** and **Sufficiency Gate** invariants.

---

## 3. Comparative Remediation Options

We evaluate two viable technical paths:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REMEDIATION COMPARISON                             │
├──────────────────────────────────────┬──────────────────────────────────────┤
│  Option A: Parameterized Stylized   │  Option B: Purely Observable         │
│  Matrix Game with Full Disclosure   │  Returner-Execution Matrix           │
│  (Config-Driven Walker-Wooders)     │  (Pure Data-Driven Formulation)      │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### Option A (Recommended): Parameterized Stylized Matrix Game with Honest Schema Metadata & Config Sourcing

Retains the strategic $2\times 2$ and $3\times 2$ simultaneous anticipation formulation, but enforces total code, configuration, and documentation honesty:

1. **Parameter Centralization in `params.yaml`:**
   Remove all hardcoded numbers from `scripts/build_payoff_matrices.py` and source them from namespaced configuration:
   ```yaml
   game_theory:
     anticipation_boost: 0.12 # Server win rate increase when returner covers opposite direction
     positioning_penalty: 0.05 # Server win rate decrease when returner covers serve direction
     min_3x3_sample_size: 50
     min_sample_size: 30
     min_cell_observations: 5
   ```
2. **Contract Transparency (`PayoffMatrix` & `ExploitResult`):**
   Add explicit metadata fields to Pydantic domain models in `src/core/game_theory.py`:
   ```python
   class PayoffMatrix(BaseModel):
       is_stylized_anticipation_model: bool = Field(
           default=True,
           description="True if column differentials represent a calibrated anticipation model.",
       )
       anticipation_delta: float = Field(
           default=0.12, description="Anticipation advantage parameter sourced from params.yaml."
       )
       ...
   ```
3. **LP Strong Duality Verification:**
   In `_solve_mn_linprog()`, assert strong duality between primal and dual solutions:
   ```python
   v_primal = float(res_primal.x[m])
   v_dual = float(-res_dual.x[n])
   if abs(v_primal - v_dual) > 1e-5:
       raise GameTheorySolverException(
           f"Linear program duality gap exceeded tolerance: |{v_primal:.6f} - {v_dual:.6f}| > 1e-5"
       )
   ```
4. **Transparent Documentation:**
   Update `system_design.md` (ADR-011), `game_theory_report.md`, and `specs/game_theory_spec.md` to clearly disclose:
   - Row baselines are empirical and Bayesian-shrunk via Method-of-Moments Beta priors.
   - Column differentials represent a calibrated anticipation model.
   - `server_id` is aggregated at the `population_server` level to preserve statistical power.

- **Pros:** Preserves the closed-form $2\times 2$ minimax equilibrium solver and established spec; eliminates magic numbers; 100% transparent and reproducible.
- **Cons:** Returner anticipation columns remain a calibrated parameter rather than an observed optical coordinate.

---

### Option B: Purely Observable Empirical Matrix (Serve Direction $\times$ Return Shot Outcome)

Redefines the matrix game columns to represent directly observed returner execution states from MCP charting data (e.g., Return in Play vs Return Miss/Error, or Forehand vs Backhand Return):

1. **Observable Column Definition:**
   Define returner actions as observable return categories:
   $$A_R = \{\text{"Return In Play"}, \text{"Return Error / Unforced Error"}\}$$
2. **Direct Cell Counts:**
   Compute $(k_{ij}, n_{ij})$ directly from the returner's actual charting records for each serve direction without any synthetic scalar offsets.
3. **Model Shift:**
   Shifts the game from a simultaneous spatial anticipation game (Walker-Wooders) to a serve-placement vs return-execution game.

- **Pros:** 100% of matrix values come directly from empirical cell counts in `points.parquet`.
- **Cons:** Alters the game-theoretic meaning of the exploit module from strategic anticipation to empirical shot execution; requires rewriting specification contracts and test fixtures.

---

## 4. Invariant Alignment & Evaluation Matrix

| Criterion / Invariant     |      Current State       |             Option A (Recommended)              |                 Option B                 |
| :------------------------ | :----------------------: | :---------------------------------------------: | :--------------------------------------: |
| **Ground-Truth Primacy**  |  ⚠️ Hardcoded in script  | 🟢 Sourced from `params.yaml` + LP Duality Gate |     🟢 Sourced from empirical cells      |
| **Sufficiency Gate**      |  🟢 Gated at $N \ge 30$  |      🟢 Gated at $N \ge 30$, cell $\ge 5$       |   🟢 Gated at $N \ge 30$, cell $\ge 5$   |
| **Architectural Honesty** | ❌ Undisclosed heuristic |   🟢 Explicit Pydantic flags + ADR disclosure   | 🟢 Explicit empirical column definitions |
| **Domain Alignment**      | 🟢 Simultaneous Minimax  |    🟢 Simultaneous Minimax (Walker-Wooders)     |         ⚠️ Execution-stage game          |
| **Refactor Overhead**     |           None           |  🟢 Low (Config + Schema + LP Duality + Docs)   |  🔴 High (Spec + Graph + Test overhaul)  |

---

## 5. Recommendation & Proposed Action Plan

**We recommend Option A.** It maintains the strategic serve-anticipation game-theoretic foundation intended for PULSE while enforcing rigorous engineering discipline and total documentation transparency.

### Proposed Action Items for Option A:

1. **Config:** Add `anticipation_boost: 0.12` and `positioning_penalty: 0.05` to `params.yaml` under `game_theory`.
2. **Schema:** Add `is_stylized_anticipation_model: bool = True` and `anticipation_delta: float` to `PayoffMatrix` and `ExploitResult`.
3. **Script:** Update `scripts/build_payoff_matrices.py` to read these parameters from `params.yaml` with zero hardcoded literals.
4. **Solver:** Add strong duality assertion (`abs(v_primal - v_dual) < 1e-5`) in `_solve_mn_linprog()` in `src/core/game_theory.py`.
5. **Docs:** Update `system_design.md` (ADR-011 amendment) and `game_theory_report.md` with full architectural disclosure and corrected example payloads.
6. **Pipeline:** Run `uv run dvc repro` and `uv run pytest` to regenerate the artifact and verify all 102+ tests.
