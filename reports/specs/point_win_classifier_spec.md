# Component Specification — Point-Win Classifier (Hierarchical Empirical Stratum Estimator)

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Version:** 0.1.0  
**Date:** 2026-08-05  
**Component:** `src/models/point_win_classifier.py`  
**Authority:** ADR-005 Amendment 1 (`reports/docs/architecture/system_design.md`) - Phase 3 Decision D-3, D-3a, D-4 (`reports/docs/decisions/phase3_implementation_plan_and_decisions.md`)

---

## 1. Executive Summary & Design Rationale

This specification defines the mathematical contract, data schema, and resolution algorithm for the **Point-Win Classifier**.

Per **ADR-005 Amendment 1**, this component replaces a parametric `LogisticRegression` model with a **Hierarchical Empirical Stratum Estimator**. The estimator calculates observed serve-win rates across nested player, surface, and serve-number strata, returning point estimates $p_{\text{hat}}$ and sample sizes $N$ that directly feed the Wilson score confidence interval layer (`src/core/leverage_uncertainty.py`).

### Key Design Rationale:

1. **Direct Sample-Size Transparency:** Wilson interval sizing requires the exact observation count $N$ backing $p$. An empirical stratum lookup directly exposes $N$ at every aggregation tier without synthetic approximations.
2. **Elimination of Score-Context Feature Leakage:** Score-state variables (`break_point`, `set_point`, `match_point`) represent in-game states that the closed-form Markov solver already conditions on. Excluding them from the point-win estimator avoids circularity between the prior estimate $p$ and the solver's state-transition logic.
3. **Zero Inference Latency:** Stratum resolution is a deterministic lookup table query ($O(1)$ dictionary get), executing well within the $< 1\text{s}$ per-point latency budget for `StateMonitorNode`.

---

## 2. Data Schema Contract

The estimator's primary artifact is a `StratumTable` serialized to Parquet (`artifacts/models/point_win_classifier/stratum_table.parquet`).

### 2.1 Aggregation Key Schema

Data is aggregated across four distinct hierarchical levels during training:

1. **Tier 0 (Exact Stratum):** Key `(server_id: str, surface: Surface, serve_number: int)`
2. **Tier 1 (Player Overall):** Key `(server_id: str, serve_number: int)`
3. **Tier 2 (Population Surface):** Key `(surface: Surface, serve_number: int)`
4. **Tier 3 (Global Default):** Fixed constant `solver.default_p_serve` (0.62) with margin `uncertainty.default_fallback_margin` (0.15).

### 2.2 Pydantic Data Structures

```python
from enum import IntEnum
from pydantic import BaseModel, Field, model_validator


class FallbackTier(IntEnum):
    """Hierarchical fallback tier resolution level."""

    EXACT_STRATUM = 0  # (player, surface, serve_number) >= min_stratum_observations
    PLAYER_OVERALL = 1  # (player, serve_number) >= min_player_observations
    SURFACE_POPULATION = 2  # (surface, serve_number) >= min_surface_observations
    GLOBAL_DEFAULT = 3  # Fallback to solver.default_p_serve


class StratumEntry(BaseModel):
    """Win-rate statistics for a specific aggregation stratum."""

    wins: int = Field(..., ge=0, description="Total point wins k")
    sample_size: int = Field(..., ge=0, description="Total point attempts N")
    p_hat: float = Field(..., ge=0.0, le=1.0, description="Observed win proportion k / N")

    @model_validator(mode="after")
    def validate_proportion(self) -> "StratumEntry":
        if self.sample_size > 0:
            expected_p = float(self.wins) / float(self.sample_size)
            if abs(self.p_hat - expected_p) > 1e-6:
                raise ValueError(
                    f"p_hat {self.p_hat} does not match wins/sample_size ({expected_p})"
                )
        return self


class StratumLookupResult(BaseModel):
    """Output payload returned by resolve_point_win_probability()."""

    p_hat: float = Field(..., ge=0.0, le=1.0, description="Point win probability estimate")
    sample_size: int = Field(..., ge=0, description="Observation count N backing p_hat")
    wins: int = Field(..., ge=0, description="Point win count k backing p_hat")
    fallback_tier: FallbackTier = Field(..., description="Tier level used for resolution")
    server_id: str
    surface: str
    serve_number: int
```

---

## 3. Hierarchical Fallback Resolution Procedure

Given a point query for `(server_id, surface, serve_number)`, the estimator resolves $p_{\text{hat}}$, sample size $N$, win count $k$, and `fallback_tier` through the following deterministic algorithm:

```text
PROCEDURE ResolvePointWinProbability(server_id, surface, serve_number):
    1. Read thresholds from params.yaml:
       min_stratum = params.uncertainty.min_stratum_observations (10)
       min_player  = params.uncertainty.min_player_observations (20)
       min_surface = params.uncertainty.min_surface_observations (50)
       default_p   = params.solver.default_p_serve (0.62)

    2. TIER 0 CHECK: Look up exact stratum (server_id, surface, serve_number)
       IF entry exists AND entry.sample_size >= min_stratum THEN
           RETURN StratumLookupResult(
               p_hat=entry.p_hat,
               sample_size=entry.sample_size,
               wins=entry.wins,
               fallback_tier=FallbackTier.EXACT_STRATUM
           )

    3. TIER 1 CHECK: Look up player overall (server_id, serve_number)
       IF entry exists AND entry.sample_size >= min_player THEN
           RETURN StratumLookupResult(
               p_hat=entry.p_hat,
               sample_size=entry.sample_size,
               wins=entry.wins,
               fallback_tier=FallbackTier.PLAYER_OVERALL
           )

    4. TIER 2 CHECK: Look up population surface (surface, serve_number)
       IF entry exists AND entry.sample_size >= min_surface THEN
           RETURN StratumLookupResult(
               p_hat=entry.p_hat,
               sample_size=entry.sample_size,
               wins=entry.wins,
               fallback_tier=FallbackTier.SURFACE_POPULATION
           )

    5. TIER 3 FALLBACK: Global Default
       RETURN StratumLookupResult(
           p_hat=default_p,
           sample_size=0,
           wins=0,
           fallback_tier=FallbackTier.GLOBAL_DEFAULT
       )
END PROCEDURE
```

### Invariants:

- **Zero Exception Rule:** Any valid or unrecognized `(server_id, surface, serve_number)` tuple (including `N=0` or unknown player IDs) resolves cleanly to Tier 3 without throwing an exception.
- **Traceability:** `fallback_tier` is logged on every inference payload to support post-hoc auditing of data provenance.

---

## 4. Train/Test Partitioning & Leakage Avoidance

To evaluate model quality (e.g., ROC-AUC) without data leakage:

1. **Partitioning:** Raw point records (`artifacts/validated_data/points.parquet`) are split into training (80%) and holdout test (20%) sets using `models.train_test_split` and `models.random_state` (42).
2. **Training Partition Construction:** The `StratumTable` lookup dictionary is compiled **strictly from the training partition**. Test partition labels ($y_i \in \{0, 1\}$) NEVER update or influence the training table.
3. **Evaluation Protocol:** Each point in the holdout test set is queried against the training-derived `StratumTable`. The resolved $p_{\text{hat}}$ acts as the predicted score for ROC-AUC computation against the true `is_server_win` ground truth.
4. **Exit Criterion:** Classifier holdout ROC-AUC must achieve $\ge 0.65$.

---

## 5. Configuration Integration (`params.yaml`)

All parameters are strictly sourced from `params.yaml`:

```yaml
uncertainty:
  confidence_level: 0.95
  min_stratum_observations: 10
  min_player_observations: 20
  min_surface_observations: 50
  default_fallback_margin: 0.15

solver:
  default_p_serve: 0.62

models:
  point_win_classifier: "hierarchical_stratum_estimator"
  train_test_split: 0.20
  random_state: 42
  mlflow_experiment_classifier: "pulse_point_win_classifier_v1"
```
