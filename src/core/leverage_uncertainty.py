"""PULSE — Wilson Score Uncertainty & Leverage Band Propagation Layer.

Computes Wilson score confidence intervals for point-win probability p based on stratum
sample sizes N (player x surface x serve-number), and propagates interval bounds through
the closed-form Markov solver to produce leverage confidence bands per ADR-005.

Authority: ADR-005, Phase 2 Decision D-4
"""

import math

from pydantic import BaseModel, Field
from scipy.stats import norm

from src.core.markov_solver import MatchState, SolverResult, compute_leverage


class WilsonInterval(BaseModel):
    """Wilson score confidence interval for point-win probability p.

    Attributes:
        p_hat: Observed sample win proportion k / N (or fallback default).
        p_low: Lower Wilson confidence bound.
        p_high: Upper Wilson confidence bound.
        sample_size: Total stratum observation count N.
        wins: Total stratum wins k.
        confidence_level: Nominal confidence level (e.g. 0.95).
        is_sufficient_sample: True if sample_size >= min_stratum_observations.
    """

    p_hat: float = Field(..., ge=0.0, le=1.0, description="Observed sample proportion k / N")
    p_low: float = Field(..., ge=0.0, le=1.0, description="Lower Wilson confidence bound")
    p_high: float = Field(..., ge=0.0, le=1.0, description="Upper Wilson confidence bound")
    sample_size: int = Field(..., ge=0, description="Total stratum observations N")
    wins: int = Field(..., ge=0, description="Total stratum wins k")
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.999)
    is_sufficient_sample: bool = Field(
        default=True, description="True if sample_size >= min_stratum_observations"
    )


class LeverageBandResult(BaseModel):
    """Propagated leverage confidence band result per ADR-005.

    Attributes:
        state: MatchState evaluated.
        p_hat: Point-win probability point estimate used.
        p_low: Lower Wilson bound for p.
        p_high: Upper Wilson bound for p.
        leverage_point: Leverage evaluated at p_hat.
        leverage_low: Leverage evaluated at boundary point.
        leverage_high: Leverage evaluated at boundary point.
        band_width: Width of the leverage confidence band (max_L - min_L).
        sample_size: Stratum observation count backing p.
        is_sufficient_sample: True if sample_size >= min_stratum_observations.
        solver_result_point: Primary SolverResult evaluated at p_hat.
    """

    state: MatchState
    p_hat: float = Field(..., ge=0.0, le=1.0)
    p_low: float = Field(..., ge=0.0, le=1.0)
    p_high: float = Field(..., ge=0.0, le=1.0)
    leverage_point: float = Field(..., ge=0.0, le=1.0)
    leverage_low: float = Field(..., ge=0.0, le=1.0)
    leverage_high: float = Field(..., ge=0.0, le=1.0)
    band_width: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(..., ge=0)
    is_sufficient_sample: bool
    solver_result_point: SolverResult


def compute_wilson_interval(
    wins: int,
    sample_size: int,
    confidence_level: float = 0.95,
    min_observations: int = 10,
    default_p: float = 0.62,
    fallback_margin: float = 0.15,
) -> WilsonInterval:
    """Compute Wilson score confidence interval for point win probability p.

    Formulas (Spec §D-4):
        p_tilde = (p_hat + z^2 / (2N)) / (1 + z^2 / N)
        margin = (z / (1 + z^2 / N)) * sqrt(p_hat * (1 - p_hat) / N + z^2 / (4N^2))
        p_low = max(0.001, p_tilde - margin)
        p_high = min(0.999, p_tilde + margin)

    Args:
        wins: Number of point wins k in stratum.
        sample_size: Total stratum observation count N.
        confidence_level: Confidence level (e.g., 0.95 for 95% CI).
        min_observations: Minimum required N for sufficiency gate.
        default_p: Fallback point-win probability when sample_size < min_observations.
        fallback_margin: Symmetric +/- margin applied around default_p when the
            sufficiency gate is not met. Sourced from
            `params.yaml: uncertainty.default_fallback_margin` (Phase 2 D-5) --
            never hardcoded at the call site.

    Returns:
        WilsonInterval object with p_hat, p_low, p_high, and sufficiency status.
    """
    if sample_size < min_observations or sample_size <= 0:
        return WilsonInterval(
            p_hat=default_p,
            p_low=max(0.001, default_p - fallback_margin),
            p_high=min(0.999, default_p + fallback_margin),
            sample_size=max(0, sample_size),
            wins=max(0, wins),
            confidence_level=confidence_level,
            is_sufficient_sample=False,
        )

    # Calculate observed proportion
    p_hat = float(wins) / float(sample_size)

    # Calculate standard normal quantile z for confidence_level
    alpha = 1.0 - confidence_level
    z = float(norm.ppf(1.0 - alpha / 2.0))

    z2 = z**2
    n = float(sample_size)

    p_tilde = (p_hat + (z2 / (2.0 * n))) / (1.0 + (z2 / n))
    under_sqrt = (p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * (n**2)))
    margin = (z / (1.0 + (z2 / n))) * math.sqrt(max(0.0, under_sqrt))

    p_low = max(0.001, min(0.999, p_tilde - margin))
    p_high = max(0.001, min(0.999, p_tilde + margin))

    return WilsonInterval(
        p_hat=p_hat,
        p_low=p_low,
        p_high=p_high,
        sample_size=sample_size,
        wins=wins,
        confidence_level=confidence_level,
        is_sufficient_sample=True,
    )


def propagate_leverage_uncertainty(
    state: MatchState,
    wins: int,
    sample_size: int,
    confidence_level: float = 0.95,
    min_observations: int = 10,
    default_p: float = 0.62,
    fallback_margin: float = 0.15,
) -> LeverageBandResult:
    """Propagate point-win probability Wilson bounds through Markov solver to obtain leverage band.

    Direct Extreme Evaluation (Spec §D-4 Option A):
        Evaluates leverage at p_hat, p_low, and p_high to compute the leverage band
        [leverage_low, leverage_high] and band width W_L. Sound because match-win
        probability is monotonic in p_serve (verified empirically, Phase 2 review),
        so no interior extremum can fall between p_low and p_high.

    Args:
        state: Current MatchState.
        wins: Stratum point wins k.
        sample_size: Stratum total observation count N.
        confidence_level: Confidence level (e.g. 0.95).
        min_observations: Minimum required observations for sufficiency gate.
        default_p: Fallback p when sample_size < min_observations.
        fallback_margin: Symmetric +/- margin around default_p on insufficient
            sample. Sourced from `params.yaml: uncertainty.default_fallback_margin`.

    Returns:
        LeverageBandResult with leverage confidence band bounds and width.
    """
    interval = compute_wilson_interval(
        wins=wins,
        sample_size=sample_size,
        confidence_level=confidence_level,
        min_observations=min_observations,
        default_p=default_p,
        fallback_margin=fallback_margin,
    )

    # 1. Primary evaluation at point estimate p_hat
    solver_point = compute_leverage(state, interval.p_hat)

    # 2. Extreme evaluation at boundary points p_low and p_high
    solver_low = compute_leverage(state, interval.p_low)
    solver_high = compute_leverage(state, interval.p_high)

    leverages = [solver_point.leverage, solver_low.leverage, solver_high.leverage]
    lev_min = min(leverages)
    lev_max = max(leverages)
    band_width = max(0.0, min(1.0, lev_max - lev_min))

    return LeverageBandResult(
        state=state,
        p_hat=interval.p_hat,
        p_low=interval.p_low,
        p_high=interval.p_high,
        leverage_point=solver_point.leverage,
        leverage_low=lev_min,
        leverage_high=lev_max,
        band_width=band_width,
        sample_size=sample_size,
        is_sufficient_sample=interval.is_sufficient_sample,
        solver_result_point=solver_point,
    )
