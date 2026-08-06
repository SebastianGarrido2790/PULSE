# Phase 3 — Tier 1 ML Layer: Sequential Implementation Plan

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)
**Status:** Ready for implementation — all decisions (D-0 through D-8) approved, ADR-005 Amendment 1 logged
**Scope of this document:** Execution sequence only. Translates the approved decisions in `reports/docs/decisions/phase3_implementation_plan_and_decisions.md` into an ordered set of concrete steps, respecting dependencies between them.

---

### Step 1: Component Specifications for the Two Novel Statistical Components

Before any model code is written, write the mathematical contracts these two components must satisfy — the same discipline applied to `markov_solver_spec.md` before Phase 2 implementation began, extended here because the empirical-Bayes shrinkage math is exactly the kind of "correct in prose, ambiguous in practice" risk that caused the Phase 2 tiebreak bug.

1. **`reports/specs/point_win_classifier_spec.md`**
   - Formal `StratumTable` schema: fields, types, and which aggregation level each row represents.
   - The 4-tier resolution algorithm stated as an explicit, ordered procedure (not prose): given `(server_id, surface, serve_number)`, exactly which threshold from `params.yaml` gates each tier transition, and what happens at `N=0` at every tier (must resolve to Tier 3, never error).
   - An explicit statement that this is not a trained classifier — the ADR-005 Amendment 1 rationale, restated here so the spec is self-contained for anyone reading it without the full ADR history.

2. **`reports/specs/pressure_deviation_spec.md`**
   - Beta-Binomial conjugate update formulas (prior → likelihood → posterior), stated exactly as they will be coded.
   - **Pin down now, not during implementation:** the per-bucket prior-fitting method. D-5's decision text left "moment-matching or log-likelihood optimization" open — this spec must choose one explicitly (method-of-moments is the simpler, closed-form-adjacent choice and is recommended unless there's a reason to prefer MLE via `scipy.optimize.minimize`).
   - Sparse-bucket fallback gate logic, stated as a precise threshold check against `models.pressure_prior_min_players_per_bucket`.
   - The shrinkage-direction invariant as a formal, testable property: posterior mean strictly between `k_pressure/N_pressure` and the prior mean whenever `N_pressure > 0`.
   - Credible interval formula (Beta distribution percentiles) and the target coverage this must be validated against (90%, per exit criteria).

---

### Step 2: `params.yaml` Loader (D-1)

File: `src/config/loader.py`

- Nested Pydantic models mirroring `params.yaml`'s structure exactly (`ThresholdsParams`, `UncertaintyParams` — including the 4-tier fields, `SolverParams`, `IngestionParams`, `LatencyParams`, `ModelsParams` — including all Phase 3 additions, `CIParams`), composed into one top-level `Params` model.
- `load_params(config_path: Path | None = None) -> Params` — default path resolved relative to the repository root, not the caller's working directory.
- Missing or malformed keys raise `ValidationError` at load time — fail at startup, not deep inside a training loop.
- Re-exported from `src/config/__init__.py` so every downstream module imports `from src.config import load_params`, never reads `params.yaml` directly.

---

### Step 3: Point-Win Classifier — Hierarchical Empirical Stratum Estimator (D-3, D-3a)

File: `src/models/point_win_classifier.py`

- `StratumTable` Pydantic model, and `build_stratum_table(points_df) -> StratumTable` computing `k`, `N`, `p_hat` at all four aggregation levels (exact stratum, player-overall, surface-population, global) in one pass.
- `resolve_point_win_probability(stratum_table, server_id, surface, serve_number) -> (p_hat, N, fallback_tier)` implementing the 4-tier lookup exactly per the Step 1 spec, thresholds sourced from `Params`, never hardcoded.
- **Train/test split methodology — must be explicit, not assumed.** The split (`models.train_test_split`, `models.random_state`) is applied first; the `StratumTable` is built **only from the training partition**. Held-out test points are then scored by looking up their `p_hat` from the training-derived table. This is the leakage-avoidance rule for a lookup-table estimator: a test point's own label must never contribute to the table it's evaluated against. Point-level random splitting is acceptable given this rule is followed; match-level splitting is a stricter optional alternative, not required.
- Co-located per D-3a (Option A1) — the module owns aggregation and resolution together, since the stratum table _is_ the model artifact.

---

### Step 4: Pressure Deviation Model (D-5, D-5a)

File: `src/models/pressure_deviation.py`

- Leverage-bucket assignment against `models.pressure_leverage_buckets` boundaries.
- **Explicit dependency to account for:** bucketing requires each training point's _leverage_ value, which requires calling the existing, already-verified `compute_leverage()` from `markov_solver.py` — reusing it as-is, no modification. This means `pressure_deviation.py` (or its training script, Step 6) depends on Step 3's stratum table being built first, for two separate reasons: it supplies `baseline_p` per player, and the per-point `p` estimate needed to compute leverage in the first place.
- Per-player, per-bucket aggregation of `k_pressure`, `N_pressure` against the player's Tier-1 (player-overall) baseline rate.
- Per-bucket prior fitting per the Step 1 spec's chosen method; sparse-bucket fallback gate at `models.pressure_prior_min_players_per_bucket` (15); `is_prior_estimated: bool` set accordingly.
- Beta-Binomial posterior, deviation (`posterior_mean - baseline_p`), and credible interval per player per bucket.
- Assert the shrinkage-direction invariant as an internal check during development, not just in tests — a violation here indicates a sign or formula error, not a data quirk.

---

### Step 5: `leverage_uncertainty.py` — Close Out D-0

File: `src/core/leverage_uncertainty.py` (existing, Phase 2)

- Docstring-only change: state explicitly that Monte Carlo propagation was considered and formally retired per ADR-005 Amendment 1, with a one-line pointer to the amendment. No functional change — this module has been correct since Phase 2 D-4. The goal is that a reader of this module in isolation understands MC was a deliberate rejection, not an unfinished item.

---

### Step 6: Training Scripts & DVC Stage Promotion (D-6, D-7)

Files: `scripts/train_classifier.py`, `scripts/train_pressure.py`, `dvc.yaml`

**`train_classifier.py`:**

- Load `Params`, load `points.parquet`, apply the Step 3 train/test split, build the training-only `StratumTable`, evaluate AUC on the held-out partition (each test point's "prediction" is its resolved `p_hat` — this is still a valid ROC-AUC computation even though the estimator is piecewise-constant rather than continuously scored per-feature).
- Log run to MLflow under `models.mlflow_experiment_classifier`; log a calibration-curve PNG artifact.
- Persist `StratumTable` to `artifacts/models/point_win_classifier/` (DVC-tracked); write `artifacts/metrics/classifier_metrics.json` (AUC, per-tier row counts).

**`train_pressure.py`:**

- Load the classifier's persisted `StratumTable` (hard dependency — must run after `train_classifier`).
- Batch-compute leverage for all training points via `compute_leverage()`, bucket them, fit priors per Step 4, compute posteriors/deviations/intervals.
- Log to MLflow under `models.mlflow_experiment_pressure`; persist artifacts to `artifacts/models/pressure_deviation/`; write `artifacts/metrics/pressure_metrics.json` (empirical coverage check result).

**`dvc.yaml`:** Replace both echo stubs with real stages. `train_classifier` depends on `points.parquet` and `point_win_classifier.py`; `train_pressure` depends additionally on `train_classifier`'s output artifact and `markov_solver.py` — the DAG must encode this ordering explicitly, not rely on manual run order.

---

### Step 7: Tests (D-8)

- `tests/unit/test_point_win_classifier.py` — aggregation correctness on a small synthetic frame with hand-computed `k`/`N`/`p_hat`; 4-tier resolution correctness via fixtures deliberately constructed to resolve at each tier; threshold boundary tests (exactly at, one below, one above each `params.yaml` cutoff).
- `tests/unit/test_pressure_deviation.py` — Beta-Binomial posterior golden-value test (hand-computable small case); shrinkage-direction invariant as a property test across a range of synthetic `(k, N)`; sparse-bucket fallback gate test (below-15 uses fixed prior with `is_prior_estimated=False`; at-or-above uses MLE prior with `is_prior_estimated=True`).
- `tests/integration/test_classifier_uncertainty_integration.py` — synthetic fixture through the full chain: aggregation → 4-tier resolution → `propagate_leverage_uncertainty()`; assert `LeverageBandResult` validates and `band_width >= 0`.

---

### Step 8: Exit Criteria Validation

- `uv run pytest` (existing 19 + all new Phase 3 tests), `uv run ruff check .`, `uv run pyright`, `python scripts/check_file_size.py`, `uv run dvc repro` (full pipeline, both new stages included).
- Confirm classifier AUC ≥ 0.65 on the held-out partition; confirm pressure-deviation credible intervals achieve ≥ 90% empirical coverage on held-out high-leverage points.
- Confirm `mlruns/` is in `.gitignore`; grep-check no magic numbers were introduced in either new module.
- Update `system_design.md`: mark ADR-005 Amendment 1 as **Validated** (implementation matched the amended decision) rather than leaving it at Accepted-pending-implementation; update "Current Implementation Status" to Phase 3 complete, per the Update Protocol.
