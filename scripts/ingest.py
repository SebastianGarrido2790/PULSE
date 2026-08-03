"""PULSE — Raw Point Data Ingestion Script.

Reads raw point-by-point CSV data from `data/raw/`, validates every row against
`PointRecordSchema` (the pandera bulk-validation gate), and writes the validated
result to `data/validated/points.parquet`. This script performs validation and
format conversion only -- it does not transform, impute, or reinterpret raw
values. A row that fails schema validation fails the whole ingestion run; this
script never silently drops or coerces invalid rows.

Expected raw CSV schema: one column per `PointRecordSchema` field, including
`server_is_p1` (bool) -- source extraction is responsible for populating this
field from unambiguous match metadata (e.g. comparing the charted server's name
against the match's recorded player1 field), not from this script. If your raw
export does not yet include `server_is_p1`, add that derivation at the source-data
extraction stage before this script runs; ingest.py intentionally does not guess it.

Authority: Phase 2 Decision D-6 (`phase2_implementation_plan_and_decisions.md`),
`point_record.py` (Phase 2 D-5 hardening).
"""

import sys
from pathlib import Path

import pandas as pd
import yaml
from pandera.errors import SchemaErrors

from src.schemas.point_record import PointRecordSchema
from src.utils.exceptions import IngestionException
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_params(params_path: Path) -> dict:
    """Load the ingestion section of params.yaml.

    Args:
        params_path: Path to the project's params.yaml.

    Returns:
        The parsed `ingestion` config section as a dict.

    Raises:
        IngestionException: If params.yaml is missing or malformed.
    """
    if not params_path.exists():
        raise IngestionException(f"params.yaml not found at {params_path}")

    with params_path.open("r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    if "ingestion" not in params:
        raise IngestionException("params.yaml is missing the required 'ingestion' section")

    return params["ingestion"]


def read_raw_csvs(raw_dir: Path) -> pd.DataFrame:
    """Read and concatenate every CSV file in the raw data directory.

    Args:
        raw_dir: Directory containing raw point-level CSV files.

    Returns:
        A single concatenated, unvalidated DataFrame.

    Raises:
        IngestionException: If the directory is missing or contains no CSV files.
    """
    if not raw_dir.exists():
        raise IngestionException(f"Raw data directory not found: {raw_dir}")

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        raise IngestionException(f"No CSV files found in raw data directory: {raw_dir}")

    logger.info(f"ingest.read_raw_csvs file_count={len(csv_files)} raw_dir={raw_dir}")

    frames = [pd.read_csv(f, dtype=str, keep_default_na=False) for f in csv_files]
    combined = pd.concat(frames, ignore_index=True)

    logger.info(f"ingest.read_raw_csvs.complete total_rows={len(combined)}")
    return combined


def coerce_column_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce raw string-typed CSV columns to the types PointRecordSchema expects.

    CSVs are read with `dtype=str` deliberately (avoids pandas' silent type
    inference, e.g. treating a "0" score as an integer or a tournament level
    code as a float). This function performs the one explicit, intentional
    type coercion step, after which pandera validates the result.

    Args:
        df: Raw DataFrame with all-string columns.

    Returns:
        DataFrame with columns coerced to their target types.

    Raises:
        IngestionException: If a required column is missing or a boolean/int
            column contains a value that cannot be unambiguously coerced.
    """
    required_bool_cols = ["server_is_p1", "break_point", "set_point", "match_point"]
    required_int_cols = [
        "serve_number",
        "p1_games",
        "p2_games",
        "p1_sets",
        "p2_sets",
        "rally_length",
    ]

    missing = [c for c in required_bool_cols + required_int_cols if c not in df.columns]
    if missing:
        raise IngestionException(f"Raw data is missing required columns: {missing}")

    out = df.copy()

    bool_map = {
        "true": True,
        "True": True,
        "1": True,
        "TRUE": True,
        "false": False,
        "False": False,
        "0": False,
        "FALSE": False,
    }
    for col in required_bool_cols:
        unmapped = set(out[col].unique()) - set(bool_map.keys())
        if unmapped:
            raise IngestionException(
                f"Column '{col}' contains values that cannot be coerced to bool: {unmapped}"
            )
        out[col] = out[col].map(lambda val, bm=bool_map: bm[str(val)])

    for col in required_int_cols:
        try:
            out[col] = out[col].astype(int)
        except ValueError as e:
            raise IngestionException(f"Column '{col}' contains a non-integer value: {e}") from e

    if "serve_direction" in out.columns:
        out["serve_direction"] = out["serve_direction"].replace("", pd.NA)

    return out


def validate_and_write(df: pd.DataFrame, output_path: Path) -> None:
    """Validate the ingested DataFrame against PointRecordSchema and write Parquet.

    Args:
        df: Type-coerced DataFrame ready for schema validation.
        output_path: Destination path for the validated Parquet file.

    Raises:
        IngestionException: If schema validation fails. The full pandera error
            report is logged before raising -- validation failures are never
            silently dropped or partially written.
    """
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
    """Ingestion entry point: read raw CSVs, coerce types, validate, write Parquet.

    Args:
        params_path: Path to params.yaml (default: repository root).
    """
    ingestion_cfg = load_params(params_path)

    raw_dir = Path(ingestion_cfg["raw_data_dir"])
    validated_dir = Path(ingestion_cfg["validated_data_dir"])
    output_path = validated_dir / ingestion_cfg["validated_file_name"]

    raw_df = read_raw_csvs(raw_dir)
    typed_df = coerce_column_types(raw_df)
    validate_and_write(typed_df, output_path)


if __name__ == "__main__":
    try:
        main()
    except IngestionException as e:
        logger.error(f"ingest.failed error={e}")
        sys.exit(1)
