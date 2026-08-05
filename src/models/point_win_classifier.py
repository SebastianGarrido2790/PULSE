"""PULSE — Point-Win Classifier (Hierarchical Empirical Stratum Estimator).

Calculates observed serve-win rates across nested player, surface, and serve-number strata,
returning point win probabilities p_hat, observation counts N, and explicit fallback tier tracking.

Authority: ADR-005 Amendment 1, point_win_classifier_spec.md
"""

from enum import IntEnum
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, model_validator
from sklearn.model_selection import train_test_split

from src.config.loader import Params, load_params
from src.schemas.point_record import Surface
from src.utils.exceptions import ModelInferenceError


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
        """Ensure p_hat equals wins / sample_size when sample_size > 0."""
        if self.sample_size > 0:
            expected_p = float(self.wins) / float(self.sample_size)
            if abs(self.p_hat - expected_p) > 1e-5:
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


class StratumTable(BaseModel):
    """Serializable container for all hierarchical stratum win-rate lookup tables."""

    tier0_exact: dict[str, StratumEntry] = Field(
        default_factory=dict, description="Key: server|surface|serve_number"
    )
    tier1_player: dict[str, StratumEntry] = Field(
        default_factory=dict, description="Key: server|serve_number"
    )
    tier2_surface: dict[str, StratumEntry] = Field(
        default_factory=dict, description="Key: surface|serve_number"
    )
    global_default_p: float = Field(
        default=0.62, ge=0.0, le=1.0, description="Global fallback win probability"
    )


def format_exact_key(server_id: str, surface: str | Surface, serve_number: int) -> str:
    """Format exact stratum key: server_id|surface|serve_number."""
    surf_str = surface.value if isinstance(surface, Surface) else str(surface).upper()
    return f"{server_id}|{surf_str}|{serve_number}"


def format_player_key(server_id: str, serve_number: int) -> str:
    """Format player overall key: server_id|serve_number."""
    return f"{server_id}|{serve_number}"


def format_surface_key(surface: str | Surface, serve_number: int) -> str:
    """Format surface population key: surface|serve_number."""
    surf_str = surface.value if isinstance(surface, Surface) else str(surface).upper()
    return f"{surf_str}|{serve_number}"


def split_points_data(
    df: pd.DataFrame, train_ratio: float = 0.8, random_state: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split point records into training and holdout evaluation partitions.

    Guarantees no data leakage by allowing StratumTable to be built exclusively
    from the training partition.

    Args:
        df: Input points DataFrame.
        train_ratio: Fraction of data for training (e.g. 0.8 for 80/20 split).
        random_state: Reproducibility seed.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (train_df, test_df)
    """
    test_size = 1.0 - train_ratio
    res = train_test_split(df, test_size=test_size, random_state=random_state, shuffle=True)
    train_raw, test_raw = res[0], res[1]
    train_df = pd.DataFrame(train_raw).reset_index(drop=True)
    test_df = pd.DataFrame(test_raw).reset_index(drop=True)
    return train_df, test_df


def build_stratum_table(df: pd.DataFrame, default_p: float = 0.62) -> StratumTable:
    """Build hierarchical stratum lookup table from point records DataFrame.

    Computes win counts k, sample sizes N, and win rates p_hat for all three
    aggregation tiers (exact stratum, player overall, surface population).

    Args:
        df: Points DataFrame with server, surface, serve_number, point_winner columns.
        default_p: Global default p_serve fallback.

    Returns:
        StratumTable object containing all compiled lookup dictionaries.

    Raises:
        ModelInferenceError: If required columns are missing from the input DataFrame.
    """
    required_cols = {"server", "surface", "serve_number", "point_winner"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ModelInferenceError(f"Missing required columns for stratum table build: {missing}")

    # Binary indicator: server won point
    is_server_win = (df["point_winner"] == "server").astype(int)
    work_df = df.copy()
    work_df["is_server_win"] = is_server_win
    work_df["surface_str"] = work_df["surface"].astype(str).str.upper()

    # Tier 0: Exact Stratum (server, surface, serve_number)
    t0_grp = (
        work_df.groupby(["server", "surface_str", "serve_number"])
        .agg(wins=("is_server_win", "sum"), sample_size=("is_server_win", "count"))
        .reset_index()
    )
    tier0_exact: dict[str, StratumEntry] = {}
    for row in t0_grp.to_dict(orient="records"):
        srv = str(row["server"])
        surf = str(row["surface_str"])
        srv_num = int(row["serve_number"])
        key = format_exact_key(srv, surf, srv_num)
        n = int(row["sample_size"])
        k = int(row["wins"])
        p_hat = float(k) / float(n) if n > 0 else default_p
        tier0_exact[key] = StratumEntry(wins=k, sample_size=n, p_hat=p_hat)

    # Tier 1: Player Overall (server, serve_number)
    t1_grp = (
        work_df.groupby(["server", "serve_number"])
        .agg(wins=("is_server_win", "sum"), sample_size=("is_server_win", "count"))
        .reset_index()
    )
    tier1_player: dict[str, StratumEntry] = {}
    for row in t1_grp.to_dict(orient="records"):
        srv = str(row["server"])
        srv_num = int(row["serve_number"])
        key = format_player_key(srv, srv_num)
        n = int(row["sample_size"])
        k = int(row["wins"])
        p_hat = float(k) / float(n) if n > 0 else default_p
        tier1_player[key] = StratumEntry(wins=k, sample_size=n, p_hat=p_hat)

    # Tier 2: Population Surface (surface, serve_number)
    t2_grp = (
        work_df.groupby(["surface_str", "serve_number"])
        .agg(wins=("is_server_win", "sum"), sample_size=("is_server_win", "count"))
        .reset_index()
    )
    tier2_surface: dict[str, StratumEntry] = {}
    for row in t2_grp.to_dict(orient="records"):
        surf = str(row["surface_str"])
        srv_num = int(row["serve_number"])
        key = format_surface_key(surf, srv_num)
        n = int(row["sample_size"])
        k = int(row["wins"])
        p_hat = float(k) / float(n) if n > 0 else default_p
        tier2_surface[key] = StratumEntry(wins=k, sample_size=n, p_hat=p_hat)

    return StratumTable(
        tier0_exact=tier0_exact,
        tier1_player=tier1_player,
        tier2_surface=tier2_surface,
        global_default_p=default_p,
    )


def resolve_point_win_probability(
    stratum_table: StratumTable,
    server_id: str,
    surface: str | Surface,
    serve_number: int,
    params: Params | None = None,
) -> StratumLookupResult:
    """Resolve point-win probability p_hat and sample size N through 4-tier fallback hierarchy.

    Algorithm (Spec §3):
        Tier 0: Look up exact (server_id, surface, serve_number). Return if N >= min_stratum.
        Tier 1: Look up player overall (server_id, serve_number). Return if N >= min_player.
        Tier 2: Look up population surface (surface, serve_number). Return if N >= min_surface.
        Tier 3: Return global default_p_serve with sample_size=0, fallback_tier=GLOBAL_DEFAULT.

    Args:
        stratum_table: StratumTable lookup container.
        server_id: Server player identifier string.
        surface: Surface enum or string ("HARD", "CLAY", "GRASS").
        serve_number: Serve attempt number (1 or 2).
        params: Optional Params object. Loaded via load_params() if None.

    Returns:
        StratumLookupResult detailing resolved p_hat, sample_size, wins, and fallback_tier.
    """
    cfg = params if params is not None else load_params()

    surf_str = surface.value if isinstance(surface, Surface) else str(surface).upper()

    # Tier 0 Check: Exact Stratum (server_id, surface, serve_number)
    key_t0 = format_exact_key(server_id, surf_str, serve_number)
    if key_t0 in stratum_table.tier0_exact:
        entry = stratum_table.tier0_exact[key_t0]
        if entry.sample_size >= cfg.uncertainty.min_stratum_observations:
            return StratumLookupResult(
                p_hat=entry.p_hat,
                sample_size=entry.sample_size,
                wins=entry.wins,
                fallback_tier=FallbackTier.EXACT_STRATUM,
                server_id=server_id,
                surface=surf_str,
                serve_number=serve_number,
            )

    # Tier 1 Check: Player Overall (server_id, serve_number)
    key_t1 = format_player_key(server_id, serve_number)
    if key_t1 in stratum_table.tier1_player:
        entry = stratum_table.tier1_player[key_t1]
        if entry.sample_size >= cfg.uncertainty.min_player_observations:
            return StratumLookupResult(
                p_hat=entry.p_hat,
                sample_size=entry.sample_size,
                wins=entry.wins,
                fallback_tier=FallbackTier.PLAYER_OVERALL,
                server_id=server_id,
                surface=surf_str,
                serve_number=serve_number,
            )

    # Tier 2 Check: Population Surface (surface, serve_number)
    key_t2 = format_surface_key(surf_str, serve_number)
    if key_t2 in stratum_table.tier2_surface:
        entry = stratum_table.tier2_surface[key_t2]
        if entry.sample_size >= cfg.uncertainty.min_surface_observations:
            return StratumLookupResult(
                p_hat=entry.p_hat,
                sample_size=entry.sample_size,
                wins=entry.wins,
                fallback_tier=FallbackTier.SURFACE_POPULATION,
                server_id=server_id,
                surface=surf_str,
                serve_number=serve_number,
            )

    # Tier 3 Fallback: Global Default
    return StratumLookupResult(
        p_hat=cfg.solver.default_p_serve,
        sample_size=0,
        wins=0,
        fallback_tier=FallbackTier.GLOBAL_DEFAULT,
        server_id=server_id,
        surface=surf_str,
        serve_number=serve_number,
    )


def save_stratum_table(stratum_table: StratumTable, artifact_dir: Path) -> Path:
    """Save StratumTable artifact to JSON file.

    Args:
        stratum_table: StratumTable object.
        artifact_dir: Output artifact directory.

    Returns:
        Path to saved json artifact file.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifact_dir / "stratum_table.json"
    out_path.write_text(stratum_table.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_stratum_table(artifact_dir: Path) -> StratumTable:
    """Load StratumTable artifact from JSON file.

    Args:
        artifact_dir: Path to artifact directory containing stratum_table.json.

    Returns:
        StratumTable instance.

    Raises:
        ModelInferenceError: If artifact file is missing or unparseable.
    """
    target = artifact_dir / "stratum_table.json"
    if not target.exists():
        raise ModelInferenceError(f"StratumTable artifact not found at [{target}]")

    try:
        content = target.read_text(encoding="utf-8")
        return StratumTable.model_validate_json(content)
    except Exception as e:
        raise ModelInferenceError(f"Failed to load StratumTable from [{target}]: {e}") from e
