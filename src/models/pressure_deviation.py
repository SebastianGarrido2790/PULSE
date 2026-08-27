"""PULSE — Pressure Deviation Model (Empirical-Bayes Shrinkage Estimator).

Estimates player serve-win performance deviations under leverage using Empirical-Bayes
Beta-Binomial shrinkage with closed-form Method of Moments prior fitting and a
sparse-bucket fallback gate.

Authority: Phase 3 Decision D-5, D-5a, pressure_deviation_spec.md
"""

from pathlib import Path

import numpy as np
import pandas as pd
from opentelemetry import trace
from pydantic import BaseModel, Field
from scipy.stats import beta as scipy_beta

from src.config.loader import Params, load_params
from src.models.point_win_classifier import StratumTable, format_player_key
from src.utils.exceptions import ModelInferenceError

tracer = trace.get_tracer("pulse.models.pressure_deviation")


class PressureDeviationResult(BaseModel):
    """Posterior pressure deviation output payload for a single player in a leverage bucket."""

    server_id: str
    leverage_bucket: int = Field(
        ..., ge=0, le=2, description="Bucket index (0=Routine, 1=Elevated, 2=Critical)"
    )
    k_pressure: int = Field(..., ge=0, description="High-leverage point wins")
    n_pressure: int = Field(..., ge=0, description="High-leverage point attempts")
    baseline_p: float = Field(..., ge=0.0, le=1.0, description="Player overall baseline serve rate")
    shrunk_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Empirical-Bayes posterior mean rate"
    )
    pressure_deviation: float = Field(..., ge=-1.0, le=1.0, description="shrunk_rate - baseline_p")
    deviation_low_90: float = Field(
        ..., ge=-1.0, le=1.0, description="Lower 90% credible bound for deviation"
    )
    deviation_high_90: float = Field(
        ..., ge=-1.0, le=1.0, description="Upper 90% credible bound for deviation"
    )
    alpha_prior: float = Field(..., gt=0.0)
    beta_prior: float = Field(..., gt=0.0)
    is_prior_estimated: bool = Field(
        ..., description="True if prior was estimated via MoM; False if fallback"
    )
    is_sufficient_sample: bool = Field(
        ..., description="True if n_pressure >= params.uncertainty.min_stratum_observations"
    )


class PressureBucketPrior(BaseModel):
    """Fitted population prior parameters for a leverage bucket."""

    leverage_bucket: int = Field(..., ge=0, le=2)
    alpha_0: float = Field(..., gt=0.0)
    beta_0: float = Field(..., gt=0.0)
    is_prior_estimated: bool
    player_count: int = Field(..., ge=0)


class PressureModelArtifact(BaseModel):
    """Serializable container for fitted priors and per-player pressure deviation estimates."""

    priors: dict[int, PressureBucketPrior] = Field(
        ..., description="Key: leverage_bucket index (0, 1, 2)"
    )
    results: dict[str, PressureDeviationResult] = Field(
        ..., description="Key: server_id|leverage_bucket"
    )


def assign_leverage_bucket(leverage: float, boundaries: list[float] | None = None) -> int:
    """Assign point leverage delta_L to a discrete leverage bucket index.

    Default boundaries [0.10, 0.25]:
        leverage < 0.10 -> Bucket 0 (Routine)
        0.10 <= leverage < 0.25 -> Bucket 1 (Elevated)
        leverage >= 0.25 -> Bucket 2 (Critical)

    Args:
        leverage: Point leverage value delta_L in [0.0, 1.0].
        boundaries: Optional list of boundary floats. Defaults to [0.10, 0.25].

    Returns:
        int: Bucket index (0, 1, or 2).
    """
    b = boundaries if boundaries is not None else [0.10, 0.25]
    if len(b) != 2:
        raise ModelInferenceError(f"Expected 2 leverage bucket boundaries, got {len(b)}")

    if leverage < b[0]:
        return 0
    elif leverage < b[1]:
        return 1
    else:
        return 2


def fit_bucket_prior(
    player_rates: list[float], params: Params | None = None
) -> tuple[float, float, bool]:
    """Fit population Beta prior (alpha_0, beta_0) via closed-form Method of Moments.

    Falls back to fixed config prior Beta(2.0, 2.0) if player count < min_players threshold
    or if sample variance is invalid.

    Args:
        player_rates: List of observed serve-win rates across players in bucket.
        params: Optional Params object. Loaded via load_params() if None.

    Returns:
        tuple[float, float, bool]: (alpha_0, beta_0, is_prior_estimated)
    """
    cfg = params if params is not None else load_params()
    min_players = cfg.models.pressure_prior_min_players_per_bucket
    fallback_alpha = cfg.models.pressure_prior_alpha
    fallback_beta = cfg.models.pressure_prior_beta

    sample_size = len(player_rates)
    if sample_size < min_players:
        return (fallback_alpha, fallback_beta, False)

    arr = np.array(player_rates, dtype=float)
    r_bar = float(np.mean(arr))
    # Sample variance with ddof=1
    s2 = float(np.var(arr, ddof=1)) if sample_size > 1 else 0.0

    # Variance validity check for Beta distribution: 0 < s2 < r_bar * (1 - r_bar)
    max_possible_var = r_bar * (1.0 - r_bar)
    if s2 <= 1e-8 or s2 >= max_possible_var:
        return (fallback_alpha, fallback_beta, False)

    # Method of Moments formulas
    temp = (max_possible_var / s2) - 1.0
    alpha_0 = float(r_bar * temp)
    beta_0 = float((1.0 - r_bar) * temp)

    if alpha_0 <= 0.0 or beta_0 <= 0.0:
        return (fallback_alpha, fallback_beta, False)

    return (alpha_0, beta_0, True)


def compute_player_pressure_deviation(
    server_id: str,
    leverage_bucket: int,
    k_pressure: int,
    n_pressure: int,
    baseline_p: float,
    alpha_0: float,
    beta_0: float,
    is_prior_estimated: bool,
    params: Params | None = None,
) -> PressureDeviationResult:
    """Compute Empirical-Bayes posterior mean, pressure deviation, and 90% credible bounds.

    Args:
        server_id: Server player identifier string.
        leverage_bucket: Leverage bucket index (0, 1, 2).
        k_pressure: High-leverage point wins.
        n_pressure: High-leverage point attempts.
        baseline_p: Overall baseline serve-win rate for the player.
        alpha_0: Beta prior alpha.
        beta_0: Beta prior beta.
        is_prior_estimated: True if prior was estimated via MoM.
        params: Optional Params object.

    Returns:
        PressureDeviationResult containing posterior parameters and credible interval.
    """
    cfg = params if params is not None else load_params()

    # Beta-Binomial conjugate update
    alpha_post = alpha_0 + float(k_pressure)
    beta_post = beta_0 + float(n_pressure - k_pressure)

    # Posterior mean
    shrunk_rate = alpha_post / (alpha_post + beta_post)
    pressure_dev = shrunk_rate - baseline_p

    # Internal assertion: Shrinkage-Direction Invariant
    if n_pressure > 0:
        raw_rate = float(k_pressure) / float(n_pressure)
        prior_mean = alpha_0 / (alpha_0 + beta_0)
        lower_bound = min(raw_rate, prior_mean) - 1e-5
        upper_bound = max(raw_rate, prior_mean) + 1e-5
        if not (lower_bound <= shrunk_rate <= upper_bound):
            raise ModelInferenceError(
                f"Shrinkage-direction invariant violated: shrunk_rate={shrunk_rate:.4f} "
                f"not bounded by raw={raw_rate:.4f} and prior_mean={prior_mean:.4f}"
            )

    # 90% nominal credible interval percentiles (5th to 95th)
    rate_low_90 = float(scipy_beta.ppf(0.05, alpha_post, beta_post))
    rate_high_90 = float(scipy_beta.ppf(0.95, alpha_post, beta_post))

    dev_low_90 = rate_low_90 - baseline_p
    dev_high_90 = rate_high_90 - baseline_p

    is_sufficient = n_pressure >= cfg.uncertainty.min_stratum_observations

    return PressureDeviationResult(
        server_id=server_id,
        leverage_bucket=leverage_bucket,
        k_pressure=k_pressure,
        n_pressure=n_pressure,
        baseline_p=baseline_p,
        shrunk_rate=shrunk_rate,
        pressure_deviation=pressure_dev,
        deviation_low_90=dev_low_90,
        deviation_high_90=dev_high_90,
        alpha_prior=alpha_0,
        beta_prior=beta_0,
        is_prior_estimated=is_prior_estimated,
        is_sufficient_sample=is_sufficient,
    )


def fit_pressure_model(
    df_points_with_leverage: pd.DataFrame,
    stratum_table: StratumTable,
    params: Params | None = None,
) -> PressureModelArtifact:
    """Fit Pressure Deviation model across all leverage buckets and players.

    Args:
        df_points_with_leverage: DataFrame containing columns
            ['server', 'leverage', 'point_winner', 'serve_number'].
        stratum_table: StratumTable from Tier 1 classifier (supplies baseline_p).
        params: Optional Params object.

    Returns:
        PressureModelArtifact container with fitted priors and player results.
    """
    cfg = params if params is not None else load_params()

    required_cols = {"server", "leverage", "point_winner", "serve_number"}
    if not required_cols.issubset(df_points_with_leverage.columns):
        missing = required_cols - set(df_points_with_leverage.columns)
        raise ModelInferenceError(f"Missing required columns for pressure model fit: {missing}")

    work_df = df_points_with_leverage.copy()
    work_df["is_server_win"] = (work_df["point_winner"] == "server").astype(int)
    work_df["leverage_bucket"] = work_df["leverage"].apply(
        lambda lev: assign_leverage_bucket(lev, cfg.models.pressure_leverage_buckets)
    )

    # 1. Aggregate per-player, per-bucket (k_pressure, n_pressure)
    pb_grp = (
        work_df.groupby(["server", "leverage_bucket"])
        .agg(wins=("is_server_win", "sum"), attempts=("is_server_win", "count"))
        .reset_index()
    )

    # Convert to typed dict records
    pb_records = pb_grp.to_dict(orient="records")

    # 2. Fit bucket priors (MoM)
    priors: dict[int, PressureBucketPrior] = {}
    for bucket in (0, 1, 2):
        # Collect observed rates for players with >= min_stratum_observations in bucket
        bucket_rates: list[float] = []
        player_cnt = 0
        for row in pb_records:
            if int(row["leverage_bucket"]) == bucket:
                n = int(row["attempts"])
                if n >= cfg.uncertainty.min_stratum_observations:
                    bucket_rates.append(float(row["wins"]) / float(n))
                    player_cnt += 1

        alpha_0, beta_0, is_est = fit_bucket_prior(bucket_rates, cfg)
        priors[bucket] = PressureBucketPrior(
            leverage_bucket=bucket,
            alpha_0=alpha_0,
            beta_0=beta_0,
            is_prior_estimated=is_est,
            player_count=player_cnt,
        )

    # 3. Compute per-player posterior results
    results: dict[str, PressureDeviationResult] = {}
    for row in pb_records:
        server_id = str(row["server"])
        bucket = int(row["leverage_bucket"])
        k_press = int(row["wins"])
        n_press = int(row["attempts"])

        # Sourced baseline_p: Tier 1 1st-serve player rate, or global default
        t1_key = format_player_key(server_id, serve_number=1)
        if t1_key in stratum_table.tier1_player:
            baseline_p = stratum_table.tier1_player[t1_key].p_hat
        else:
            baseline_p = stratum_table.global_default_p

        prior = priors[bucket]
        res = compute_player_pressure_deviation(
            server_id=server_id,
            leverage_bucket=bucket,
            k_pressure=k_press,
            n_pressure=n_press,
            baseline_p=baseline_p,
            alpha_0=prior.alpha_0,
            beta_0=prior.beta_0,
            is_prior_estimated=prior.is_prior_estimated,
            params=cfg,
        )

        key = f"{server_id}|{bucket}"
        results[key] = res

    return PressureModelArtifact(priors=priors, results=results)


def save_pressure_artifact(artifact: PressureModelArtifact, artifact_dir: Path) -> Path:
    """Save PressureModelArtifact to JSON file.

    Args:
        artifact: PressureModelArtifact instance.
        artifact_dir: Target output directory.

    Returns:
        Path to saved json file.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifact_dir / "pressure_deviation.json"
    out_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_pressure_artifact(artifact_dir: Path) -> PressureModelArtifact:
    """Load PressureModelArtifact from JSON file.

    Args:
        artifact_dir: Path to directory containing pressure_deviation.json.

    Returns:
        PressureModelArtifact instance.

    Raises:
        ModelInferenceError: If file is missing or unparseable.
    """
    target = artifact_dir / "pressure_deviation.json"
    if not target.exists():
        raise ModelInferenceError(f"PressureModelArtifact not found at [{target}]")

    try:
        content = target.read_text(encoding="utf-8")
        return PressureModelArtifact.model_validate_json(content)
    except Exception as e:
        raise ModelInferenceError(
            f"Failed to load PressureModelArtifact from [{target}]: {e}"
        ) from e


def get_pressure_deviation(
    artifact: PressureModelArtifact, server_id: str, leverage_bucket: int
) -> PressureDeviationResult | None:
    """Retrieve serving-time pressure deviation result for a player in a leverage bucket.

    Key format: "server_id|leverage_bucket".
    Returns None if player has no entry in the specified leverage bucket (sparse-player miss).

    Args:
        artifact: Loaded PressureModelArtifact container.
        server_id: Player identifier string.
        leverage_bucket: Discrete leverage bucket index (0, 1, or 2).

    Returns:
        PressureDeviationResult if found, or None on sparse-player miss.
    """
    with tracer.start_as_current_span("pressure_deviation.get_deviation") as span:
        key = f"{server_id}|{leverage_bucket}"
        res = artifact.results.get(key)

        span.set_attribute("pulse.server_id", server_id)
        span.set_attribute("pulse.leverage_bucket", int(leverage_bucket))
        span.set_attribute("pulse.hit", bool(res is not None))

        if res is not None:
            span.set_attribute("pulse.pressure_deviation", float(res.pressure_deviation))
            span.set_attribute("pulse.deviation_low_90", float(res.deviation_low_90))
            span.set_attribute("pulse.deviation_high_90", float(res.deviation_high_90))
            span.set_attribute("pulse.k_pressure", int(res.k_pressure))
            span.set_attribute("pulse.n_pressure", int(res.n_pressure))
            span.set_attribute("pulse.is_sufficient_sample", bool(res.is_sufficient_sample))

        return res
