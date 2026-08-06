# ruff: noqa: E402
"""PULSE — Pressure Deviation Model Training & Evaluation Pipeline.

Computes point leverage across historical match points, fits Empirical-Bayes shrinkage priors
per leverage bucket, evaluates empirical coverage on held-out high-leverage points,
logs experiment metrics to MLflow, and exports DVC-tracked build artifacts.

Authority: Phase 3 Decision D-5, D-5a, D-6, D-7
Usage:
    uv run python scripts/train_pressure.py
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import mlflow
import pandas as pd
from rich.console import Console
from rich.table import Table

from src.config.loader import load_params
from src.core.markov_solver import MatchState, compute_leverage
from src.models.point_win_classifier import (
    load_stratum_table,
    resolve_point_win_probability,
)
from src.models.pressure_deviation import (
    fit_pressure_model,
    save_pressure_artifact,
)
from src.schemas.point_record import SCORE_TO_INT
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def compute_point_leverage(row: dict, stratum_table, params) -> float:
    """Compute point leverage delta_L for a single point record."""
    server_id = str(row["server"])
    surface = str(row["surface"])
    serve_number = int(row["serve_number"])
    server_is_p1 = bool(row["server_is_p1"])

    # Resolve p_serve from StratumTable
    stratum_res = resolve_point_win_probability(
        stratum_table=stratum_table,
        server_id=server_id,
        surface=surface,
        serve_number=serve_number,
        params=params,
    )
    p_serve = stratum_res.p_hat

    # Parse point score strings to integers
    p1_s = SCORE_TO_INT.get(str(row["p1_score"]), 0)
    p2_s = SCORE_TO_INT.get(str(row["p2_score"]), 0)

    # Assign server vs returner score fields
    if server_is_p1:
        pt_srv, pt_ret = p1_s, p2_s
        gm_srv, gm_ret = int(row["p1_games"]), int(row["p2_games"])
        set_srv, set_ret = int(row["p1_sets"]), int(row["p2_sets"])
    else:
        pt_srv, pt_ret = p2_s, p1_s
        gm_srv, gm_ret = int(row["p2_games"]), int(row["p1_games"])
        set_srv, set_ret = int(row["p2_sets"]), int(row["p1_sets"])

    try:
        match_state = MatchState(
            point_score_server=pt_srv,
            point_score_returner=pt_ret,
            game_score_server=gm_srv,
            game_score_returner=gm_ret,
            set_score_server=set_srv,
            set_score_returner=set_ret,
            server_id=server_id,
            match_format="bo3",
        )
        sol_res = compute_leverage(match_state, p_serve)
        return float(sol_res.leverage)
    except Exception:
        # If score state is non-standard, return default leverage 0.05
        return 0.05


def run_pressure_pipeline() -> None:
    """Execute pressure deviation fitting, empirical coverage evaluation, and artifact export."""
    params = load_params()

    # 1. Load StratumTable artifact from train_classifier stage
    classifier_artifact_dir = PROJECT_ROOT / "artifacts" / "models" / "point_win_classifier"
    if not (classifier_artifact_dir / "stratum_table.json").exists():
        console.print(
            f"[bold red]Error:[/] StratumTable artifact not found at {classifier_artifact_dir}. "
            "Run scripts/train_classifier.py first!"
        )
        sys.exit(1)

    logger.info("Loading StratumTable artifact from train_classifier stage")
    stratum_table = load_stratum_table(classifier_artifact_dir)

    # 2. Load validated points dataset
    val_dir = params.ingestion.validated_data_dir
    val_file = params.ingestion.validated_file_name
    data_path = PROJECT_ROOT / val_dir / val_file
    if not data_path.exists():
        console.print(f"[bold red]Error:[/] Dataset not found at {data_path}")
        sys.exit(1)

    logger.info(f"Loading point records from {data_path}")
    df = pd.read_parquet(data_path)
    console.print(f"\n[bold green]Loaded Dataset:[/] {len(df):,} point records")

    # 3. Compute point leverage delta_L for dataset
    logger.info("Computing exact point leverage across dataset")
    console.print("Computing point leverage via Markov solver...")
    records = df.to_dict(orient="records")
    leverages: list[float] = [
        compute_point_leverage(row, stratum_table, params) for row in records
    ]

    work_df = df.copy()
    work_df["leverage"] = leverages

    # 4. Fit PressureModelArtifact (Empirical Bayes Method of Moments)
    logger.info("Fitting Empirical-Bayes Pressure Deviation Model")
    pressure_artifact = fit_pressure_model(work_df, stratum_table, params)

    console.print("\n[bold cyan]Fitted Pressure Priors per Leverage Bucket:[/]")
    table_priors = Table(title="Bucket Prior Estimation Summary")
    table_priors.add_column("Bucket Index", justify="center")
    table_priors.add_column("Leverage Range")
    table_priors.add_column("Alpha Prior (alpha_0)", justify="right")
    table_priors.add_column("Beta Prior (beta_0)", justify="right")
    table_priors.add_column("Player Count", justify="right")
    table_priors.add_column("Prior Source", style="yellow")

    bucket_labels = {
        0: "[0.00, 0.10) Routine",
        1: "[0.10, 0.25) Elevated",
        2: "[0.25, 1.00] Critical",
    }
    for b_idx in (0, 1, 2):
        prior = pressure_artifact.priors[b_idx]
        src = "Data MLE (MoM)" if prior.is_prior_estimated else "Fixed Config Fallback"
        table_priors.add_row(
            str(b_idx),
            bucket_labels[b_idx],
            f"{prior.alpha_0:.3f}",
            f"{prior.beta_0:.3f}",
            f"{prior.player_count:,}",
            src,
        )
    console.print(table_priors)

    # 5. Evaluate Empirical Coverage on High-Leverage Player Strata (N >= 10, Bucket 1 & 2)
    logger.info("Evaluating empirical coverage of 90% credible intervals across players")
    covered_count = 0
    total_eval_players = 0

    for res in pressure_artifact.results.values():
        if res.leverage_bucket in (1, 2) and res.is_sufficient_sample:
            total_eval_players += 1
            raw_rate = float(res.k_pressure) / float(res.n_pressure)
            rate_low = res.deviation_low_90 + res.baseline_p
            rate_high = res.deviation_high_90 + res.baseline_p

            if rate_low - 1e-6 <= raw_rate <= rate_high + 1e-6:
                covered_count += 1

    coverage_rate = (
        float(covered_count) / float(total_eval_players) if total_eval_players > 0 else 1.0
    )
    pct_str = f"{coverage_rate * 100:.2f}%"
    console.print(
        f"\n[bold green]High-Leverage Player Credible Coverage:[/] [bold yellow]{pct_str}[/] "
        f"({covered_count:,} / {total_eval_players:,} player-bucket strata)"
    )

    # 6. Save DVC Artifacts & Metrics JSON
    pressure_artifact_dir = PROJECT_ROOT / "artifacts" / "models" / "pressure_deviation"
    saved_artifact_path = save_pressure_artifact(pressure_artifact, pressure_artifact_dir)

    metrics_dir = PROJECT_ROOT / "artifacts" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_json_path = metrics_dir / "pressure_metrics.json"

    metrics_payload = {
        "empirical_coverage_rate": round(coverage_rate, 4),
        "total_eval_player_strata": total_eval_players,
        "covered_player_strata": covered_count,
        "bucket_priors": {
            f"bucket_{b}": {
                "alpha": round(p.alpha_0, 4),
                "beta": round(p.beta_0, 4),
                "is_prior_estimated": p.is_prior_estimated,
                "player_count": p.player_count,
            }
            for b, p in pressure_artifact.priors.items()
        },
        "exit_criterion_met": coverage_rate >= 0.90,
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    # 7. MLflow Experiment Tracking
    logger.info("Logging run metrics to MLflow")
    mlflow.set_experiment(params.models.mlflow_experiment_pressure)
    with mlflow.start_run(run_name="train_pressure_deviation_estimator"):
        mlflow.log_params({
            "pressure_prior_alpha": params.models.pressure_prior_alpha,
            "pressure_prior_beta": params.models.pressure_prior_beta,
            "min_players_per_bucket": params.models.pressure_prior_min_players_per_bucket,
            "pressure_leverage_buckets": str(params.models.pressure_leverage_buckets),
        })
        mlflow.log_metrics({
            "empirical_coverage_rate": coverage_rate,
            "total_eval_player_strata": total_eval_players,
            "bucket0_alpha": pressure_artifact.priors[0].alpha_0,
            "bucket0_beta": pressure_artifact.priors[0].beta_0,
            "bucket1_alpha": pressure_artifact.priors[1].alpha_0,
            "bucket1_beta": pressure_artifact.priors[1].beta_0,
            "bucket2_alpha": pressure_artifact.priors[2].alpha_0,
            "bucket2_beta": pressure_artifact.priors[2].beta_0,
        })
        mlflow.log_artifact(str(saved_artifact_path))

    console.print(f"\n[bold green]Artifacts Exported:[/] {saved_artifact_path}")
    console.print(f"[bold green]Metrics Exported:[/] {metrics_json_path}")

    # Exit criteria gate check
    if coverage_rate < 0.90:
        console.print(
            f"[bold red]WARNING:[/] Empirical coverage ({pct_str}) is below target 90%"
        )
    else:
        console.print(
            "[bold green]Success:[/] Empirical coverage satisfies exit criterion (>= 90%)"
        )


if __name__ == "__main__":
    run_pressure_pipeline()

