# Phase 3 — Tier 1 ML Layer: Implementation Plan & Decisions

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Phase:** Phase 3 — Tier 1 ML Layer  
**Version:** 0.1.0  
**Date Created:** 2026-08-04  
**Status:** ✅ Approved (2026-08-04)

> **Purpose of this document.** This is the living design-decision record and technical implementation plan for Phase 3. It translates each deliverable from [`technical_roadmap.md` §Phase 3](../references/technical_roadmap.md) into concrete, actionable design choices with trade-off analysis. All decisions in this document have been reviewed and approved by the user (2026-08-04) and serve as the authoritative baseline for implementation and phase-close ADR review.
>
> **Governing invariants:** ADR-002 (solver is ground truth), ADR-003 (sufficiency gate), ADR-005 (Amended: Hierarchical Empirical Stratum Estimator + Wilson interval), ADR-006 (calibration method in config). Every decision below is downstream of these four; where a proposed option conflicts with any of them, the ADR governs.

---

## 1. Current State Audit

An honest, file-by-file inventory of every artifact in Phase 3 scope before any implementation begins. This audit drives the decision map in Section 2.

### 1.1 Deliverables Declared by the Roadmap

The roadmap (L74) declares four deliverables for Phase 3:

1. `models/point_win_classifier.py`
2. `models/pressure_deviation.py`
3. `core/leverage_uncertainty.py`
4. MLflow experiment log

### 1.2 File-by-File Inventory

| Artifact / File Path | State | Finding |
|---|---|---|
| `src/models/__init__.py` | Package stub exists (2 lines) | Docstring only. No imports, no exports. Ready to receive Phase 3 modules. |
| `src/models/point_win_classifier.py` | Does not exist | Pure blank. Must be created from scratch. |
| `src/models/pressure_deviation.py` | Does not exist | Pure blank. Must be created from scratch. |
| `src/core/leverage_uncertainty.py` | Implemented (205 lines) | Wilson-interval computation (`compute_wilson_interval`) and direct-extreme-evaluation propagation (`propagate_leverage_uncertainty`) are complete and tested per Phase 2 D-4. |
| `src/core/markov_solver.py` | Implemented (548 lines) | Closed-form solver is complete; CI-blocking tests pass at `< 1e-9` tolerance. This is the ground truth. Phase 3 must not touch its internals. |
| `src/schemas/point_record.py` | Implemented (207 lines) | Pydantic v2 `PointRecord` + Pandera `PointRecordSchema` complete. `surface`, `serve_number`, and `server_is_p1` identity fields present; these define the stratification key for the estimator. |
| `src/config/__init__.py` | Stub only (1 line) | Docstring only. No `params.yaml` loader is implemented. Phase 3 models must load thresholds from `params.yaml`; a loader is needed. |
| `src/utils/exceptions.py` | Implemented (92 lines) | `ModelInferenceError` already present and ready to use in Phase 3 model modules. |
| `params.yaml` | ✅ Updated (45 lines) | Updated with Phase 3 configuration keys (train/test split, random seed, experiment names, Beta shrinkage priors, `pressure_prior_min_players_per_bucket`, leverage buckets, and 4-tier fallback observation thresholds). |
| `dvc.yaml` | Stubs only | `train_classifier` and `train_pressure` stages exist but each contain `cmd: echo "Stage not yet implemented..."`. Must be replaced with real commands, deps, params, and outputs. |
| `artifacts/validated_data/points.parquet` | Exists (5.18 MB) | 547,478 MCP point records, validated against `PointRecordSchema`. This is the training corpus. |
| `tests/unit/test_leverage_uncertainty.py` | Implemented (57 lines) | Covers Wilson interval (sufficient and insufficient samples) and `propagate_leverage_uncertainty`. |
| `tests/unit/` (models) | No model test files | `test_point_win_classifier.py` and `test_pressure_deviation.py` to be implemented. |
| `tests/integration/` | Stub only (`__init__.py`) | `test_classifier_uncertainty_integration.py` to be added for Tier 1 model -> uncertainty band handoff. |
| `tests/evals/` | Stub only (`__init__.py`) | DeepEval groundedness check is Phase 4/5 scope. No action required in Phase 3. |
| `reports/specs/markov_solver_spec.md` | Exists (24.8 KB, v1.0.1+) | Mathematical spec is complete. Phase 3 does not modify it. |
| `reports/specs/game_theory_spec.md` | Exists (19.9 KB) | Phase 5 scope. No action in Phase 3. |
| `mlruns/` (MLflow tracking) | Not initialized | Local tracking URI `./mlruns/` to be created on first training run. |

### 1.3 Identified Latent Gaps & Risks

These are concrete findings from the audit that must be addressed before or alongside Phase 3 implementation.

#### Gap A — `leverage_uncertainty.py` Phase 3 Scope Ambiguity (Roadmap Item 4)

The roadmap (L70) states: *"Extend the Tier 2 Monte Carlo layer to propagate the `p` confidence interval through the Markov solver, producing a leverage confidence band rather than a point value."*

**What exists:** `propagate_leverage_uncertainty()` already produces a leverage confidence band via direct extreme evaluation. `leverage_low`, `leverage_high`, and `band_width` are all present in `LeverageBandResult`. This is the Phase 2 D-4 deliverable.

**The conflict:** The phrase "Tier 2 Monte Carlo layer" was the Phase 0 design intent. Phase 2 D-4 replaced Monte Carlo sampling with direct-extreme evaluation, which is analytically superior for a monotonic function (match-win probability is monotonically increasing in `p_serve`). The implemented approach already satisfies the roadmap's stated end-goal: a leverage confidence band, not a point value.

#### Gap B — `src/config/__init__.py` Has No Loader

`params.yaml` is the project's single source of truth for all thresholds (project constitution Section 5). The classifier and pressure model must load their parameters from `params.yaml`, not from hardcoded literals. A loader must be created in `src/config/`.

#### Gap C — `params.yaml` Is Incomplete for Phase 3

The following keys are needed by Phase 3 modules and are absent from the original 33-line `params.yaml`:

- `models.train_test_split` — holdout fraction for classifier evaluation
- `models.random_state` — reproducibility seed
- `models.mlflow_experiment_classifier` — MLflow experiment name (no magic strings)
- `models.mlflow_experiment_pressure` — MLflow experiment name for pressure model
- `models.pressure_prior_alpha` — Beta-distribution alpha prior for shrinkage
- `models.pressure_prior_beta` — Beta-distribution beta prior for shrinkage
- `models.pressure_prior_min_players_per_bucket` — Minimum players per bucket to fit MLE prior
- `models.pressure_leverage_buckets` — Ordered leverage bucket upper boundaries
- `uncertainty.min_player_observations` — Tier 1 fallback threshold
- `uncertainty.min_surface_observations` — Tier 2 fallback threshold

#### Gap D — `dvc.yaml` Stubs Must Be Promoted to Executable Stages

`train_classifier` and `train_pressure` are currently echo placeholder commands. They must be replaced with real `cmd`, `deps`, `params`, `outs`, and `metrics` entries. This is a mechanical consequence of Phase 3 implementation.

#### Gap E — No Stratum-Count Feature Exists in the Parquet Dataset

`artifacts/validated_data/points.parquet` contains individual point records, not pre-aggregated stratum counts. The classifier training code must compute per-player x surface x serve-number win-rate stratification and observation counts from the raw records. This aggregation logic does not exist yet.

---

## 2. Decision Map

Each Phase 3 deliverable maps to one primary decision. Sub-decisions are defined where a primary decision has meaningful internal branching.

| Decision ID | Deliverable / Component | Decision Title | Approved Status & Decision |
|---|---|---|---|
| **D-0** | `core/leverage_uncertainty.py` | Monte Carlo Extension vs. Phase 2 Direct-Extreme Evaluation | ✅ **Approved (Option A)** — Direct-extreme evaluation supersedes MC. Formally logged as ADR-005 Amendment 1. |
| **D-1** | `src/config/` | `params.yaml` Loader Location and Interface | ✅ **Approved (Single Path)** — `src/config/loader.py` returning typed Pydantic `Params` model. |
| **D-2** | `params.yaml` | Phase 3 Parameter Keys: Schema Extension | ✅ **Approved (Single Path)** — Extended schema with 11 parameters including fallback thresholds. |
| **D-3** | `src/models/point_win_classifier.py` | Feature Engineering & Stratification Architecture | ✅ **Approved (Option A + 4-Tier Hierarchical Fallback)** — Formally amends ADR-005 model class. |
| **D-3a** | `src/models/point_win_classifier.py` | Stratum Aggregation Ownership | ✅ **Approved (Option A1)** — Co-located inside `point_win_classifier.py` emitting `StratumTable`. |
| **D-4** | `core/leverage_uncertainty.py` | Wilson Interval Source | ✅ **Approved (Single Path)** — Training-time stratum table loaded at inference; no live cross-match state. |
| **D-5** | `src/models/pressure_deviation.py` | Empirical-Bayes Shrinkage Strategy | ✅ **Approved (Option B + Fallback)** — Data-driven MLE Beta prior per bucket + fallback threshold gate. |
| **D-5a** | `src/models/pressure_deviation.py` | Leverage Bucket Granularity | ✅ **Approved (Option A1)** — 3 buckets: `[0, 0.10)` Routine, `[0.10, 0.25)` Elevated, `[0.25, 1.0]` Critical. |
| **D-6** | MLflow experiment log | MLflow Tracking URI and Artifact Store Strategy | ✅ **Approved (Single Path)** — Local `./mlruns/` tracking; DVC tracks final build artifacts in `artifacts/models/`. |
| **D-7** | `dvc.yaml` | DVC Stage Architecture for Phase 3 Training | ✅ **Approved (Single Path)** — Real executable stages for `train_classifier` and `train_pressure`. |
| **D-8** | `tests/unit/`, `tests/integration/` | Test Coverage Strategy for Tier 1 Models | ✅ **Approved (Option B)** — Unit tests for each model + integration smoke test for classifier -> uncertainty handoff. |

---

## D-0 — Monte Carlo Extension vs. Phase 2 Direct-Extreme Evaluation: Scope Clarification

**Status:** ✅ **Approved (Option A)** — Formally logged as ADR-005 Amendment 1

### Context

The roadmap (L70) states: *"Extend the Tier 2 Monte Carlo layer to propagate the `p` confidence interval through the Markov solver, producing a leverage confidence band rather than a point value."*

Phase 2 D-4 (approved and implemented) chose direct extreme evaluation over Monte Carlo for propagating the Wilson interval through the solver. The reasoning: match-win probability is monotonic in `p_serve` (verified empirically during Phase 2 review), so evaluating the solver at `p_low` and `p_high` directly yields exact leverage band extremes without any sampling error. The implemented `LeverageBandResult` already carries `leverage_low`, `leverage_high`, and `band_width`.

The roadmap's "Tier 2 Monte Carlo layer" language predates Phase 2 D-4 and reflects Phase 0 design intent. The phrase "rather than a point value" — the actual stated goal — is already achieved by the existing implementation.

### Options & Comparative Trade-offs

| Approach | What It Does | When It Adds Value | Trade-off Analysis |
|---|---|---|---|
| **Option A — Confirm Phase 2 D-4 supersedes MC (Selected)** | Evaluates solver at $p_{\text{low}}$, $p_{\text{hat}}$, and $p_{\text{high}}$; takes min/max as the band. | Always valid for PULSE's in-process solver. Exact analytics. | **Pro:** Zero stochastic variance, no sampling error, fully consistent with ADR-002.<br>**Con:** Requires explicit decision log entry acknowledging roadmap supersession. |
| **Option B — Add Monte Carlo sampling path as config-gated alternative** | Draws $N$ samples from Wilson posterior over $p$; propagates each through solver; takes percentile band. | Adds value if solver mapping is non-monotonic or distribution is highly asymmetric. | **Pro:** Independent validation of direct-extreme band.<br>**Con:** Introduces sampling error into an exact system; adds unnecessary code surface. |

### Final Approved Decision

**Option A is selected and approved.** Direct extreme evaluation is strictly more precise than Monte Carlo sampling for a monotonic solver. Adding Monte Carlo sampling would be adding worse math alongside better math for no reason. 

**Documentation Action:** Logged as **ADR-005 Amendment 1** in `reports/docs/architecture/system_design.md`.

---

## D-1 — `params.yaml` Loader Location and Interface

**Status:** ✅ **Approved (Single Valid Path)**

### Context

Multiple Phase 3 modules need to read `params.yaml` keys. The project constitution (Section 5) forbids hardcoded thresholds. `src/config/__init__.py` is a stub with no loader. A loader must exist before model training scripts are written.

### Final Approved Decision

Implement a `load_params()` function in **`src/config/loader.py`** (new file). The function must:

1. Accept an optional `config_path: Path` override; default to the repository root's `params.yaml` (resolved relative to `__file__`).
2. Return a typed Pydantic `BaseModel` (`Params`) wrapping the full `params.yaml` structure — not a raw `dict`, per the project constitution's Tool I/O rule (Section 5).
3. Be re-exported from `src/config/__init__.py` so importers use `from src.config import load_params`.

---

## D-2 — `params.yaml` Phase 3 Parameter Schema Extension

**Status:** ✅ **Approved (Single Valid Path)**

### Context

Gap C (Section 1.3) identified parameter blocks needed for Phase 3 models and fallback logic. All must be added before any model code is written, per the "no magic numbers" invariant.

### Final Approved Decision & Parameter Schema

`params.yaml` has been updated with the following complete parameter structure:

```yaml
uncertainty:
  confidence_level: 0.95          # 95% Wilson score confidence interval (z = 1.95996) per ADR-005
  min_stratum_observations: 10   # Tier 0: Minimum observations for exact (player, surface, serve_number)
  min_player_observations: 20     # Tier 1: Minimum observations for overall player serve rate
  min_surface_observations: 50    # Tier 2: Minimum observations for population surface serve rate
  default_fallback_margin: 0.15   # +/- margin around default_p when falling back to Tier 3

models:
  calibration_method: "sigmoid"   # Required: "sigmoid" for LogisticRegression v1; "isotonic" for LightGBM v2 (ADR-006)
  point_win_classifier: "hierarchical_stratum_estimator" # Amended ADR-005 estimator class
  solver_tolerance: 1.0e-9        # Compatibility alias for solver tolerance
  train_test_split: 0.20          # Holdout fraction for classifier evaluation
  random_state: 42                # Reproducibility seed for train/test split and model fit
  mlflow_experiment_classifier: "pulse_point_win_classifier_v1"
  mlflow_experiment_pressure: "pulse_pressure_deviation_v1"

  # Empirical-Bayes Shrinkage Priors & Fallback Thresholds (Pressure Deviation Model)
  pressure_prior_alpha: 2.0       # Fallback Beta prior alpha (weak 4-observation prior)
  pressure_prior_beta: 2.0        # Fallback Beta prior beta
  pressure_prior_min_players_per_bucket: 15 # Minimum players in bucket required to fit MLE prior

  # Leverage bucket upper boundaries (exclusive). Partition for per-bucket pressure deviation estimation.
  # [0.10, 0.25] produces 3 buckets: [0, 0.10) Routine, [0.10, 0.25) Elevated, [0.25, 1.0] Critical.
  pressure_leverage_buckets: [0.10, 0.25]
```

---

## D-3 — Feature Engineering & Stratification Architecture for the Point-Win Classifier

**Status:** ✅ **Approved (Option A + 4-Tier Hierarchical Fallback)** — Formally amends ADR-005

### Context

The point-win classifier must be trained from `artifacts/validated_data/points.parquet`. The target variable is `point_winner == "server"` (binary).

ADR-005 originally stated: *"Retain `LogisticRegression` + `CalibratedClassifierCV` as the v1 point-win probability model."* The core question is whether to train a global LogisticRegression model or build a player-stratified empirical rate estimator.

### Options & Comparative Trade-offs

| Option | Description | Pros | Cons |
|---|---|---|---|
| **Option A — Stratum-Rate Aggregation (Selected)** | Per-player x surface x serve-number observed win rate $k/N$. Serves as direct $p_{\text{hat}}$ for Wilson interval. | • Direct semantic alignment with ADR-005 Wilson sizing.<br>• Zero risk of score-context feature leakage (`break_point`, etc.).<br>• Zero inference latency (dict/Parquet lookup). | • Sparse strata require fallback strategy.<br>• Replaces `LogisticRegression` model class (requires formal ADR-005 amendment). |
| **Option B — Global Logistic Regression Classifier** | Single `LogisticRegression` model on all 547k records with surface, serve_number, and encoded player features. | • Literally matches roadmap text.<br>• Captures cross-stratum signals (e.g. surface specialization). | • Non-trivial player encoding.<br>• Wilson interval still requires separate stratum counts.<br>• Risk of feature leakage. |
| **Option C — Hybrid Smoother** | Compute stratum rate as feature, train LogisticRegression to smooth/blend. | • Retains sklearn pipeline pattern.<br>• Avoids raw player-ID encoding. | • Linear logistic regression adds trivial linear blending.<br>• Requires dual artifacts (table + pipeline). |

### Final Approved Decision & Hierarchical Fallback Extension

**Option A is selected and approved**, with a crucial **4-Tier Hierarchical Fallback** extension.

**ADR-005 Amendment Rationale:** A `LogisticRegression` with full interaction terms ($\text{player} \times \text{surface} \times \text{serve\_number}$) converges toward empirical stratum rates with L2 regularization acting as an implicit prior. Choosing Option A is a technical correction that replaces L2 regularization with explicit Empirical-Bayes shrinkage (D-5) and Wilson intervals (D-4).

#### 4-Tier Hierarchical Fallback Resolution Strategy
To prevent dropping straight from a sparse stratum to a flat global constant (`default_p_serve`), queries for player $P$, surface $S$, and serve number $N_{\text{serve}}$ resolve through a 4-tier hierarchy:

1. **Tier 0 (Exact Stratum Rate):** If $N_{(P, S, N_{\text{serve}})} \ge \text{min\_stratum\_observations}$ (10), return exact stratum win rate $k/N$ and sample size $N$.
2. **Tier 1 (Player Overall Rate):** Else if $N_{(P, N_{\text{serve}})} \ge \text{min\_player\_observations}$ (20), return player's overall win rate across all surfaces for that serve number.
3. **Tier 2 (Population Surface Rate):** Else if $N_{(S, N_{\text{serve}})} \ge \text{min\_surface\_observations}$ (50), return population-wide win rate for surface $S$ and serve number $N_{\text{serve}}$.
4. **Tier 3 (Global Default):** Else, return `solver.default_p_serve` (0.62) with `default_fallback_margin` (0.15).

Every inference output carries an explicit `fallback_tier: int` (0–3) to ensure complete data provenance tracking.

---

## D-3a — Stratum Aggregation Ownership

**Status:** ✅ **Approved (Option A1)**

### Options

- **Option A1 (Selected): Co-located inside `point_win_classifier.py`.** The module owns both aggregation and inference lookup, exporting a Pydantic `StratumTable` model written to `artifacts/models/point_win_classifier/stratum_table.parquet`.
- **Option A2: Dedicated script `scripts/build_stratum_table.py`.** Separate DVC pre-processing step.

**Final Approved Decision:** Option A1 is selected. Co-location is natural since the stratum table *is* the estimator artifact under Option A.

---

## D-4 — Wilson Interval Data Provenance

**Status:** ✅ **Approved (Single Valid Path)**

### Decision

Stratum observation counts $(k, N)$ are sourced from the **training-time `StratumTable` artifact** at inference time. `StateMonitorNode` looks up the server's stratum counts from the loaded artifact and passes them to `propagate_leverage_uncertainty()`. No live cross-match memory is maintained, respecting project constitution §6 ("short-term per-match session memory only").

---

## D-5 — Empirical-Bayes Shrinkage Estimator Implementation Strategy

**Status:** ✅ **Approved (Option B + Sparse-Bucket Fallback Gate)**

### Context

The roadmap mandates an Empirical-Bayes shrinkage estimator for player pressure performance deviations across leverage buckets.

### Options & Comparative Trade-offs

| Option | Description | Pros | Cons |
|---|---|---|---|
| **Option A — Fixed Beta Prior Conjugate Shrinkage** | Uses fixed `Beta(alpha_0, beta_0)` prior from config for all players. | • Closed-form, simple.<br>• Analytical credible intervals. | • Prior is static config, not estimated empirically from population data. |
| **Option B — Empirical-Bayes Pooled Prior (Selected)** | Estimates $(\alpha_0, \beta_0)$ prior per leverage bucket from population distribution using MLE (method of moments). | • Statistically precise "Empirical Bayes".<br>• Adaptive to population distribution per bucket. | • Requires MLE optimization.<br>• Sparse buckets cause unstable MLE priors. |

### Final Approved Decision & Sparse-Bucket Fallback Gate

**Option B is selected and approved**, with a mandatory **Sparse-Bucket Fallback Gate**.

1. **MLE Prior Fitting:** For each leverage bucket, fit population prior parameters $(\alpha_0, \beta_0)$ from observed serve-win rates across all players in that bucket using method of moments.
2. **Sparse-Bucket Fallback Gate:** If the number of players with observations in a leverage bucket is $< \text{models.pressure_prior_min_players_per_bucket}$ (15), the MLE optimization is bypassed and the fixed prior `Beta(pressure_prior_alpha, pressure_prior_beta)` from `params.yaml` is used instead. The output flags `is_prior_estimated: bool`.
3. **Beta-Binomial Posterior Update:** For each player and leverage bucket:
   $$\alpha_{\text{post}} = \alpha_0 + k_{\text{pressure}}, \quad \beta_{\text{post}} = \beta_0 + N_{\text{pressure}} - k_{\text{pressure}}$$
   $$\text{shrunk\_rate} = \frac{\alpha_{\text{post}}}{\alpha_{\text{post}} + \beta_{\text{post}}}, \quad \text{pressure\_deviation} = \text{shrunk\_rate} - p_{\text{baseline}}$$
4. **Sufficiency Gate:** 90% credible intervals are extracted from the Beta posterior percentiles (5th to 95th). Credible interval width automatically widens as $N_{\text{pressure}}$ decreases, fulfilling ADR-003 and addressing the fairness concern by structure rather than prose.

---

## D-5a — Leverage Bucket Granularity

**Status:** ✅ **Approved (Option A1)**

### Options

- **Option A1 (Selected): 3 Buckets — Routine / Elevated / Critical.** `[0, 0.10)` Routine, `[0.10, 0.25)` Elevated, `[0.25, 1.0]` Critical.
- **Option A2: 2 Buckets — Below-Threshold / Above-Threshold.** `[0, 0.10)` vs `[0.10, 1.0]`.

**Final Approved Decision:** Option A1 is selected. Aligns the first boundary with `thresholds.leverage_escalation` (0.10) and preserves coaching-relevant distinctions. Expectation noted: the `[0.25, 1.0]` bucket will likely trigger the fixed-prior fallback gate due to point rarity in historical charting, which is handled gracefully by D-5's fallback design.

---

## D-6 — Local MLflow Tracking & DVC Build Artifact Boundary

**Status:** ✅ **Approved (Single Valid Path)**

- **MLflow:** Logs experiment runs, parameters, calibration curves (PNG), AUC, and shrinkage coverage metrics to local `./mlruns/` (`.gitignore` enforced).
- **DVC:** Tracks final production build artifacts (`artifacts/models/point_win_classifier/` and `artifacts/models/pressure_deviation/`) for pipeline reproducibility.

---

## D-7 — DVC Stage Architecture for Phase 3 Training

**Status:** ✅ **Approved (Single Valid Path)**

Replace placeholder stages in `dvc.yaml` with executable commands:
- `train_classifier`: executes `scripts/train_classifier.py`, outputs `artifacts/models/point_win_classifier/` and `artifacts/metrics/classifier_metrics.json`.
- `train_pressure`: executes `scripts/train_pressure.py`, depends on classifier stratum table, outputs `artifacts/models/pressure_deviation/` and `artifacts/metrics/pressure_metrics.json`.

---

## D-8 — Test Suite Architecture (Unit + Integration Smoke Test)

**Status:** ✅ **Approved (Option B)**

### Options

- **Option A: Unit Tests Only.** `test_point_win_classifier.py` and `test_pressure_deviation.py`.
- **Option B (Selected): Unit Tests + Integration Smoke Test.** Adds `tests/integration/test_classifier_uncertainty_integration.py`.

**Final Approved Decision:** Option B is selected. The integration smoke test runs synthetic point records end-to-end through stratum aggregation → `propagate_leverage_uncertainty()` → `LeverageBandResult` validation, serving as cheap insurance against cross-phase schema mismatches.

---

## 3. Implementation Sequence

1. **`src/config/loader.py`** — Implement typed `Params` loader (reads updated `params.yaml`).
2. **`src/models/point_win_classifier.py`** — Implement 4-tier Hierarchical Empirical Stratum Estimator and `StratumTable` artifact builder.
3. **`scripts/train_classifier.py`** & `dvc.yaml` update — Run stratum aggregation pipeline, log metrics to MLflow.
4. **`src/models/pressure_deviation.py`** — Implement Empirical-Bayes Beta-Binomial shrinkage estimator with sparse-bucket fallback.
5. **`scripts/train_pressure.py`** & `dvc.yaml` update — Run pressure model pipeline, log metrics to MLflow.
6. **Unit & Integration Tests** — Add `test_point_win_classifier.py`, `test_pressure_deviation.py`, and `test_classifier_uncertainty_integration.py`.
7. **Verification & Quality Gate** — Run `uv run pytest`, `uv run ruff check .`, `uv run pyright`, `python scripts/check_file_size.py`, and `uv run dvc repro`.
