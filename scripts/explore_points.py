# ruff: noqa: E402
"""PULSE — Point Data Exploration Script.

Explores `artifacts/validated_data/points.parquet` to provide empirical insights
into player observation counts, surface distributions, serve-win rates, and
stratum sparsity to inform Phase 3 decision making.

Usage:
    uv run python scripts/explore_points.py
"""

import sys
from pathlib import Path

# Add repository root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def explore_points_dataset(parquet_path: Path) -> None:
    """Read parquet dataset and output summary statistics."""
    if not parquet_path.exists():
        console.print(f"[bold red]Error:[/] Parquet dataset not found at {parquet_path}")
        return

    logger.info(f"Loading parquet dataset from {parquet_path}")
    df = pd.read_parquet(parquet_path)

    console.print(f"\n[bold green]Dataset Summary:[/] {len(df):,} total points\n")

    # 1. Surface Distribution
    console.print("[bold cyan]1. Surface Distribution[/]")
    surface_counts = df["surface"].value_counts(dropna=False)
    table_surface = Table(title="Surface Counts")
    table_surface.add_column("Surface", style="magenta")
    table_surface.add_column("Point Count", justify="right")
    table_surface.add_column("Percentage", justify="right")

    for surface, count in surface_counts.items():
        pct = (count / len(df)) * 100
        table_surface.add_row(str(surface), f"{count:,}", f"{pct:.2f}%")
    console.print(table_surface)
    console.print()

    # 2. Serve Number Distribution & Win Rates
    console.print("[bold cyan]2. Serve Performance[/]")
    df["is_server_win"] = df["point_winner"] == "server"
    serve_stats = (
        df.groupby("serve_number")
        .agg(total_points=("is_server_win", "count"), win_rate=("is_server_win", "mean"))
        .reset_index()
    )

    table_serve = Table(title="Serve Win Rates")
    table_serve.add_column("Serve Number", justify="center")
    table_serve.add_column("Total Points", justify="right")
    table_serve.add_column("Win Rate", justify="right")

    for _, row in serve_stats.iterrows():
        table_serve.add_row(
            f"{int(row['serve_number'])}st Serve" if row['serve_number'] == 1 else "2nd Serve",
            f"{int(row['total_points']):,}",
            f"{row['win_rate']:.4f}",
        )
    console.print(table_serve)
    console.print()

    # 3. Stratum Sparsity (Player x Surface x Serve Number)
    console.print("[bold cyan]3. Stratum Observation Sparsity[/]")
    strata = (
        df.groupby(["server", "surface", "serve_number"])
        .agg(points=("is_server_win", "count"), wins=("is_server_win", "sum"))
        .reset_index()
    )

    total_strata = len(strata)
    n_under_10 = len(strata[strata["points"] < 10])
    n_under_30 = len(strata[strata["points"] < 30])
    n_over_100 = len(strata[strata["points"] >= 100])

    pct_10 = (n_under_10 / total_strata) * 100
    pct_30 = (n_under_30 / total_strata) * 100
    pct_100 = (n_over_100 / total_strata) * 100

    console.print(
        f"Total Unique Strata (Player x Surface x Serve Number): [bold]{total_strata:,}[/]"
    )
    console.print(
        f"Strata with < 10 points (Fallback gate): [bold yellow]{n_under_10:,}[/] ({pct_10:.1f}%)"
    )
    console.print(
        f"Strata with < 30 points (Low sample): [bold yellow]{n_under_30:,}[/] ({pct_30:.1f}%)"
    )
    console.print(
        f"Strata with >= 100 points (High confidence): "
        f"[bold green]{n_over_100:,}[/] ({pct_100:.1f}%)"
    )
    console.print()

    # 4. Top 10 Most Charted Players
    console.print("[bold cyan]4. Top 10 Most Charted Players (Server Role)[/]")
    player_grp = df.groupby("server").agg(
        total_points=("is_server_win", "count"), win_rate=("is_server_win", "mean")
    )
    top_players = (
        pd.DataFrame(player_grp)
        .sort_values("total_points", ascending=False)
        .head(10)
        .reset_index()
    )

    table_players = Table(title="Top 10 Servers by Volume")
    table_players.add_column("Player ID / Name", style="yellow")
    table_players.add_column("Serve Points", justify="right")
    table_players.add_column("Serve Win Rate", justify="right")

    for _, row in top_players.iterrows():
        table_players.add_row(
            str(row["server"]),
            f"{int(row['total_points']):,}",
            f"{row['win_rate']:.4f}",
        )
    console.print(table_players)


if __name__ == "__main__":
    parquet_file = PROJECT_ROOT / "artifacts" / "validated_data" / "points.parquet"
    explore_points_dataset(parquet_file)
