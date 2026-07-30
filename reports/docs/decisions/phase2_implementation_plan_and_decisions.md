# Phase 2 — Data Layer & Deterministic Core: Implementation Plan & Decisions

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Phase:** Phase 2 — Data Layer & Deterministic Core  
**Version:** 0.1.0  
**Date Created:** 2026-07-30  
**Status:** ✅ Approved (2026-07-30)

> **Purpose of this document.** This is the living design-decision record and technical implementation plan for Phase 2. It translates each deliverable from [`technical_roadmap.md` §Phase 2](../references/technical_roadmap.md) into concrete, actionable design choices with trade-off analysis. All decisions in this document have been explicitly approved by the user (2026-07-30) and serve as the authoritative baseline for implementation and phase-close ADR review.

---

## 1. Current State Audit

Before proposing design decisions, here is the honest, file-by-file inventory of what exists, what is missing, and what requires attention within the Phase 2 scope:

| Artifact / File Path               | Current State                                                                        | Identified Gap / Latent Issue                                                                                                                                        | Action Required for Phase 2                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `reports/docs/specs/`              | Directory does not exist                                                             | Missing written mathematical contracts for the two highest-novelty components (`markov_solver_spec.md` & `game_theory_spec.md`)                                      | Create directory and draft mathematical specifications                          |
| `src/schemas/point_record.py`      | File does not exist (`src/schemas/` contains only `__init__.py`)                     | Missing Pydantic v2 `PointRecord` domain schema, enum definitions, and `pandera` DataFrame validation gates per `ml_canvas.md` §6                                    | Implement Pydantic schema and `pandera` validation model                        |
| `src/core/markov_solver.py`        | File does not exist (`src/core/` contains only `__init__.py`)                        | Missing closed-form Markov solver engine computing point $\rightarrow$ game $\rightarrow$ set $\rightarrow$ match probabilities and leverage ($\Delta L$)            | Implement exact analytical Markov solver engine                                 |
| `src/core/leverage_uncertainty.py` | File does not exist                                                                  | Missing Wilson score confidence interval propagation for point-win probability $p$ and leverage bounds $[\Delta L_{\text{low}}, \Delta L_{\text{high}}]$ per ADR-005 | Implement Wilson score & leverage interval propagation module                   |
| `tests/unit/test_markov_solver.py` | File does not exist (`tests/unit/` contains `__init__.py` and `test_scaffolding.py`) | Missing CI-blocking golden-value unit tests comparing solver output to textbook combinatorial formulas within $1 \cdot 10^{-9}$ tolerance                            | Implement comprehensive solver test suite with `@pytest.mark.solver` marker     |
| `params.yaml`                      | Implemented in Phase 1 (20 lines)                                                    | Lacks Phase 2 parameters: stratum observation count thresholds, Wilson confidence alpha, score state limits, dataset path specs                                      | Update with Phase 2 data & solver configuration blocks                          |
| `dvc.yaml`                         | Implemented in Phase 1 (27 lines)                                                    | `ingest` stage is a dummy placeholder (`cmd: echo "Stage not yet implemented..."`)                                                                                   | Replace dummy `ingest` stage with executable command, dependencies, and outputs |
| `scripts/ingest.py`                | File does not exist                                                                  | Missing ingestion execution script referenced by `dvc.yaml` to validate and transform raw point data into `data/validated/`                                          | Implement raw data parser and `pandera` validation runner                       |
| `data/raw/`                        | Directory exists (0 files)                                                           | Raw Tennis Abstract / charted point-by-point data missing                                                                                                            | Add raw sample CSV dataset and DVC tracking rules                               |
| `data/validated/`                  | Directory does not exist                                                             | Missing output target directory for validated Parquet datasets                                                                                                       | Create directory and configure DVC pipeline tracking                            |
| `src/utils/logger.py`              | ✅ Implemented in Phase 1 (79 lines)                                                 | Clean (imports `Path` on line 12)                                                                                                                                    | Ready for schema and solver logging                                             |
| `src/utils/exceptions.py`          | ✅ Implemented in Phase 1 (88 lines)                                                 | `SolverException` and `SufficiencyGateException` already present                                                                                                     | Ready for use in Phase 2 core engine                                            |

---

## 2. Decision Map

Each Phase 2 deliverable from `technical_roadmap.md §Phase 2` maps to one primary decision below. Where a decision involves architectural choices, comparative options and trade-offs are presented for user selection.

| Decision ID | Deliverable / Component            | Decision Title                                                       | Decision Type                                     |
| ----------- | ---------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------- |
| **D-1**     | `reports/docs/specs/*.md`          | Specs Scope & Mathematical Rigor Standard                            | ✅ **[Approved — Single Valid Path]**              |
| **D-2**     | `src/schemas/point_record.py`      | Data Schema Architecture & Validation Strategy                       | ✅ **[Approved — Option A, Sub-Option A1]**        |
| **D-3**     | `src/core/markov_solver.py`        | Markov Solver Engine: Closed-Form Derivation vs. Transition Matrices | ✅ **[Approved — Option A, Sub-Option A1]**        |
| **D-4**     | `src/core/leverage_uncertainty.py` | Wilson Score Uncertainty & Leverage Band Propagation Architecture    | ✅ **[Approved — Option A]**                       |
| **D-5**     | `tests/unit/test_markov_solver.py` | CI-Blocking Solver Verification Suite & Combinatorial Coverage       | ✅ **[Approved — Single Valid Path]**              |
| **D-6**     | `params.yaml`                      | Operational Parameters & Stratum Threshold Configuration             | ✅ **[Approved — Option A]**                       |
| **D-7**     | `dvc.yaml` & `scripts/ingest.py`   | Raw Data Ingestion & DVC Pipeline Architecture                       | ✅ **[Approved — Option A]**                       |

---

## D-1 — Specs Scope & Mathematical Rigor Standard (`reports/docs/specs/*.md`)

**Status:** ✅ **Approved (Single Valid Path)**

**Deliverable:** Create directory `reports/docs/specs/` and author written component specifications for the two highest-novelty components:

1. `reports/docs/specs/markov_solver_spec.md`: Closed-form Markov solver specification.
2. `reports/docs/specs/game_theory_spec.md`: Game-theoretic Nash equilibrium and best-response deviation specification.

**Context & Constraints:**

- Project constitution §4 explicitly lists `reports/docs/specs/markov_solver_spec.md` and `reports/docs/specs/game_theory_spec.md` as required written contracts.
- ADR-002 mandates exact mathematical derivation matching combinatorial probability theory within $1 \cdot 10^{-9}$ tolerance.
- ADR-003 mandates exact data-sufficiency gating equations for game-theoretic exploit calculation.

**Specification Plan:**

- **`reports/docs/specs/markov_solver_spec.md`**:
  - Full mathematical formulation for Game win probability $g(p)$, Advantage/Deuce recurrence relations, Tiebreak probabilities (7-point and 10-point match tiebreaks), Set win probability $S(g_A, g_B)$, and Match win probability $M(S)$.
  - Leverage mathematical definition: $\Delta L(s) = P(\text{Match Win} \mid \text{Won Point}, s) - P(\text{Match Win} \mid \text{Lost Point}, s)$.
  - Floating-point precision requirements ($1 \cdot 10^{-9}$) and Pydantic/Python interface definitions.
- **`reports/docs/specs/game_theory_spec.md`**:
  - $2 \times 2$ matrix game formulation between server shot selection (e.g., Wide vs. T) and receiver positioning (e.g., Cover Wide vs. Cover T).
  - Exact minimax Nash equilibrium calculation via closed-form $2 \times 2$ solution (and `scipy.optimize.linprog` fallback for general $m \times n$).
  - Exploitation deviation metric $\delta = u(\text{actual}) - u(\text{optimal})$ and sample-size gate formula $N_{\text{opp}} \ge N_{\text{min}}$.

---

## D-2 — Data Schema Architecture & Validation Strategy (`src/schemas/point_record.py`)

**Status:** ✅ **Approved (Option A — Co-located Pydantic v2 + Pandera Schema, Sub-Option A1 — Strict Tennis Score Coercion)**

**Deliverable:** `src/schemas/point_record.py` defining Pydantic v2 `PointRecord` domain model and `pandera` DataFrame schema gates per `pulse_ml_canvas.md` §6.

**Context & Constraints:**

- The system processes tennis data in two modes:
  1. **Bulk Ingestion & Pipeline Validation:** Processing raw CSV files into validated Parquet datasets (`dvc.yaml`).
  2. **Streaming / In-Memory Inference:** Single-point evaluation in `StateMonitorNode` and match replay simulator (`simulator/replay.py`).
- Pydantic v2 is required for Python runtime validation (Project constitution §2).
- `pandera` is required for DataFrame column, data type, and range validation (Project constitution §2).

### Options:

#### Option A — Co-located Pydantic v2 Domain Model + `pandera` DataFrame Schema (Proposed ✅)

Define shared Enumerations (`Surface`, `ServeNumber`, `PointOutcome`, `TournamentLevel`), the single-record Pydantic model `PointRecord`, and the bulk `pandera.DataFrameModel` (`PointRecordSchema`) together in `src/schemas/point_record.py`.

```python
# Shared Enums
class Surface(str, Enum):
    HARD = "HARD"
    CLAY = "CLAY"
    GRASS = "GRASS"

# Pydantic v2 model for runtime / streaming point records
class PointRecord(BaseModel):
    match_id: str
    point_number: int = Field(ge=1)
    player1_id: str
    player2_id: str
    server_id: str
    serve_number: int = Field(ge=1, le=2)
    surface: Surface
    p1_score: str
    p2_score: str
    point_winner: str
    # ... additional domain fields

# Pandera DataFrame Schema for DVC bulk ingestion pipeline validation
class PointRecordSchema(pa.DataFrameModel):
    match_id: pa.String
    point_number: pa.Int = pa.Field(ge=1)
    serve_number: pa.Int = pa.Field(isin=[1, 2])
    surface: pa.String = pa.Field(isin=["HARD", "CLAY", "GRASS"])
    # ... additional DataFrame checks
```

_Trade-offs:_

- **Pros:** Guarantees 100% field parity between row-by-row streaming inference and bulk Parquet ingestion. Keeps single source of truth in `src/schemas/point_record.py` (~220 lines, well below the 1,000-line ceiling).
- **Cons:** Slightly tighter coupling between Pydantic and Pandera imports, but both are standard project dependencies in `pyproject.toml`.

#### Option B — Separate Schema Files (`point_record_pydantic.py` and `point_record_pandera.py`)

Split the single-record Pydantic model and the DataFrame Pandera schema into two separate files under `src/schemas/`.

_Trade-offs:_

- **Pros:** Isolates Pandera dependency from light streaming scripts that only need Pydantic.
- **Cons:** High risk of schema drift when fields are added or modified; duplicates enum definitions across multiple files.

### Sub-Decision D-2a — Score State Validation Strategy:

| Sub-Option                            | Description                                                                                                                          | Recommendation                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| **A1 — Strict Tennis Score Coercion** | Validate `p1_score` and `p2_score` against valid tennis point scores (`"0"`, `"15"`, `"30"`, `"40"`, `"AD"`) at the schema boundary. | ✅ **Proposed**                                                  |
| **A2 — Raw Integer Point Counts**     | Convert scores to cumulative points won (`0`, `1`, `2`, `3`, `4+`) in the schema.                                                    | Alternative (Loses traditional score context needed for logging) |

---

## D-3 — Markov Solver Engine Architecture (`src/core/markov_solver.py`)

**Status:** ✅ **Approved (Option A — Direct Hierarchical Closed-Form Analytical Formulas, Sub-Option A1 — Exact Alternating Serve Sequence)**

**Deliverable:** `src/core/markov_solver.py` implementing exact closed-form functions for tennis win probabilities and point leverage $\Delta L(s)$.

**Context & Constraints:**

- ADR-002 mandates that the closed-form Markov solver is the ground truth. Its output must match combinatorial probability theory within $1 \cdot 10^{-9}$ tolerance.
- `StateMonitorNode` latency budget is $< 1000\,\text{ms}$ per point (NFR). Solver computation per point must be ultra-fast ($< 1\,\text{ms}$).
- Tennis scoring is hierarchical: Point $\rightarrow$ Game $\rightarrow$ Set $\rightarrow$ Match.

### Options:

#### Option A — Direct Hierarchical Closed-Form Analytical Formulas (Proposed ✅)

Implement closed-form algebraic functions derived directly from absorbing Markov chain theory for each tier:

1. **Game Level $g(p)$:**
   For serve win probability $p$ and return win probability $q = 1-p$:
   $$g(p) = p^4 + 4p^4(1-p) + 10p^4(1-p)^2 + \frac{20p^3(1-p)^3 \cdot p^2}{p^2 + (1-p)^2}$$
   Simplifying algebraically to:
   $$g(p) = \frac{p^4(15 - 34p + 28p^2 - 8p^3)}{1 - 2p(1-p)}$$
2. **Tiebreak Level $t(p_A, p_B)$:**
   Exact analytical solution accounting for alternating serve sequence ($A, B, B, A, A, B, B \dots$) for 7-point tiebreaks and 10-point match tiebreaks.
3. **Set Level $S(g_A, g_B)$:**
   Exact combinatorial formula over set score states $(i, j)$ up to 6–6 (entering tiebreak).
4. **Match Level $M(S_A, S_B)$:**
   Exact combinatorial expansion for Best-of-3 ($S^2(3-2S)$) and Best-of-5 sets ($S^3(1 + 3(1-S) + 6(1-S)^2)$).
5. **Leverage Computation $\Delta L(s)$:**
   $$\Delta L(s) = P(\text{Match Win} \mid \text{Server wins point } s, p_A, p_B) - P(\text{Match Win} \mid \text{Receiver wins point } s, p_A, p_B)$$

_Trade-offs:_

- **Pros:** Absolute exactness ($0.000000000$ deviation from theory), ultra-fast execution speed ($< 5\,\mu\text{s}$ per call), zero memory allocations, 100% deterministic type safety. Fully satisfies ADR-002 $1 \cdot 10^{-9}$ CI gate.
- **Cons:** Mathematical formulas require rigorous unit testing across all score boundary states (provided by D-5).

#### Option B — Transition Matrix Sparse System Inversion ($(I - Q)^{-1} R$)

Represent tennis score states as a sparse graph transition matrix $P$, construct fundamental matrix $N = (I - Q)^{-1}$, and solve for absorbing probabilities using `scipy.sparse.linalg`.

_Trade-offs:_

- **Pros:** Flexible layout if custom non-standard game rules are dynamically introduced.
- **Cons:** Significantly higher memory allocations and slower runtime ($\sim 1\text{--}5\,\text{ms}$ per lookup); subject to floating-point matrix inversion inaccuracies that risk violating the strict $1 \cdot 10^{-9}$ tolerance gate.

### Sub-Decision D-3a — Tiebreak Serve Sequence Strategy:

| Sub-Option                                | Description                                                                                                   | Recommendation                                                |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **A1 — Exact Alternating Serve Sequence** | Model exact serve order ($A \rightarrow B B \rightarrow A A \rightarrow B B$) in tiebreak analytical formula. | ✅ **Proposed** (Ensures $1 \cdot 10^{-9}$ exactness)         |
| **A2 — Averaged Serve Probability**       | Use mean serve win probability $\bar{p} = \frac{p_A + (1-p_B)}{2}$ during tiebreaks.                          | ❌ Rejected (Introduces error $> 10^{-4}$, violating ADR-002) |

---

## D-4 — Wilson Score Uncertainty & Leverage Band Propagation Architecture (`src/core/leverage_uncertainty.py`)

**Status:** ✅ **Approved (Option A — Analytical Wilson Score Bounds + Direct Extreme Evaluation)**

**Deliverable:** `src/core/leverage_uncertainty.py` implementing Wilson interval computation for point-win probability $p$ and propagation to leverage confidence bands $[\Delta L_{\text{low}}, \Delta L_{\text{high}}]$ per ADR-005.

**Context & Constraints:**

- ADR-005 mandates attaching a Wilson confidence interval to $p$ based on sample size $N$ (stratum: player $\times$ surface $\times$ serve-number), propagating it through the solver to produce a **leverage confidence band** $[\Delta L_{\text{low}}, \Delta L_{\text{high}}]$, and band width $W_L = \Delta L_{\text{high}} - \Delta L_{\text{low}}$.
- Downstream nodes (`StateMonitorNode`) use band width to gate high-confidence alerts.

### Options:

#### Option A — Analytical Wilson Score Bounds + Direct Extreme Evaluation (Proposed ✅)

1. **Wilson Score Interval Calculation:**
   For observed point win rate $\hat{p} = \frac{k}{N}$ and confidence level $1-\alpha$ ($z = 1.95996$ for 95%):
   $$\tilde{p} = \frac{\hat{p} + \frac{z^2}{2N}}{1 + \frac{z^2}{N}}, \quad \text{margin} = \frac{z}{1 + \frac{z^2}{N}} \sqrt{\frac{\hat{p}(1-\hat{p})}{N} + \frac{z^2}{4N^2}}$$
   $$p_{\text{low}} = \max(0, \tilde{p} - \text{margin}), \quad p_{\text{high}} = \min(1, \tilde{p} + \text{margin})$$
2. **Direct Extreme Propagation:**
   Evaluate solver at boundary points $(p_{\text{low}}, p_{\text{high}})$ to obtain leverage bounds:
   $$\Delta L_{\text{low}} = \Delta L(s; p_{\text{low}}), \quad \Delta L_{\text{high}} = \Delta L(s; p_{\text{high}})$$
   $$W_L = \Delta L_{\text{high}} - \Delta L_{\text{low}}$$

_Trade-offs:_

- **Pros:** Completely deterministic, sub-millisecond execution ($< 20\,\mu\text{s}$), robust for small sample sizes ($N < 30$), zero random seed dependency.
- **Cons:** Assumes monotonicity of leverage with respect to $p$ (which holds true for monotonic tennis score functions).

#### Option B — Monte Carlo Sampling Over Beta Posterior Distribution

Sample 1,000 draws from Beta posterior distribution $\text{Beta}(k+1, N-k+1)$, pass each draw through `markov_solver.py`, and compute empirical 2.5% and 97.5% quantiles.

_Trade-offs:_

- **Pros:** Statistically non-parametric across arbitrary non-monotonic functions.
- **Cons:** Slower execution ($\sim 20\text{--}50\,\text{ms}$ per point), introduces stochastic noise, requires random seed configuration to pass deterministic tests.

---

## D-5 — CI-Blocking Solver Verification Suite & Combinatorial Coverage (`tests/unit/test_markov_solver.py`)

**Status:** ✅ **Approved (Single Valid Path)**

**Deliverable:** `tests/unit/test_markov_solver.py` with `@pytest.mark.solver` marker enforcing $1 \cdot 10^{-9}$ tolerance against textbook combinatorial formulas.

**Context & Constraints:**

- ADR-002: "A deviation between the solver and combinatorial probability theory is a build-breaking bug, not a tolerance to be loosened."
- Must execute cleanly in CI workflow `.github/workflows/ci.yml`.

**Verification Plan:**

- **Test Suite Structure:**
  1. **Game Level Golden Tests:**
     - $p = 0.5 \Rightarrow g(p) = 0.5$
     - $p = 0.6 \Rightarrow g(0.6) = 0.735728640000$
     - $p = 0.7 \Rightarrow g(0.7) = 0.900756020000$
  2. **Deuce Recurrence Golden Tests:** Verify deuce win probability matches $\frac{p^2}{p^2 + (1-p)^2}$ to within $1 \cdot 10^{-9}$.
  3. **Tiebreak Golden Tests:** Benchmark 7-point tiebreak outputs against independent combinatorial expansions.
  4. **Set & Match Golden Tests:** Verify set win probability for 6-0, 6-4, 7-6 states and match win probability for Best-of-3 and Best-of-5.
  5. **Leverage Symmetry Tests:** Verify $\Delta L(s) > 0$ for all non-terminal states and $\Delta L = 0$ for completed matches.
  6. **Tolerance Assertion Standard:** All tests use `pytest.approx(expected, abs=1e-9)`.

---

## D-6 — Operational Parameters & Stratum Threshold Configuration (`params.yaml`)

**Status:** ✅ **Approved (Option A — Hierarchical Structured YAML Config)**

**Deliverable:** Expand `params.yaml` with Phase 2 data, uncertainty, and solver parameters.

**Context & Constraints:**

- Project constitution §5: No hardcoded thresholds or magic numbers in Python source code — all source from `params.yaml`.

### Options:

#### Option A — Hierarchical Structured YAML Config (Proposed ✅)

Update `params.yaml` to include explicit Phase 2 configuration blocks:

```yaml
# PULSE Parameters Schema
thresholds:
  leverage_escalation: 0.10 # Leverage threshold to trigger PressureDiagnosticNode
  exploit_min_sample_size: 30 # Opponent minimum observation count for StrategyExploitNode

uncertainty:
  confidence_level: 0.95 # 95% Wilson score confidence interval (z = 1.95996)
  min_stratum_observations: 10 # Minimum observations to compute stratum-specific win rate

solver:
  tolerance: 1.0e-9 # Hard CI-blocking solver tolerance gate
  default_p_serve: 0.62 # Fallback point-win probability when stratum observations < min

ingestion:
  raw_data_dir: "data/raw"
  validated_data_dir: "data/validated"
  validated_file_name: "points.parquet"

latency:
  state_monitor_ms: 1000
  triggered_node_ms: 5000

models:
  calibration_method: "sigmoid"
  point_win_classifier: "logistic_regression"

ci:
  line_ceiling: 1000
  min_coverage_pct: 70
```

_Trade-offs:_ Clean logical grouping, 100% compliance with non-negotiable parameterization rule.

#### Option B — Flat Key Structure

Maintain all parameters in a flat unnested list under `params.yaml`.

_Trade-offs:_ Harder to maintain and read as phase parameters grow.

---

## D-7 — Raw Data Ingestion & DVC Pipeline Architecture (`dvc.yaml` & `scripts/ingest.py`)

**Status:** ✅ **Approved (Option A — Executable Python Ingest Script + Parquet Output)**

**Deliverable:** `scripts/ingest.py` and `dvc.yaml` stage definition for Phase 2 data ingestion and validation.

**Context & Constraints:**

- `dvc.yaml` currently has a placeholder `ingest` stage.
- Raw charted point-by-point data (Tennis Abstract format) must be ingested from `data/raw/`, validated via `pandera` `PointRecordSchema`, transformed, and saved to `data/validated/points.parquet`.

### Options:

#### Option A — Executable Python Ingest Script + Parquet Output (Proposed ✅)

1. Implement `scripts/ingest.py` to:
   - Read raw CSV files from `data/raw/`.
   - Coerce and validate columns using `PointRecordSchema.validate(df)`.
   - Log invalid/dropped rows using `src/utils/logger.py`.
   - Export validated dataset to `data/validated/points.parquet`.
2. Update `dvc.yaml`:

```yaml
stages:
  ingest:
    cmd: uv run python scripts/ingest.py
    deps:
      - data/raw
      - src/schemas/point_record.py
      - scripts/ingest.py
    params:
      - ingestion
    outs:
      - data/validated/points.parquet
```

_Trade-offs:_

- **Pros:** Full DVC reproducibility (`dvc repro`), fast binary columnar Parquet storage for Phase 3 ML model training, strict validation reporting via logger.
- **Cons:** Requires a sample CSV file placed in `data/raw/` for initial `dvc repro` run.

#### Option B — Direct In-Memory DataFrame Processing Without Intermediate Parquet Output

Pass raw CSV directly into training scripts in Phase 3 without writing an intermediate `data/validated/points.parquet` file.

_Trade-offs:_ Violates DVC modular pipeline design; requires re-running expensive schema validation on every model training run.

---

## 3. Summary of Approved Decisions & Implementation Baseline

All proposed architectural decisions have been formally approved by the user (2026-07-30). This establishes the authoritative technical baseline for Phase 2 implementation:

1. **D-1 (Specs):** Author written mathematical contracts in `reports/docs/specs/markov_solver_spec.md` and `reports/docs/specs/game_theory_spec.md`.
2. **D-2 (Schema):** Adopt **Option A** — Co-located Pydantic v2 domain model + `pandera` DataFrame schema in `src/schemas/point_record.py` with strict tennis score coercion (**Sub-decision D-2a: A1**).
3. **D-3 (Solver):** Adopt **Option A** — Direct hierarchical closed-form analytical formulas in `src/core/markov_solver.py` with exact alternating serve sequence in tiebreaks (**Sub-decision D-3a: A1**).
4. **D-4 (Uncertainty):** Adopt **Option A** — Analytical Wilson score bounds + direct extreme evaluation propagation in `src/core/leverage_uncertainty.py`.
5. **D-5 (Tests):** Implement `@pytest.mark.solver` CI-blocking golden-value unit tests in `tests/unit/test_markov_solver.py` enforcing $1 \cdot 10^{-9}$ tolerance.
6. **D-6 (Parameters):** Adopt **Option A** — Hierarchical structured YAML configuration in `params.yaml`.
7. **D-7 (Ingestion):** Adopt **Option A** — Executable `scripts/ingest.py` producing `data/validated/points.parquet` tracked via `dvc.yaml`.

---

_End of Phase 2 Implementation Plan & Decisions Document._
