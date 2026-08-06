# ruff: noqa: E402
"""PULSE — Point-Win Classifier Training & Evaluation Pipeline.

Trains the Hierarchical Empirical Stratum Estimator from artifacts/validated_data/points.parquet,
evaluates ROC-AUC on a leakage-free holdout partition, logs experiment metrics to MLflow,
and persists DVC-tracked build artifacts to artifacts/models/point_win_classifier/.

Authority: Phase 3 Decision D-3, D-3a, D-6, D-7
Usage:
    uv run python scripts/train_classifier.py
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import mlflow
import pandas as pd
from rich.console import Console
from rich.table import Table
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score

from src.config.loader import load_params
from src.models.point_win_classifier import (
    FallbackTier,
    build_stratum_table,
    resolve_point_win_probability,
    save_stratum_table,
    split_points_data,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_training_pipeline() -> None:
    """Execute classifier training, holdout evaluation, MLflow logging, and artifact export."""
    params = load_params()
    val_dir = params.ingestion.validated_data_dir
    val_file = params.ingestion.validated_file_name
    data_path = PROJECT_ROOT / val_dir / val_file

    if not data_path.exists():
        console.print(f"[bold red]Error:[/] Validated points dataset not found at {data_path}")
        sys.exit(1)

    logger.info(f"Loading point records from {data_path}")
    df = pd.read_parquet(data_path)
    console.print(f"\n[bold green]Loaded Dataset:[/] {len(df):,} point records")

    # 1. Leakage-Free Train/Test Partitioning
    train_ratio = 1.0 - params.models.train_test_split
    train_df, test_df = split_points_data(
        df, train_ratio=train_ratio, random_state=params.models.random_state
    )
    console.print(
        f"Training partition: {len(train_df):,} points | "
        f"Holdout evaluation: {len(test_df):,} points"
    )

    # 2. Build StratumTable strictly from training partition
    logger.info("Building StratumTable from training partition")
    stratum_table = build_stratum_table(train_df, default_p=params.solver.default_p_serve)

    console.print("\n[bold cyan]StratumTable Compiled Summary:[/]")
    console.print(f"  • Tier 0 Exact Strata: {len(stratum_table.tier0_exact):,}")
    console.print(f"  • Tier 1 Player Overall Strata: {len(stratum_table.tier1_player):,}")
    console.print(f"  • Tier 2 Surface Population Strata: {len(stratum_table.tier2_surface):,}")

    # 3. Evaluate Holdout Test Partition
    logger.info("Evaluating holdout test partition")
    y_true: list[int] = []
    y_pred: list[float] = []
    tier_counts = {tier: 0 for tier in FallbackTier}

    test_records = test_df.to_dict(orient="records")
    for row in test_records:
        server = str(row["server"])
        surface = str(row["surface"])
        serve_num = int(row["serve_number"])
        win_label = 1 if row["point_winner"] == "server" else 0

        result = resolve_point_win_probability(
            stratum_table=stratum_table,
            server_id=server,
            surface=surface,
            serve_number=serve_num,
            params=params,
        )

        y_true.append(win_label)
        y_pred.append(result.p_hat)
        tier_counts[result.fallback_tier] += 1

    auc_score = float(roc_auc_score(y_true, y_pred))
    console.print(f"\n[bold green]Holdout ROC-AUC Score:[/] [bold yellow]{auc_score:.4f}[/]")

    # Tier Resolution Breakdown
    table_tiers = Table(title="Holdout Fallback Tier Resolution Breakdown")
    table_tiers.add_column("Tier", style="magenta")
    table_tiers.add_column("Description")
    table_tiers.add_column("Query Count", justify="right")
    table_tiers.add_column("Percentage", justify="right")

    tier_names = {
        FallbackTier.EXACT_STRATUM: "Tier 0 (Exact Stratum)",
        FallbackTier.PLAYER_OVERALL: "Tier 1 (Player Overall)",
        FallbackTier.SURFACE_POPULATION: "Tier 2 (Surface Population)",
        FallbackTier.GLOBAL_DEFAULT: "Tier 3 (Global Default)",
    }

    for tier, count in tier_counts.items():
        pct = (count / len(test_df)) * 100
        table_tiers.add_row(
            f"Tier {int(tier)}", tier_names[tier], f"{count:,}", f"{pct:.2f}%"
        )
    console.print(table_tiers)

    # 4. Generate Calibration Curve Plot
    prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=10, strategy="uniform")
    plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, marker="o", linewidth=2, label="Hierarchical Stratum Estimator")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect Calibration")
    plt.xlabel("Mean Predicted Probability (p_hat)")
    plt.ylabel("Fraction of Positives (Observed Serve Wins)")
    plt.title(f"Point-Win Classifier Calibration Curve (Holdout AUC = {auc_score:.4f})")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)

    artifact_model_dir = PROJECT_ROOT / "artifacts" / "models" / "point_win_classifier"
    artifact_model_dir.mkdir(parents=True, exist_ok=True)
    calib_plot_path = artifact_model_dir / "calibration_curve.png"
    plt.savefig(calib_plot_path, dpi=300, bbox_inches="tight")
    plt.close()

    # 5. Persist DVC Artifacts & Metrics JSON
    saved_table_path = save_stratum_table(stratum_table, artifact_model_dir)

    metrics_dir = PROJECT_ROOT / "artifacts" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_json_path = metrics_dir / "classifier_metrics.json"

    metrics_payload = {
        "auc_score": round(auc_score, 4),
        "holdout_sample_size": len(test_df),
        "train_sample_size": len(train_df),
        "tier_counts": {tier_names[t]: count for t, count in tier_counts.items()},
        "exit_criterion_met": auc_score >= 0.65,
    }
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    # 6. MLflow Experiment Tracking
    logger.info("Logging run metrics to MLflow")
    mlflow.set_experiment(params.models.mlflow_experiment_classifier)
    with mlflow.start_run(run_name="train_hierarchical_stratum_estimator"):
        mlflow.log_params({
            "train_test_split": params.models.train_test_split,
            "random_state": params.models.random_state,
            "min_stratum_observations": params.uncertainty.min_stratum_observations,
            "min_player_observations": params.uncertainty.min_player_observations,
            "min_surface_observations": params.uncertainty.min_surface_observations,
            "default_p_serve": params.solver.default_p_serve,
        })
        mlflow.log_metrics({
            "auc_score": auc_score,
            "tier0_count": tier_counts[FallbackTier.EXACT_STRATUM],
            "tier1_count": tier_counts[FallbackTier.PLAYER_OVERALL],
            "tier2_count": tier_counts[FallbackTier.SURFACE_POPULATION],
            "tier3_count": tier_counts[FallbackTier.GLOBAL_DEFAULT],
        })
        mlflow.log_artifact(str(calib_plot_path))
        mlflow.log_artifact(str(saved_table_path))

    console.print(f"\n[bold green]Artifacts Exported:[/] {saved_table_path}")
    console.print(f"[bold green]Metrics Exported:[/] {metrics_json_path}")

    # Exit criteria gate check
    if auc_score < 0.65:
        console.print(
            f"[bold red]WARNING:[/] Holdout AUC ({auc_score:.4f}) is below target 0.65"
        )
    else:
        console.print("[bold green]Success:[/] Holdout AUC satisfies exit criterion (>= 0.65)")


if __name__ == "__main__":
    run_training_pipeline()
