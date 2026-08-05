# Component Specification — Pressure Deviation Model (Empirical-Bayes Shrinkage Estimator)

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Version:** 0.1.0  
**Date:** 2026-08-05  
**Component:** `src/models/pressure_deviation.py`  
**Authority:** Phase 3 Decision D-5, D-5a - `reports/docs/decisions/phase3_implementation_plan_and_decisions.md`

---

## 1. Executive Summary & Design Rationale

This specification defines the mathematical contracts, parameter estimation algorithms, and inference interfaces for the **Pressure Deviation Model**.

The model measures whether an individual player's serve-win performance systematically deviates during high-leverage situations compared to their baseline serve-win rate.

### Key Design Rationale:

1. **Empirical-Bayes Pooling:** Rather than asserting fixed global priors or relying on raw un-shrunk sample proportions $k/N$, the model estimates population Beta priors $\text{Beta}(\alpha_0, \beta_0)$ empirically from data for each leverage bucket.
2. **Sufficiency Gate & Fairness Invariant:** Players with low observation counts under high leverage ($N_{\text{pressure}}$) are shrunk heavily toward the population prior mean. Their posterior credible intervals automatically widen, preventing sparse data from being misdiagnosed as "choking under pressure."
3. **Closed-Form Efficiency:** Prior fitting uses the closed-form **Method of Moments**, avoiding numerical optimization failures while guaranteeing reproducible estimates.

---

## 2. Leverage Bucket Partitioning

Point leverage $\Delta L \in [0.0, 1.0]$ is computed per point via `src/core/markov_solver.py:compute_leverage()`. Each point is partitioned into one of three discrete leverage buckets using boundaries defined in `params.yaml: models.pressure_leverage_buckets` (`[0.10, 0.25]`):

| Bucket Index | Bucket Label | Leverage Range ($\Delta L$) | Operational Meaning                                                        |
| ------------ | ------------ | --------------------------- | -------------------------------------------------------------------------- |
| **0**        | `ROUTINE`    | $[0.00, 0.10)$              | Points below escalation threshold (`PressureDiagnosticNode` does not fire) |
| **1**        | `ELEVATED`   | $[0.10, 0.25)$              | Points at or above escalation threshold                                    |
| **2**        | `CRITICAL`   | $[0.25, 1.00]$              | Decisive, highly influential points                                        |

---

## 3. Prior Parameter Estimation (Method of Moments & Sparse-Bucket Fallback)

For each leverage bucket $b \in \{0, 1, 2\}$:

### 3.1 Population Sample Collection

Collect the observed high-leverage serve-win rates $r_i = k_i / N_i$ across all players $i = 1 \dots M$ who have $N_i \ge \text{params.uncertainty.min\_stratum\_observations}$ (10) points in bucket $b$.

### 3.2 Method of Moments Formulation

If sample size $M \ge \text{params.models.pressure\_prior\_min\_players\_per\_bucket}$ (15):

1. Compute sample mean $\bar{r}$:
   $$\bar{r} = \frac{1}{M} \sum_{i=1}^{M} r_i$$
2. Compute sample variance $s^2$:
   $$s^2 = \frac{1}{M - 1} \sum_{i=1}^{M} (r_i - \bar{r})^2$$
3. Check variance validity:
   If $s^2 > 0$ and $s^2 < \bar{r}(1 - \bar{r})$:
   $$\text{temp} = \frac{\bar{r}(1 - \bar{r})}{s^2} - 1$$
   $$\alpha_0 = \bar{r} \cdot \text{temp}, \quad \beta_0 = (1 - \bar{r}) \cdot \text{temp}$$
   Set `is_prior_estimated = True`.

### 3.3 Sparse-Bucket Fallback Gate

If $M < 15$ OR $s^2 \le 0$ OR $s^2 \ge \bar{r}(1 - \bar{r})$:

- Bypass Method of Moments calculation.
- Set $(\alpha_0, \beta_0) = (\text{models.pressure\_prior\_alpha}, \text{models.pressure\_prior\_beta}) = (2.0, 2.0)$.
- Set `is_prior_estimated = False`.

---

## 4. Beta-Binomial Posterior Update & Deviation Calculation

Given player $P$'s high-leverage performance in bucket $b$ ($k_{\text{pressure}}$ wins in $N_{\text{pressure}}$ points) and player $P$'s baseline serve-win rate $p_{\text{baseline}}$ (from Tier 1 overall player serve rate in the classifier's `StratumTable`):

### 4.1 Posterior Parameters

$$\alpha_{\text{post}} = \alpha_0 + k_{\text{pressure}}$$
$$\beta_{\text{post}} = \beta_0 + N_{\text{pressure}} - k_{\text{pressure}}$$

### 4.2 Point Estimates

$$\text{shrunk\_rate} = \frac{\alpha_{\text{post}}}{\alpha_{\text{post}} + \beta_{\text{post}}}$$
$$\text{pressure\_deviation} = \text{shrunk\_rate} - p_{\text{baseline}}$$

### 4.3 90% Nominal Credible Interval

Using the quantile function $F_{\text{Beta}}^{-1}(q; \alpha, \beta)$ (`scipy.stats.beta.ppf`):
$$\text{rate\_low\_90} = F_{\text{Beta}}^{-1}(0.05; \alpha_{\text{post}}, \beta_{\text{post}})$$
$$\text{rate\_high\_90} = F_{\text{Beta}}^{-1}(0.95; \alpha_{\text{post}}, \beta_{\text{post}})$$
$$\text{deviation\_low\_90} = \text{rate\_low\_90} - p_{\text{baseline}}$$
$$\text{deviation\_high\_90} = \text{rate\_high\_90} - p_{\text{baseline}}$$

---

## 5. Formal Invariants

1. **Shrinkage-Direction Invariant:**
   For any $N_{\text{pressure}} > 0$, the posterior mean $\text{shrunk\_rate}$ must lie strictly bounded between the raw sample proportion $k_{\text{pressure}} / N_{\text{pressure}}$ and the prior mean $\mu_0 = \alpha_0 / (\alpha_0 + \beta_0)$:
   $$\min\left(\frac{k_{\text{pressure}}}{N_{\text{pressure}}}, \mu_0\right) \le \text{shrunk\_rate} \le \max\left(\frac{k_{\text{pressure}}}{N_{\text{pressure}}}, \mu_0\right)$$
   _Asserted internally during model execution._

2. **Sufficiency Gate Property:**
   As $N_{\text{pressure}} \to 0$, $\text{shrunk\_rate} \to \mu_0$ and interval width $(\text{deviation\_high\_90} - \text{deviation\_low\_90})$ increases toward the prior's full range.

---

## 6. Output Data Contract

```python
from pydantic import BaseModel, Field


class PressureDeviationResult(BaseModel):
    """Posterior pressure deviation output payload for a single player in a leverage bucket."""

    server_id: str
    leverage_bucket: int = Field(..., ge=0, le=2, description="Bucket index (0=Routine, 1=Elevated, 2=Critical)")
    k_pressure: int = Field(..., ge=0, description="High-leverage point wins")
    n_pressure: int = Field(..., ge=0, description="High-leverage point attempts")
    baseline_p: float = Field(..., ge=0.0, le=1.0, description="Player overall baseline serve rate")
    shrunk_rate: float = Field(..., ge=0.0, le=1.0, description="Empirical-Bayes posterior mean rate")
    pressure_deviation: float = Field(..., ge=-1.0, le=1.0, description="shrunk_rate - baseline_p")
    deviation_low_90: float = Field(..., ge=-1.0, le=1.0, description="Lower 90% credible bound for deviation")
    deviation_high_90: float = Field(..., ge=-1.0, le=1.0, description="Upper 90% credible bound for deviation")
    alpha_prior: float = Field(..., gt=0.0)
    beta_prior: float = Field(..., gt=0.0)
    is_prior_estimated: bool = Field(..., description="True if prior was estimated via MoM; False if fallback")
    is_sufficient_sample: bool = Field(..., description="True if n_pressure >= params.uncertainty.min_stratum_observations")
```

---

## 7. Configuration Integration (`params.yaml`)

```yaml
uncertainty:
  min_stratum_observations: 10

models:
  pressure_prior_alpha: 2.0
  pressure_prior_beta: 2.0
  pressure_prior_min_players_per_bucket: 15
  pressure_leverage_buckets: [0.10, 0.25]
```
