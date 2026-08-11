# ruff: noqa: E402
"""PULSE — Raw Point Data Ingestion Script.

Reads raw point-by-point CSV data from `data/raw/` (The Match Charting Project
format), transforms MCP raw columns to PULSE domain fields, validates every row
against `PointRecordSchema`, and writes the validated result to
`artifacts/validated_data/points.parquet`.

MCP Column Mapping:
  - `match_id`: Joined between points and matches CSVs.
  - `server_is_p1`: `Svr == '1'` (Player1 is a fixed per-match identity in MCP).
  - `server` / `returner`: Player names joined from matches metadata.
  - `point_winner`: `"server"` if `PtWinner == Svr` else `"returner"`.
  - `serve_number`: `2` if `2nd` column is populated else `1`.
  - `serve_direction`: First character of `1st`/`2nd` notation ('4'->wide, '5'->body, '6'->T).
  - `p1_score` / `p2_score`: Derived from `Pts` score string.

Authority: Phase 2 Decision D-6 (`phase2_implementation_plan_and_decisions.md`),
`point_record.py` (Phase 2 D-5 hardening).
"""

import sys
from pathlib import Path

# Add repository root to sys.path for src package resolution
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any

import pandas as pd
import yaml
from pandera.errors import SchemaErrors

from src.schemas.point_record import PointRecordSchema
from src.utils.exceptions import IngestionException
from src.utils.logger import get_logger

logger = get_logger(__name__)


def parse_serve_direction(notation: str) -> str | None:
    """Extract serve direction from an MCP shot-notation string.

    Per the Match Charting Project's quick-start guide, the first character of
    the `1st`/`2nd` column encodes serve direction:
    '4' = wide, '5' = body, '6' = down the T.
    """
    if not notation or not isinstance(notation, str):
        return None
    code_map = {"4": "wide", "5": "body", "6": "T"}
    return code_map.get(notation[0])


def load_params(params_path: Path) -> dict:
    """Load the ingestion section of params.yaml."""
    if not params_path.exists():
        raise IngestionException(f"params.yaml not found at {params_path}")

    with params_path.open("r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    if "ingestion" not in params:
        raise IngestionException("params.yaml is missing the required 'ingestion' section")

    return params["ingestion"]


def read_raw_data(raw_dir: Path) -> pd.DataFrame:
    """Read raw points CSVs and matches CSVs, merging metadata on match_id."""
    if not raw_dir.exists():
        raise IngestionException(f"Raw data directory not found: {raw_dir}")

    points_files = sorted(raw_dir.glob("*points*.csv"))
    matches_files = sorted(raw_dir.glob("*matches*.csv"))

    if not points_files:
        raise IngestionException(f"No points CSV files found in raw data directory: {raw_dir}")

    logger.info(
        f"ingest.read_raw_data points_files={len(points_files)} "
        f"matches_files={len(matches_files)} raw_dir={raw_dir}"
    )

    pts_frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in points_files]
    pts_df = pd.concat(pts_frames, ignore_index=True)

    if matches_files:
        mat_frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in matches_files]
        mat_df = pd.concat(mat_frames, ignore_index=True).drop_duplicates(subset=["match_id"])
        merged = pts_df.merge(mat_df, on="match_id", how="left")
    else:
        merged = pts_df

    logger.info(f"ingest.read_raw_data.complete total_rows={len(merged)}")
    return pd.DataFrame(merged)


def transform_mcp_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw MCP DataFrame columns into PointRecordSchema format."""
    df = raw_df.copy()

    # 1. Match state & score strings
    df["match_id"] = df["match_id"].astype(str)
    df["point_id"] = df["match_id"] + "_p" + df["Pt"].astype(str)

    # 2. Player roles & server identity
    df["server_is_p1"] = df["Svr"].astype(str).str.strip() == "1"

    def get_server_name(r: pd.Series) -> str:
        if bool(r.get("server_is_p1", False)):
            return str(r.get("Player 1", "Player 1"))
        return str(r.get("Player 2", "Player 2"))

    def get_returner_name(r: pd.Series) -> str:
        if bool(r.get("server_is_p1", False)):
            return str(r.get("Player 2", "Player 2"))
        return str(r.get("Player 1", "Player 1"))

    df["server"] = df.apply(get_server_name, axis=1)
    df["returner"] = df.apply(get_returner_name, axis=1)

    # 3. Surface
    surface_col = df["Surface"] if "Surface" in df.columns else pd.Series(["HARD"] * len(df))
    df["surface"] = (
        surface_col.astype(str).str.upper().replace({"": "HARD", "NONE": "HARD", "UNKNOWN": "HARD"})
    )
    df["surface"] = df["surface"].apply(lambda s: s if s in ["HARD", "CLAY", "GRASS"] else "HARD")

    # 4. Point winner
    def get_point_winner(r: pd.Series) -> str:
        winner = str(r.get("PtWinner", "")).strip()
        svr = str(r.get("Svr", "")).strip()
        return "server" if winner == svr else "returner"

    df["point_winner"] = df.apply(get_point_winner, axis=1)

    # 5. Serve number & direction
    def get_serve_info(row: pd.Series) -> tuple[int, str | None]:
        st_2nd = str(row.get("2nd", "")).strip()
        st_1st = str(row.get("1st", "")).strip()
        if st_2nd != "":
            return 2, parse_serve_direction(st_2nd)
        return 1, parse_serve_direction(st_1st)

    serve_info = df.apply(get_serve_info, axis=1)
    df["serve_number"] = [info[0] for info in serve_info]
    df["serve_direction"] = [info[1] for info in serve_info]

    # 6. Scores (Pts string format "p1_score-p2_score")
    def parse_scores(row: pd.Series) -> tuple[str, str]:
        pts = str(row.get("Pts", "")).strip()
        if "-" in pts:
            parts = pts.split("-")
            s1, s2 = parts[0].strip(), parts[1].strip()
            s1 = "AD" if s1 in ["A", "AD"] else (s1 if s1 in ["0", "15", "30", "40"] else "0")
            s2 = "AD" if s2 in ["A", "AD"] else (s2 if s2 in ["0", "15", "30", "40"] else "0")
            return s1, s2
        return "0", "0"

    scores = df.apply(parse_scores, axis=1)
    df["p1_score"] = [sc[0] for sc in scores]
    df["p2_score"] = [sc[1] for sc in scores]

    # 7. Games, Sets, Rally length
    def safe_int(val: Any, default: int = 0) -> int:
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            return default

    df["p1_games"] = df["Gm1"].apply(lambda x: safe_int(x, 0))
    df["p2_games"] = df["Gm2"].apply(lambda x: safe_int(x, 0))
    df["p1_sets"] = df["Set1"].apply(lambda x: safe_int(x, 0))
    df["p2_sets"] = df["Set2"].apply(lambda x: safe_int(x, 0))
    df["rally_length"] = (
        df["rallyCount"].apply(lambda x: safe_int(x, 0)) if "rallyCount" in df.columns else 0
    )

    # 8. Boolean flags
    df["break_point"] = False
    df["set_point"] = False
    df["match_point"] = False

    # Select target columns
    target_cols = [
        "match_id",
        "point_id",
        "server",
        "returner",
        "server_is_p1",
        "surface",
        "serve_number",
        "serve_direction",
        "p1_score",
        "p2_score",
        "p1_games",
        "p2_games",
        "p1_sets",
        "p2_sets",
        "rally_length",
        "point_winner",
        "break_point",
        "set_point",
        "match_point",
    ]
    return pd.DataFrame(df[target_cols])


def validate_and_write(df: pd.DataFrame, output_path: Path) -> None:
    """Validate DataFrame against PointRecordSchema and write Parquet."""
    try:
        validated = PointRecordSchema.validate(df, lazy=True)
    except SchemaErrors as err:
        failures = err.failure_cases.to_dict(orient="records")[:20]
        logger.error(
            f"ingest.validation_failed failure_count={len(err.failure_cases)} failures={failures}"
        )
        raise IngestionException(
            f"Schema validation failed on {len(err.failure_cases)} row(s). "
            f"See logged failure_cases for detail. No output written."
        ) from err

    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated.to_parquet(output_path, index=False)

    logger.info(
        f"ingest.validate_and_write.complete "
        f"rows_written={len(validated)} output_path={output_path}"
    )


def main(params_path: Path = Path("params.yaml")) -> None:
    """Ingestion entry point: read raw CSVs, transform, validate, write Parquet."""
    ingestion_cfg = load_params(params_path)

    raw_dir = Path(ingestion_cfg["raw_data_dir"])
    validated_dir = Path(ingestion_cfg["validated_data_dir"])
    output_path = validated_dir / ingestion_cfg["validated_file_name"]

    raw_df = read_raw_data(raw_dir)
    transformed_df = transform_mcp_dataframe(raw_df)
    validate_and_write(transformed_df, output_path)


if __name__ == "__main__":
    try:
        main()
    except IngestionException as e:
        logger.error(f"ingest.failed error={e}")
        sys.exit(1)
