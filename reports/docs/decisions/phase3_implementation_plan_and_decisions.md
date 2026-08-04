# Phase 3 — Tier 1 ML Layer: Implementation Plan & Decisions

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)
**Phase:** Phase 3 — Tier 1 ML Layer
**Version:** 0.1.0
**Date Created:** 2026-08-04
**Status:** Awaiting User Approval

> **Purpose of this document.** This is the living design-decision record and technical implementation plan for Phase 3. It translates each deliverable from `technical_roadmap.md` Phase 3 into concrete, actionable design choices with trade-off analysis. All decisions marked **[User Input Required]** must be explicitly approved before implementation begins. Decisions marked **[Single Valid Path]** are recorded for completeness; there is unequivocally one correct option given the project invariants.
>
> **Governing invariants:** ADR-002 (solver is ground truth), ADR-003 (sufficiency gate), ADR-005 (calibrated LR + Wilson interval), ADR-006 (calibration method in config). Every decision below is downstream of these four; where a proposed option conflicts with any of them, the ADR governs.

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
| `src/core/leverage_uncertainty.py` | Implemented (205 lines) | Wilson-interval computation (`compute_wilson_interval`) and direct-extreme-evaluation propagation (`propagate_leverage_uncertainty`) are complete and tested. See latent gap 1.3.A below. |
| `src/core/markov_solver.py` | Implemented (548 lines) | Closed-form solver is complete; CI-blocking tests pass at `< 1e-9` tolerance. This is the ground truth. Phase 3 must not touch its internals. |
| `src/schemas/point_record.py` | Implemented (207 lines) | Pydantic v2 `PointRecord` + Pandera `PointRecordSchema` complete. `surface`, `serve_number`, and `server_is_p1` identity fields present; these define the stratification key for the classifier. |
| `src/config/__init__.py` | Stub only (1 line) | Docstring only. No `params.yaml` loader is implemented. Phase 3 models must load thresholds from `params.yaml`; a loader is needed. See 1.3.B. |
| `src/utils/exceptions.py` | Implemented (92 lines) | `ModelInferenceError` already present and ready to use in Phase 3 model modules. |
| `params.yaml` | Partial (33 lines) | Has `models.calibration_method = "sigmoid"` and `models.point_win_classifier = "logistic_regression"`. Missing: train/test split ratio, MLflow experiment names, pressure deviation shrinkage prior parameters, leverage bucket definitions. See 1.3.C. |
| `dvc.yaml` | Stubs only | `train_classifier` and `train_pressure` stages exist but each contain `cmd: echo "Stage not yet implemented..."`. Must be replaced with real commands, deps, params, and outputs. |
| `artifacts/validated_data/points.parquet` | Exists (5.18 MB) | 547,478 MCP point records, validated against `PointRecordSchema`. This is the training corpus. |
| `tests/unit/test_leverage_uncertainty.py` | Implemented (57 lines) | Covers Wilson interval (sufficient and insufficient samples) and `propagate_leverage_uncertainty`. No Phase 3 model tests yet. |
| `tests/unit/` (models) | No model test files | `test_point_win_classifier.py` and `test_pressure_deviation.py` do not exist. |
| `tests/integration/` | Stub only (`__init__.py`) | No integration test file exists. Phase 3 should include a classifier -> uncertainty band smoke test here. |
| `tests/evals/` | Stub only (`__init__.py`) | DeepEval groundedness check is Phase 4/5 scope. No action required in Phase 3. |
| `reports/specs/markov_solver_spec.md` | Exists (24.8 KB, v1.0.1+) | Mathematical spec is complete. Phase 3 does not modify it. |
| `reports/specs/game_theory_spec.md` | Exists (19.9 KB) | Phase 5 scope. No action in Phase 3. |
| `mlruns/` (MLflow tracking) | Not initialized | No MLflow tracking URI configured. MLflow is in `pyproject.toml` but has not been invoked. The first `mlflow.start_run()` call will create `./mlruns/` locally. |

### 1.3 Identified Latent Gaps & Risks

These are concrete findings from the audit that must be addressed before or alongside Phase 3 implementation.

#### Gap A — `leverage_uncertainty.py` Phase 3 Scope Ambiguity (Roadmap Item 4)

The roadmap (L70) states: *"Extend the Tier 2 Monte Carlo layer to propagate the `p` confidence interval through the Markov solver, producing a leverage confidence band rather than a point value."*

**What exists:** `propagate_leverage_uncertainty()` already produces a leverage confidence band via direct extreme evaluation. `leverage_low`, `leverage_high`, and `band_width` are all present in `LeverageBandResult`. This is the Phase 2 D-4 deliverable.

**The conflict:** The phrase "Tier 2 Monte Carlo layer" was the Phase 0 design intent. Phase 2 D-4 replaced Monte Carlo sampling with direct-extreme evaluation, which is analytically superior for a monotonic function (match-win probability is monotonically increasing in `p_serve`). The implemented approach already satisfies the roadmap's stated end-goal: a leverage confidence band, not a point value.

**Decision required (D-0):** Confirm whether "Monte Carlo layer" is an outdated Phase 0 artifact superseded by D-4, or whether a Monte Carlo sampling path is still expected in addition to the direct-extreme approach.

#### Gap B — `src/config/__init__.py` Has No Loader

`params.yaml` is the project's single source of truth for all thresholds (project constitution Section 5). The classifier and pressure model must load their parameters from `params.yaml`, not from hardcoded literals. A loader must be created in `src/config/`.

#### Gap C — `params.yaml` Is Incomplete for Phase 3

The following keys are needed by Phase 3 modules and are absent from the current 33-line `params.yaml`:

- `models.train_test_split` — holdout fraction for classifier evaluation
- `models.random_state` — reproducibility seed
- `models.mlflow_experiment_classifier` — MLflow experiment name (no magic strings)
- `models.mlflow_experiment_pressure` — MLflow experiment name for pressure model
- `models.pressure_prior_alpha` — Beta-distribution alpha prior for shrinkage
- `models.pressure_prior_beta` — Beta-distribution beta prior for shrinkage
- `models.pressure_leverage_buckets` — Ordered leverage bucket upper boundaries

#### Gap D — `dvc.yaml` Stubs Must Be Promoted to Executable Stages

`train_classifier` and `train_pressure` are currently echo placeholder commands. They must be replaced with real `cmd`, `deps`, `params`, `outs`, and `metrics` entries. This is a mechanical consequence of Phase 3 implementation.

#### Gap E — No Stratum-Count Feature Exists in the Parquet Dataset

`artifacts/validated_data/points.parquet` contains individual point records, not pre-aggregated stratum counts. The classifier training code must compute per-player x surface x serve-number win-rate stratification and observation counts from the raw records. This aggregation logic does not exist yet.

---

## 2. Decision Map

Each Phase 3 deliverable maps to one primary decision. Sub-decisions are defined where a primary decision has meaningful internal branching.

| Decision ID | Deliverable / Component | Decision Title | Decision Type |
|---|---|---|---|
| D-0 | `core/leverage_uncertainty.py` | Monte Carlo Extension vs. Phase 2 Direct-Extreme Evaluation: Scope Clarification | [User Input Required] |
| D-1 | `src/config/` | `params.yaml` Loader Location and Interface | [Single Valid Path] |
| D-2 | `params.yaml` | Phase 3 Parameter Keys: Schema Extension | [Single Valid Path] |
| D-3 | `src/models/point_win_classifier.py` | Feature Engineering and Stratification Architecture | [User Input Required] |
| D-3a | `src/models/point_win_classifier.py` | Stratum Aggregation Ownership | [User Input Required — contingent on D-3] |
| D-4 | `core/leverage_uncertainty.py` | Wilson Interval Source: Classifier-Computed vs. Upstream Stratum Count | [Single Valid Path] |
| D-5 | `src/models/pressure_deviation.py` | Empirical-Bayes Shrinkage Estimator Implementation Strategy | [User Input Required] |
| D-5a | `src/models/pressure_deviation.py` | Leverage Bucket Definition and Granularity | [User Input Required — contingent on D-5] |
| D-6 | MLflow experiment log | MLflow Tracking URI and Artifact Store Strategy | [Single Valid Path] |
| D-7 | `dvc.yaml` | DVC Stage Architecture for Phase 3 Training | [Single Valid Path] |
| D-8 | `tests/unit/`, `tests/integration/` | Test Coverage Strategy for Tier 1 Models | [User Input Required] |

---

## D-0 — Monte Carlo Extension vs. Phase 2 Direct-Extreme Evaluation: Scope Clarification

**Status: [User Input Required]**

### Context

The roadmap (L70) states: *"Extend the Tier 2 Monte Carlo layer to propagate the `p` confidence interval through the Markov solver, producing a leverage confidence band rather than a point value."*

Phase 2 D-4 (approved and implemented) chose direct extreme evaluation over Monte Carlo. The reasoning: match-win probability is monotonic in `p_serve` (verified empirically during Phase 2 review), so evaluating the solver at `p_low` and `p_high` directly yields exact leverage band extremes without any sampling error. The implemented `LeverageBandResult` already carries `leverage_low`, `leverage_high`, and `band_width`.

The roadmap's "Tier 2 Monte Carlo layer" language predates Phase 2 D-4 and reflects Phase 0 design intent. The phrase "rather than a point value" — the actual stated goal — is already achieved by the existing implementation.

### What Genuinely Differs Between Approaches

| Approach | What It Does | When It Adds Value |
|---|---|---|
| Direct Extreme Evaluation (Phase 2 D-4, implemented) | Evaluates solver at p_low, p_hat, and p_high; takes min/max as the band. Exact for monotonic solver. No approximation error. | Always valid for PULSE's in-process solver. |
| Monte Carlo Sampling | Draws N samples from the Wilson posterior over p; propagates each through the solver; computes a percentile band. | Adds value when the mapping from p to leverage is non-monotonic (it is not for this solver), or when the p distribution is highly asymmetric and band endpoints are not sufficient summaries. |

### Options

**Option A — Confirm Phase 2 D-4 supersedes the roadmap's Monte Carlo clause (no new code).**

The existing `propagate_leverage_uncertainty()` already produces a leverage band. Phase 3's `core/leverage_uncertainty.py` deliverable is satisfied by confirming and documenting this substitution. The only actions are: adding an explicit note in the module docstring and adding an ADR amendment to `system_design.md`.

- Pro: No additional code; no approximation error introduced; fully consistent with ADR-002 (exact solver is ground truth).
- Con: The roadmap text is not literally implemented; requires an explicit decision log entry acknowledging the deviation.

**Option B — Add a Monte Carlo sampling path as an optional, config-gated alternative.**

Implement a second function `propagate_leverage_uncertainty_mc()` that draws from the Wilson posterior and produces a sampled band. The existing direct-extreme path remains the default.

- Pro: Provides an independent validation of the direct-extreme band.
- Con: Adds code and test surface for a path not needed for correctness; introduces sampling approximation error into a system whose value proposition is exactness; risks scope creep.

> **Recommendation: Option A.** The direct-extreme method is strictly more precise than Monte Carlo for this solver. Adding Monte Carlo sampling would be adding worse math alongside better math. The correct action is to log the supersession in `system_design.md` as an ADR amendment to ADR-005, update the module docstring, and close this roadmap item. **No new functional code is needed for this deliverable.**

---

## D-1 — `params.yaml` Loader Location and Interface

**Status: [Single Valid Path]**

### Decision

Implement a `load_params()` function in **`src/config/loader.py`** (new file). The function must:

1. Accept an optional `config_path: Path` override; default to the repository root's `params.yaml` (resolved relative to `__file__`).
2. Return a **typed Pydantic `BaseModel`** wrapping the full `params.yaml` structure — not a raw `dict`, per the project constitution's Tool I/O rule (Section 5).
3. Be re-exported from `src/config/__init__.py` so importers use `from src.config import load_params`.

**Why this is the only valid path:**

- `src/utils/` is for cross-cutting infrastructure (exceptions, logging). Configuration loading is a domain responsibility; it belongs in `src/config/`.
- Returning a raw `dict` violates the "every module boundary must validate input/output via Pydantic BaseModel" rule.
- A global module-level singleton (`PARAMS = load_params()` at import time) makes tests that need different parameter values difficult to write without monkeypatching.
- The Pydantic model wrapping `params.yaml` provides a schema validation safety net: if a required key is missing, `ValidationError` fires at load time, not deep in a training loop.

---

## D-2 — `params.yaml` Phase 3 Parameter Schema Extension

**Status: [Single Valid Path]**

### Decision

Add the following keys to `params.yaml` under the `models:` namespace. Values shown are justified starting points; they are not calibrated final values and may be updated after initial training runs without a new decision entry.

```yaml
models:
  # Existing (Phase 2 — do not change):
  calibration_method: "sigmoid"
  point_win_classifier: "logistic_regression"

  # Phase 3 additions:
  train_test_split: 0.20           # Holdout fraction for classifier AUC evaluation
  random_state: 42                 # Reproducibility seed for train/test split and model fit
  mlflow_experiment_classifier: "pulse_point_win_classifier_v1"
  mlflow_experiment_pressure: "pulse_pressure_deviation_v1"

  # Empirical-Bayes shrinkage priors for Pressure Deviation model (Beta distribution).
  # Beta(2, 2) encodes a weak symmetric prior centred at 0.5; adjust post-calibration.
  pressure_prior_alpha: 2.0
  pressure_prior_beta: 2.0

  # Leverage bucket upper boundaries (exclusive). Defines the partition for per-bucket
  # pressure deviation estimation. Must align with thresholds.leverage_escalation.
  # [0.10, 0.25] produces 3 buckets: [0, 0.10), [0.10, 0.25), [0.25, 1.0].
  pressure_leverage_buckets: [0.10, 0.25]
```

**Rationale for each value:**

- `train_test_split: 0.20` — Standard 80/20 split; sufficient holdout given 547k records (~110k test points with comfortable AUC stability).
- `random_state: 42` — Conventional fixed seed; reproducibility requires it to be explicit, not an implicit runtime default.
- MLflow experiment names — No magic strings in code; changing the experiment name is a config-file change, not a code change.
- `pressure_prior_alpha/beta: 2.0` — A symmetric Beta(2,2) prior gives a weak pull toward a 0.5 win-rate; equivalent to 4 pseudo-observations. Intentionally uninformative; will be revisited once real shrinkage intervals are validated against the 90% coverage criterion.
- `pressure_leverage_buckets: [0.10, 0.25]` — The lower boundary (0.10) matches `thresholds.leverage_escalation` (the trigger for `PressureDiagnosticNode`). Keeping them aligned is intentional: pressure deviation is only interpreted in the context of a leverage-escalation decision.

---

## D-3 — Feature Engineering and Stratification Architecture for the Point-Win Classifier

**Status: [User Input Required]**

### Context

The point-win classifier (`LogisticRegression` + `CalibratedClassifierCV(method='sigmoid')` per ADR-005/ADR-006) must be trained from `artifacts/validated_data/points.parquet`. The target variable is `point_winner == "server"` (binary).

**Constraint from ADR-005:** The classifier produces `p` — the per-point serve-win probability used as the sole ML input to the Markov solver. The solver amplifies errors in `p` through a nested Markov chain; a poorly specified feature set will degrade all downstream leverage estimates.

**Constraint from Phase 4:** `StateMonitorNode` will call the classifier in real time, per-point, within the `< 1s` latency budget. Features that require complex real-time computation at inference time are a latency risk.

**The core architectural question:** Should the classifier be a population-level global model trained on all players with player identity as a feature, or a player-stratified aggregation computing per-player x surface x serve-number win-rate statistics that feed the Wilson interval directly?

### Options

**Option A — Stratum-Rate Aggregation (Per-Player x Surface x Serve-Number Win Rate)**

Each stratum `(server_id, surface, serve_number)` computes an observed win rate `k/N`. That rate is the `p_hat` input to the Wilson interval. The "classifier artifact" is a stratum lookup table (a validated Parquet or dict).

Pros:
- Direct semantic alignment with ADR-005: `p` is the observed serve-win rate for that stratum — no translation layer.
- No risk of a learned model encoding score-context features (`break_point`, `set_point`, `match_point`) that are in-game state. Including such features would create circularity: the solver computes probabilities conditioned on that same state.
- Zero inference latency: stratum lookup is a dict/DataFrame get.
- The Sufficiency Gate and fairness concern (project constitution Section 7) are handled automatically: strata with low N receive wide Wilson intervals, not confident point estimates.

Cons:
- Sparse strata (infrequently charted players) fall back to `solver.default_p_serve` from `params.yaml`. Coverage depends on how well-charted the players are in the MCP dataset.
- Does not leverage potentially discriminatory features like `tournament_level`.
- The roadmap explicitly names `LogisticRegression` + `CalibratedClassifierCV` — this option does not train a classifier in the usual sklearn sense. Requires explicit sign-off.

**Option B — Global Logistic Regression Classifier with Stratum Features**

Train a single `LogisticRegression` model on all 547k point records. Features: `surface` (one-hot), `serve_number` (binary), and player-level statistics as numeric features. Calibrate with `CalibratedClassifierCV(method='sigmoid')`.

Pros:
- Literally matches the roadmap's stated implementation: `LogisticRegression` + `CalibratedClassifierCV`.
- Can encode cross-stratum signal (e.g., hard-court specialists performing differently on clay).
- MLflow experiment tracking is unambiguous: the artifact is a trained sklearn pipeline.

Cons:
- Player encoding strategy is non-trivial: raw player-ID categoricals have thousands of levels, requiring either target encoding (leak risk on holdout) or pre-computed player features.
- The Wilson interval must still be tied to stratum observation counts, requiring stratum counts as a separate side artifact of training.
- Score-context features (`break_point`, `set_point`, `match_point`) must be explicitly excluded — they encode the match state the solver is conditioned on; including them creates circularity.
- Logistic regression on a mix of categorical and numeric player features requires careful column transformer design.

**Option C — Hybrid: Stratum-Rate as Feature + Logistic Regression as Calibrated Smoother**

Compute per-stratum win rates as a feature (`stratum_serve_rate`), then train logistic regression on `[stratum_serve_rate, surface (one-hot), serve_number]`. The model's role is to smooth and calibrate across strata.

Pros:
- Retains the `LogisticRegression` + `CalibratedClassifierCV` sklearn pattern literally.
- Avoids the player-ID encoding problem.

Cons:
- The model adds a layer of indirection that may provide little marginal value over the raw stratum rate (logistic regression's linearity means the "smoothing" is trivially linear blending).
- Inference requires the stratum rate at inference time, meaning the stratum table must be stored as a model artifact and loaded alongside the sklearn pipeline.

> **Recommendation: Option A.** The project constitution's Brain/Brawn boundary rule has a structural analogue for the classifier: do not use a trained model to approximate something already exactly computable from the data. The stratum serve-win rate is directly observable from `points.parquet`; the Wilson interval is the statistically principled way to express uncertainty over it. A logistic regression on top of that rate adds a learned layer whose only contribution is to blend adjacent strata — a task better handled by the empirical-Bayes shrinkage in the Pressure Deviation model (D-5). **This requires explicit user sign-off before proceeding.**

---

## D-3a — Stratum Aggregation Ownership (Contingent on D-3)

**Status: [User Input Required — contingent on D-3]**

### Context

Regardless of which D-3 option is chosen, the stratum aggregation step (computing `k`, `N`, and `p_hat` per `(server_id, surface, serve_number)` from `points.parquet`) must live somewhere. Its placement determines how it fits into the DVC pipeline and how inference at runtime accesses stratum counts.

### Options

**Option A1 — Inside `point_win_classifier.py`** (co-located with the aggregation/model logic)

The module owns both the aggregation step and the Wilson interval computation. It exposes a `StratumTable` Pydantic model as its primary artifact.

- Pro: Single module owns the full "how do we produce `p` and `(k, N)` from data" responsibility. Clean training-to-inference handoff within one import.
- Con: `point_win_classifier.py` becomes a hybrid training + inference module; must remain under 1,000 lines.

**Option A2 — As a separate DVC pre-processing step (`scripts/build_stratum_table.py`)**

A dedicated script computes the stratum table and writes it to `artifacts/stratum_table.parquet`. The `train_classifier` DVC stage depends on it. `point_win_classifier.py` only loads and queries the table.

- Pro: Clean separation of concerns — ingestion -> aggregation -> model. Each DVC stage has a single responsibility.
- Con: Adds a script and a DVC stage that are thin wrappers around a groupby operation; may feel over-engineered given the simplicity of the transformation.

> **Recommendation: Option A1** if D-3 = Option A (stratum aggregation IS the classifier; co-location is natural). **Option A2** if D-3 = Option B or C (stratum computation is a pre-processing dependency the DVC stage should track explicitly).

---

## D-4 — Wilson Interval Source: Classifier-Computed vs. Upstream Stratum Count

**Status: [Single Valid Path]**

### Decision

The stratum observation count (`N`) and win count (`k`) must be sourced from the **training-time stratum table**, not re-computed at inference time from live data. The rationale:

1. At inference time, `StateMonitorNode` has received one point — it does not have access to a running historical count of points for that player on that surface with that serve number.
2. The Wilson interval is a retrospective confidence bound over the historical record, not a real-time streaming estimate. Its semantics are: "given everything we know about this player on this surface on this serve number from the historical dataset, how uncertain is `p_hat`?"
3. Re-computing stratum counts from a live stream would require maintaining a running counter per stratum across match sessions — stateful cross-match accumulation that is explicitly out of scope for v1 (project constitution Section 6: "short-term per-match session memory only").

**Implementation:** The stratum table artifact (produced at training time, loaded at inference from `artifacts/models/point_win_classifier/`) carries `(k, N)` per stratum. `StateMonitorNode` looks up the stratum, retrieves `(k, N)`, and passes them to `propagate_leverage_uncertainty()`. This is the only path consistent with ADR-005.

---

## D-5 — Empirical-Bayes Shrinkage Estimator Implementation Strategy

**Status: [User Input Required]**

### Context

The roadmap mandates: *"Implement the Pressure Deviation model as an empirical-Bayes shrinkage estimator, per-player, shrinking toward the population baseline as a function of leverage bucket."*

**What this means precisely:** For each player, at each leverage bucket, the model estimates whether the player's serve-win rate in high-leverage situations deviates from their baseline serve-win rate. The shrinkage ensures that players with sparse high-leverage observations are pulled toward the population average, rather than expressing spurious extreme deviations.

**Sufficiency Gate invariant (ADR-003, project constitution Section 7):** The deviation estimate must carry a confidence interval that widens as observation count drops. Sparse data must produce wide intervals, not confident-sounding small deviations. The constitution explicitly calls out the risk of systematically reading sparse data as "chokes under pressure" — a fairness concern.

### Options

**Option A — Beta-Binomial Conjugate Shrinkage (Fixed Prior, Closed-Form)**

For each (player, leverage bucket) stratum, the model computes a posterior mean and credible interval using a Beta-Binomial conjugate model.

- Prior: `Beta(alpha_0, beta_0)` from `params.yaml` (`pressure_prior_alpha`, `pressure_prior_beta`).
- Likelihood: `k_pressure` wins out of `N_pressure` high-leverage points.
- Posterior: `Beta(alpha_0 + k_pressure, beta_0 + N_pressure - k_pressure)`.
- Posterior mean: `(alpha_0 + k_pressure) / (alpha_0 + beta_0 + N_pressure)` — the shrunk estimate.
- Deviation: `posterior_mean - player_baseline_p` (where `baseline_p` is from the stratum table).
- Credible interval: Beta distribution percentiles (e.g., 5th/95th for 90% coverage).

Pros:
- Fully closed-form; no optimization. Consistent with ADR-002's preference for exact computation.
- The posterior mean is provably a weighted average of `k/N` and `alpha_0/(alpha_0+beta_0)`, making the shrinkage transparent and auditable.
- The credible interval directly satisfies the Sufficiency Gate: it widens as N_pressure decreases (the prior dominates more), making the fairness concern structurally addressed.
- Simpler to test: golden-value tests for the posterior update and credible interval are derivable analytically.

Cons:
- The prior `(alpha_0, beta_0)` is a fixed config value, not estimated from data. Potentially over-shrinks well-charted players if the config default is too uninformative.
- Does not share information across players in the same leverage bucket (no pooling across player strata).

**Option B — Empirical-Bayes Pooled Prior (MLE-Estimated Prior per Leverage Bucket)**

Instead of a fixed prior from `params.yaml`, the prior `(alpha_0, beta_0)` is estimated from the data per leverage bucket using marginal maximum likelihood (method of moments on the Beta distribution).

- For each leverage bucket, fit `(alpha_0, beta_0)` from the distribution of all players' observed high-leverage rates in that bucket.
- Then apply the Beta-Binomial posterior per player using the bucket-estimated prior.

Pros:
- The prior is data-driven and properly reflects the population distribution for each leverage level. This is the statistically precise interpretation of "empirical-Bayes": the prior is estimated empirically.
- Adaptive: the prior will be tighter (less shrinkage) for well-measured leverage buckets.
- The word "empirical" in the roadmap's "empirical-Bayes shrinkage estimator" most plausibly refers to this approach.

Cons:
- Requires moment-matching or log-likelihood optimization (`scipy.optimize.minimize`) to fit `(alpha_0, beta_0)` per bucket — more computation and more code surface than Option A.
- Needs enough players per bucket to produce a stable MLE prior. Sparse buckets produce poorly estimated priors, which then drive poorly estimated posteriors — the opposite of the intended behavior.
- Harder to test: the test suite must verify the MLE prior estimation, the posterior update, and the interval coverage separately.

> **Recommendation: Option B with a sparse-bucket fallback.** The roadmap uses "empirical-Bayes" specifically; Option A is a standard Bayesian estimator, not an empirical-Bayes one. Option B is the statistically correct interpretation. However, the sparse-bucket failure mode is real: if fewer than `N_min_players` players have observations in a given leverage bucket, the MLE prior is unreliable. The implementation should fall back to the fixed `params.yaml` prior (Option A behavior) for those buckets, with an explicit `is_prior_estimated: bool` flag on the result. **User input is required to confirm Option B and acknowledge the sparse-bucket fallback design.**

---

## D-5a — Leverage Bucket Definition and Granularity (Contingent on D-5)

**Status: [User Input Required — contingent on D-5]**

### Context

The pressure deviation model operates per leverage bucket. The roadmap does not specify bucket boundaries. D-2 proposes `pressure_leverage_buckets: [0.10, 0.25]` as a starting point (three buckets). This needs explicit confirmation.

### Options

**Option A1 — Three Buckets: Routine / Elevated / Critical**

- `[0.00, 0.10)` — Routine (below escalation threshold; `PressureDiagnosticNode` does not fire)
- `[0.10, 0.25)` — Elevated (at or above escalation threshold; diagnostic fires)
- `[0.25, 1.00]` — Critical (deep match pressure; most consequential points)

Pros: Aligns the first boundary with `thresholds.leverage_escalation`; semantically clear; produces three coaching-relevant populations.
Cons: The `[0.25, 1.0]` bucket may be sparse — very high-leverage points are rare by definition. This is the sparse-bucket failure mode flagged in D-5.

**Option A2 — Two Buckets: Below-Threshold / Above-Threshold**

- `[0.00, 0.10)` — Non-escalated
- `[0.10, 1.00]` — Escalated

Pros: Maximum data per bucket; simplest structure that still tests the core hypothesis.
Cons: Does not distinguish between "moderately high leverage" and "critically decisive point" — a distinction coaches explicitly care about.

> **Recommendation: Option A1.** Three buckets is the minimum granularity that allows the model to distinguish routine from modestly high-leverage from definitively high-leverage. If the `[0.25, 1.0]` bucket proves too sparse after data exploration, the boundaries can be revised in `params.yaml` without a code change — this is precisely why they live in config rather than code.

---

## D-6 — MLflow Tracking URI and Artifact Store Strategy

**Status: [Single Valid Path]**

### Decision

1. **Tracking URI:** Local filesystem at `./mlruns/` (MLflow default). No remote tracking server in Phase 3 — a remote server is Phase 7 scope (observability hardening). `mlruns/` must be added to `.gitignore`.
2. **Artifact Store:** MLflow's local artifact store under `./mlruns/<experiment_id>/<run_id>/artifacts/`. Additionally, the final trained model artifacts used at inference time are written to `artifacts/models/` and tracked by **DVC** (not MLflow) as part of the `train_classifier` and `train_pressure` stage outputs. This dual-tracking design is intentional: MLflow tracks experiments (calibration curves, AUC, run metadata); DVC tracks the deterministic pipeline's build artifacts.
3. **Calibration curves:** Logged to MLflow as PNG artifacts (generated by plotting `sklearn.calibration.calibration_curve` output).

**Why this is the only valid path:**

- A remote MLflow server adds infrastructure overhead with no benefit in a local development phase.
- Committing `mlruns/` to git bloats the repository with binary artifacts; DVC tracks the outputs that matter for pipeline reproducibility.
- The inference path must load from a deterministic, DVC-tracked artifact path (`artifacts/models/`), not from a mutable MLflow model registry URI that could change between runs or be absent in CI.

---

## D-7 — DVC Stage Architecture for Phase 3 Training

**Status: [Single Valid Path]**

### Decision

Replace both stub stages with the following structure. Exact file paths and parameter keys will be finalized during implementation, consistent with whichever D-3 option is approved.

```yaml
# Representative schema — exact paths finalized during implementation.

train_classifier:
  cmd: uv run python scripts/train_classifier.py
  deps:
    - scripts/train_classifier.py
    - src/models/point_win_classifier.py
    - src/config/loader.py
    - artifacts/validated_data/points.parquet
    - params.yaml
  params:
    - models.train_test_split
    - models.random_state
    - models.calibration_method
    - models.mlflow_experiment_classifier
    - uncertainty.min_stratum_observations
    - uncertainty.confidence_level
    - solver.default_p_serve
  outs:
    - artifacts/models/point_win_classifier/
  metrics:
    - artifacts/metrics/classifier_metrics.json:
        cache: false

train_pressure:
  cmd: uv run python scripts/train_pressure.py
  deps:
    - scripts/train_pressure.py
    - src/models/pressure_deviation.py
    - src/config/loader.py
    - artifacts/validated_data/points.parquet
    - artifacts/models/point_win_classifier/   # Depends on stratum table for player baseline p
    - params.yaml
  params:
    - models.pressure_prior_alpha
    - models.pressure_prior_beta
    - models.pressure_leverage_buckets
    - models.mlflow_experiment_pressure
    - models.random_state
  outs:
    - artifacts/models/pressure_deviation/
  metrics:
    - artifacts/metrics/pressure_metrics.json:
        cache: false
```

**Key design choices embedded in this structure:**

- `train_pressure` depends on `artifacts/models/point_win_classifier/` — the pressure model needs the stratum table (player baseline `p`) to compute deviations. This dependency is a DVC-enforced ordering guarantee, not a runtime import.
- `metrics` files are `cache: false` — they are lightweight JSON metric snapshots, not pipeline artifacts that need to be re-produced from scratch on every run.
- Both stages depend on `params.yaml` — DVC will re-run the stage if any tracked param changes, enforcing reproducibility without manual invalidation.

---

## D-8 — Test Coverage Strategy for Tier 1 Models

**Status: [User Input Required]**

### Context

Phase 3 introduces two new modules (`point_win_classifier.py`, `pressure_deviation.py`) and closes the `core/leverage_uncertainty.py` scope item (D-0). Testing strategy requires a decision because ML model tests differ structurally from the closed-form solver tests (which have exact golden values derivable analytically).

**Hard constraint:** The solver correctness test (`@pytest.mark.solver`, tolerance `< 1e-9`) remains the highest-priority test in the suite. Phase 3 tests must not weaken, modify, or replace it.

### What Must Be Tested Regardless of Option

The following behaviors have deterministic, analytically verifiable outputs and must be unit-tested in either option:

- **Stratum aggregation correctness:** Given a synthetic DataFrame with known `(server, surface, serve_number, point_winner)` values, verify the computed `k`, `N`, and `p_hat` are exactly correct.
- **Sufficiency Gate behavior:** Below `uncertainty.min_stratum_observations`, the stratum lookup must return `is_sufficient_sample=False` and produce the fallback interval, not a Wilson interval based on sparse data.
- **Shrinkage direction (pressure model):** The posterior mean must lie strictly between `k_pressure/N_pressure` (the raw high-leverage rate) and `alpha_0/(alpha_0+beta_0)` (the prior mean) when `N_pressure > 0`. This is an invariant of Beta-Binomial conjugate updates.
- **Calibration method routing:** Assert that the `calibration_method` value from `params.yaml` is passed to the sklearn pipeline (if D-3 = Option B or C), not hardcoded.
- **No magic numbers:** All threshold lookups in test setup must source from `params.yaml`, not inline literals.

### Options

**Option A — Unit Tests Only**

Implement only `tests/unit/test_point_win_classifier.py` and `tests/unit/test_pressure_deviation.py`. No integration test.

- Pro: Faster to implement; each unit is testable in isolation with synthetic data.
- Con: Does not verify that Phase 3 outputs (the stratum table's `(k, N)` values) flow correctly into `propagate_leverage_uncertainty()` without schema errors. This boundary is exactly what Phase 4's `StateMonitorNode` will depend on.

**Option B — Unit Tests + Integration Smoke Test**

Same unit tests as Option A, plus one integration test in `tests/integration/test_classifier_uncertainty_integration.py` that:

1. Loads a small synthetic DataFrame (not the real 547k-row Parquet; synthetic data to keep test runtime fast and hermetic).
2. Runs the stratum aggregation step on the synthetic data.
3. Passes the resulting `(k, N)` stratum counts through `propagate_leverage_uncertainty()`.
4. Asserts that `LeverageBandResult` validates correctly and that `band_width >= 0`.

- Pro: Catches schema mismatches between Phase 3 outputs and Phase 2 inputs before they reach the graph in Phase 4. This is the most common category of integration bug in ML pipelines.
- Con: Requires a synthetic DataFrame fixture; adds approximately 30-60 minutes of implementation time.

> **Recommendation: Option B.** The integration test boundary between Tier 1 models and `core/leverage_uncertainty.py` is precisely the contract that Phase 4's `StateMonitorNode` will depend on. Finding a schema mismatch here in Phase 3, with a 30-line synthetic fixture, is far cheaper than finding it during graph integration in Phase 4.

---

## 3. Decision Summary Table

| ID | Title | User Input Required? | Recommendation |
|---|---|---|---|
| D-0 | Monte Carlo vs. Direct-Extreme scope clarification | Yes | Option A — confirm D-4 supersedes; no new functional code |
| D-1 | `params.yaml` loader location | No (single path) | `src/config/loader.py` with Pydantic model return type |
| D-2 | `params.yaml` Phase 3 schema extension | No (single path) | Add seven keys under `models:` namespace |
| D-3 | Feature engineering and stratification architecture | Yes | Option A — stratum-rate aggregation (no sklearn classifier) |
| D-3a | Stratum aggregation ownership | Yes (after D-3) | Option A1 if D-3=A; Option A2 if D-3=B or C |
| D-4 | Wilson interval source | No (single path) | Training-time stratum table; loaded at inference |
| D-5 | Empirical-Bayes shrinkage strategy | Yes | Option B — MLE-estimated prior per bucket + sparse-bucket fallback |
| D-5a | Leverage bucket granularity | Yes (after D-5) | Option A1 — three buckets (routine / elevated / critical) |
| D-6 | MLflow tracking URI and artifact store | No (single path) | Local `./mlruns/`; DVC tracks final artifacts in `artifacts/models/` |
| D-7 | DVC stage architecture | No (single path) | Real stages with explicit deps/params/outs/metrics |
| D-8 | Test coverage strategy | Yes | Option B — unit tests + integration smoke test |

---

## 4. Implementation Sequence (Pending Approval)

Once all user-input decisions are resolved, implementation proceeds in this order to respect dependency constraints:

1. **`params.yaml` extension** (D-2) — must be first; every subsequent step reads from it.
2. **`src/config/loader.py`** (D-1) — enables all other modules to load typed params.
3. **`src/models/point_win_classifier.py`** (D-3) — produces the stratum table and `p_hat`/`(k, N)` per stratum.
4. **`scripts/train_classifier.py`** + DVC `train_classifier` stage update (D-7, first half).
5. **`src/models/pressure_deviation.py`** (D-5) — depends on stratum baselines from step 3.
6. **`scripts/train_pressure.py`** + DVC `train_pressure` stage update (D-7, second half).
7. **`core/leverage_uncertainty.py` docstring amendment + `system_design.md` ADR amendment** (D-0) — closes the roadmap item cleanly.
8. **Unit tests** (`tests/unit/test_point_win_classifier.py`, `tests/unit/test_pressure_deviation.py`) — written alongside or immediately after each module.
9. **Integration smoke test** (`tests/integration/test_classifier_uncertainty_integration.py`) (D-8) — written after both modules exist.
10. **Exit criteria validation** — full `uv run pytest`, `uv run ruff check .`, `uv run pyright`, `python scripts/check_file_size.py`, `uv run dvc repro`, MLflow AUC >= 0.65, pressure interval >= 90% nominal coverage.

---

## 5. Exit Criteria (From Roadmap — Merge-Blocking)

| Criterion | How Verified |
|---|---|
| Classifier AUC >= 0.65 on hold-out | Logged to MLflow; checked against `artifacts/metrics/classifier_metrics.json` |
| Pressure Deviation shrinkage intervals achieve >= 90% nominal coverage | Coverage check on held-out high-leverage points; logged to MLflow |
| Leverage confidence bands produced end-to-end for a sample match | Integration smoke test (D-8 Option B) passes on synthetic fixture |
| `uv run pytest` — all existing 19/19 tests + all new Phase 3 tests pass | CI automated |
| `uv run ruff check .` — 0 errors, 0 warnings | CI automated |
| `uv run pyright` — 0 errors, 0 warnings | CI automated |
| `python scripts/check_file_size.py` — all `src/` files < 1,000 lines | CI automated |
| No magic numbers in any Phase 3 module — all thresholds from `params.yaml` | Code review + grep |
| `mlruns/` added to `.gitignore` | Verified at first commit |
| D-0 supersession logged in `system_design.md` as ADR amendment | Document review |

---

## 6. Open Questions for User Resolution

The following decisions require your explicit input before implementation begins. All others in this document are already resolved.

1. **D-0 — Monte Carlo scope clarification:** Is the roadmap's "Tier 2 Monte Carlo layer" phrase considered superseded by Phase 2 D-4's direct-extreme evaluation? *(Recommendation: Yes — confirm, update `system_design.md`, and close. No new functional code needed.)*

2. **D-3 — Classifier architecture:** Should the point-win classifier be implemented as a stratum-rate aggregation table (Option A) or as a trained sklearn `LogisticRegression` pipeline (Option B or C)? *(Recommendation: Option A.)*

3. **D-3a — Aggregation ownership:** If D-3 = Option A, should the stratum aggregation live inside `point_win_classifier.py` (Option A1) or as a separate `scripts/build_stratum_table.py` DVC step (Option A2)? *(Recommendation: A1 if D-3 = A.)*

4. **D-5 — Shrinkage strategy:** Should the empirical-Bayes prior be estimated from data per leverage bucket with a sparse-bucket fallback (Option B) or set as a fixed `params.yaml` value (Option A)? *(Recommendation: Option B with fallback.)*

5. **D-5a — Bucket granularity:** Are three leverage buckets (routine / elevated / critical) with boundaries at `[0.10, 0.25]` the right starting granularity? *(Recommendation: Yes.)*

6. **D-8 — Test coverage:** Should Phase 3 include an integration smoke test in `tests/integration/` for the classifier -> uncertainty band handoff? *(Recommendation: Yes.)*
