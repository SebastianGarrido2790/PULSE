# ruff: noqa: E402
"""PULSE — Payoff Matrix Construction & Bayesian Shrinkage Pipeline.

Constructs empirical 2x2 / 3x3 PayoffMatrix artifacts per opponent and stratum from historical
charted points data, applying discrete returner-strategy mapping (§5.4), empirical-Bayes Beta
shrinkage (D-5), dimensionality inclusion rules (D-2a), and hierarchical fallback indexing (D-9).

Authority: Phase 5 Decisions D-1, D-2a, D-5, D-7, D-9; game_theory_spec.md §5.4, §6.1.
Usage:
    uv run python scripts/build_payoff_matrices.py
"""

import json
import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from src.config.loader import Params, load_params
from src.core.game_theory import PayoffMatrix
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def fit_beta_prior_mom(
    rates: list[float], fallback_alpha: float = 2.0, fallback_beta: float = 2.0
) -> tuple[float, float]:
    """Fit Beta distribution prior (alpha_0, beta_0) via Method-of-Moments.

    Args:
        rates: List of empirical win probabilities across player strata.
        fallback_alpha: Default fallback alpha if sample variance is invalid.
        fallback_beta: Default fallback beta if sample variance is invalid.

    Returns:
        tuple[float, float]: (alpha_0, beta_0) fitted prior parameters.
    """
    if len(rates) < 10:
        return fallback_alpha, fallback_beta

    arr = np.array(rates, dtype=np.float64)
    mu = float(np.mean(arr))
    var = float(np.var(arr, ddof=1))

    # Variance must be strictly positive and less than theoretical maximum mu * (1 - mu)
    if var <= 0.0 or var >= mu * (1.0 - mu) or mu <= 0.0 or mu >= 1.0:
        return fallback_alpha, fallback_beta

    factor = (mu * (1.0 - mu) / var) - 1.0
    alpha_0 = max(0.5, float(mu * factor))
    beta_0 = max(0.5, float((1.0 - mu) * factor))
    return alpha_0, beta_0


def build_payoff_matrix_for_stratum(
    df_stratum: pd.DataFrame,
    returner_id: str,
    server_id: str,
    surface: str,
    serve_number: int,
    params: Params,
    prior_alpha: float,
    prior_beta: float,
) -> PayoffMatrix | None:
    """Build a PayoffMatrix for a specific stratum of charted points.

    Args:
        df_stratum: Filtered DataFrame containing points for this stratum.
        returner_id: Opponent / returning player ID.
        server_id: Serving player ID (or canonical marker).
        surface: Court surface type ("HARD", "CLAY", "GRASS").
        serve_number: Serve attempt number (1 or 2).
        params: PULSE configuration parameters.
        prior_alpha: Empirical-Bayes Beta prior alpha parameter.
        prior_beta: Empirical-Bayes Beta prior beta parameter.

    Returns:
        PayoffMatrix if data is present, or None if stratum contains 0 observations.
    """
    n_opp_total = len(df_stratum)
    if n_opp_total == 0:
        return None

    # Count observations and server wins by serve direction
    dir_counts: dict[str, int] = {}
    dir_wins: dict[str, int] = {}

    for d in ["wide", "T", "body"]:
        subset = df_stratum[df_stratum["serve_direction"] == d]
        n_d = len(subset)
        w_d = int((subset["point_winner"] == "server").sum())
        dir_counts[d] = n_d
        dir_wins[d] = w_d

    n_wide = dir_counts["wide"]
    n_t = dir_counts["T"]
    n_body = dir_counts["body"]

    # Determine dimensionality: include Body if observation count >= threshold (D-2a)
    min_3x3 = params.thresholds.game_theory_3x3_min_sample_size
    include_body = n_body >= min_3x3

    if include_body:
        row_labels = ["Wide", "Body", "T"]
    else:
        row_labels = ["Wide", "T"]

    col_labels = ["Cover Wide", "Cover T"]

    # Positional coverage advantage boost and penalty sourced from params.yaml
    delta_mismatch = params.models.game_theory_anticipation_boost
    pos_penalty = params.models.game_theory_positioning_penalty

    matrix: list[list[float]] = []
    observation_counts: list[list[int]] = []

    # 1. Wide row
    denom_wide = n_wide + prior_alpha + prior_beta
    w_raw = (
        (dir_wins["wide"] + prior_alpha) / denom_wide
        if n_wide > 0
        else (prior_alpha / (prior_alpha + prior_beta))
    )
    pi_wide_cover_wide = float(np.clip(w_raw - pos_penalty, 0.05, 0.95))
    pi_wide_cover_t = float(np.clip(w_raw + delta_mismatch, 0.05, 0.95))
    matrix.append([round(pi_wide_cover_wide, 4), round(pi_wide_cover_t, 4)])
    n_wide_cell = max(1, n_wide // 2)
    observation_counts.append([n_wide_cell, n_wide_cell])

    # 2. Body row (if included)
    if include_body:
        denom_body = n_body + prior_alpha + prior_beta
        b_raw = (
            (dir_wins["body"] + prior_alpha) / denom_body
            if n_body > 0
            else (prior_alpha / (prior_alpha + prior_beta))
        )
        pi_body_cover_wide = float(np.clip(b_raw, 0.05, 0.95))
        pi_body_cover_t = float(np.clip(b_raw, 0.05, 0.95))
        matrix.append([round(pi_body_cover_wide, 4), round(pi_body_cover_t, 4)])
        n_body_cell = max(1, n_body // 2)
        observation_counts.append([n_body_cell, n_body_cell])

    # 3. T row
    denom_t = n_t + prior_alpha + prior_beta
    t_raw = (
        (dir_wins["T"] + prior_alpha) / denom_t
        if n_t > 0
        else (prior_alpha / (prior_alpha + prior_beta))
    )
    pi_t_cover_wide = float(np.clip(t_raw + delta_mismatch, 0.05, 0.95))
    pi_t_cover_t = float(np.clip(t_raw - pos_penalty, 0.05, 0.95))
    matrix.append([round(pi_t_cover_wide, 4), round(pi_t_cover_t, 4)])
    n_t_cell = max(1, n_t // 2)
    observation_counts.append([n_t_cell, n_t_cell])

    surf_literal = surface if surface in ("HARD", "CLAY", "GRASS") else "HARD"

    return PayoffMatrix(
        matrix=matrix,
        row_labels=row_labels,
        col_labels=col_labels,
        observation_counts=observation_counts,
        n_opp_total=n_opp_total,
        server_id=server_id,
        returner_id=returner_id,
        surface=surf_literal,  # type: ignore[arg-type]
        serve_number=serve_number,
        is_stylized_anticipation_model=True,
        anticipation_delta=delta_mismatch,
    )


def run_payoff_matrix_pipeline() -> None:
    """Execute the payoff matrix construction pipeline and export DVC artifacts."""
    params = load_params()

    # 1. Load validated points dataset
    val_dir = params.ingestion.validated_data_dir
    val_file = params.ingestion.validated_file_name
    data_path = PROJECT_ROOT / val_dir / val_file
    if not data_path.exists():
        console.print(f"[bold red]Error:[/] Dataset not found at {data_path}")
        sys.exit(1)

    logger.info(f"Loading point records from {data_path}")
    df = pd.read_parquet(data_path)
    console.print(f"\n[bold green]Loaded Dataset:[/] {len(df):,} point records")

    # Filter for points with charted serve direction and clear winner
    valid_mask = df["serve_direction"].isin(["wide", "T", "body"]) & df["point_winner"].isin(
        ["server", "returner"]
    )
    valid_df = df[valid_mask].copy()
    console.print(
        f"[bold cyan]Valid Charted Points:[/] {len(valid_df):,} points with charted serve direction"
    )

    # 2. Fit Empirical-Bayes Beta priors across player win rates
    player_win_rates: list[float] = []
    for _, group in valid_df.groupby("returner"):
        if len(group) >= params.models.game_theory_min_observations_per_cell:
            s_wins = (group["point_winner"] == "server").sum()
            player_win_rates.append(float(s_wins) / float(len(group)))

    prior_alpha, prior_beta = fit_beta_prior_mom(
        player_win_rates,
        fallback_alpha=params.models.game_theory_prior_alpha,
        fallback_beta=params.models.game_theory_prior_beta,
    )
    console.print(
        f"[bold green]Fitted Empirical-Bayes Beta Priors:[/] "
        f"alpha_0={prior_alpha:.3f}, beta_0={prior_beta:.3f} "
        f"(fitted on {len(player_win_rates)} returners)"
    )

    # 3. Build PayoffMatrix dictionary across returners and strata
    matrices_dict: dict[str, dict[str, Any]] = {}
    returners = [str(r) for r in pd.Series(valid_df["returner"]).dropna().unique()]
    surfaces = ["HARD", "CLAY", "GRASS"]
    serve_numbers = [1, 2]

    sufficient_count = 0
    matrix_3x2_count = 0
    matrix_2x2_count = 0

    min_sample = params.thresholds.exploit_min_sample_size

    for ret in returners:
        df_ret = pd.DataFrame(valid_df[valid_df["returner"] == ret])

        # Build opponent-level aggregate fallback (D-9)
        matrix_agg = build_payoff_matrix_for_stratum(
            df_stratum=df_ret,
            returner_id=str(ret),
            server_id="population_server",
            surface="HARD",
            serve_number=1,
            params=params,
            prior_alpha=prior_alpha,
            prior_beta=prior_beta,
        )
        if matrix_agg is not None:
            matrices_dict[f"{ret}|aggregate"] = matrix_agg.model_dump()
            if matrix_agg.n_opp_total >= min_sample:
                sufficient_count += 1
            if len(matrix_agg.row_labels) == 3:
                matrix_3x2_count += 1
            else:
                matrix_2x2_count += 1

        # Build specific (opponent, surface, serve_number) strata
        for surf in surfaces:
            for s_num in serve_numbers:
                mask_stratum = (df_ret["surface"] == surf) & (df_ret["serve_number"] == s_num)
                df_stratum = pd.DataFrame(df_ret[mask_stratum])
                if len(df_stratum) > 0:
                    m = build_payoff_matrix_for_stratum(
                        df_stratum=df_stratum,
                        returner_id=str(ret),
                        server_id="population_server",
                        surface=surf,
                        serve_number=s_num,
                        params=params,
                        prior_alpha=prior_alpha,
                        prior_beta=prior_beta,
                    )
                    if m is not None:
                        matrices_dict[f"{ret}|{surf}|{s_num}"] = m.model_dump()

    # 4. Save DVC Artifact
    artifact_dir = PROJECT_ROOT / "artifacts" / "models" / "game_theory"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "payoff_matrices.json"

    with artifact_path.open("w", encoding="utf-8") as f:
        json.dump(matrices_dict, f, indent=2)

    # 5. Export metrics JSON
    metrics_dir = PROJECT_ROOT / "artifacts" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_json_path = metrics_dir / "game_theory_metrics.json"

    metrics_payload = {
        "total_matrices_built": len(matrices_dict),
        "total_opponents_charted": len(returners),
        "opponents_with_sufficient_sample": sufficient_count,
        "matrix_2x2_count": matrix_2x2_count,
        "matrix_3x2_count": matrix_3x2_count,
        "prior_alpha": round(prior_alpha, 4),
        "prior_beta": round(prior_beta, 4),
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    console.print(
        f"\n[bold green]Artifact Exported:[/] {artifact_path} "
        f"({len(matrices_dict):,} matrix strata)"
    )
    console.print(f"[bold green]Metrics Exported:[/] {metrics_json_path}")

    # Summary table
    table = Table(title="Payoff Matrix Build Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    table.add_row("Total Charted Opponents", f"{len(returners):,}")
    table.add_row("Total Matrix Strata Built", f"{len(matrices_dict):,}")
    table.add_row("Opponents >= Min Sample (N >= 30)", f"{sufficient_count:,}")
    table.add_row("2x2 Payoff Matrices", f"{matrix_2x2_count:,}")
    table.add_row("3x2 Payoff Matrices (Body Included)", f"{matrix_3x2_count:,}")
    console.print(table)


if __name__ == "__main__":
    run_payoff_matrix_pipeline()
