"""PULSE — Strongly Typed Configuration Loader.

Loads params.yaml into Pydantic v2 data models to enforce quantitative threshold contracts,
model hyperparameters, and latency budgets across the MLOps pipeline and Markov engine.

Authority: Phase 3 Decision D-1, params.yaml schema.
"""

import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.utils.exceptions import ConfigException as ConfigException

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ThresholdsParams(BaseModel):
    """Threshold parameters for leverage escalation and exploit gates."""

    leverage_escalation: float = Field(..., ge=0.0, le=1.0)
    exploit_min_sample_size: int = Field(..., ge=1)
    game_theory_3x3_min_sample_size: int = Field(default=50, ge=1)


class UncertaintyParams(BaseModel):
    """Uncertainty parameters for Wilson interval & 4-tier fallback gates."""

    confidence_level: float = Field(..., ge=0.5, le=0.999)
    min_stratum_observations: int = Field(..., ge=1)
    min_player_observations: int = Field(..., ge=1)
    min_surface_observations: int = Field(..., ge=1)
    default_fallback_margin: float = Field(..., ge=0.0, le=0.5)


class SolverParams(BaseModel):
    """Deterministic Markov solver parameters."""

    tolerance: float = Field(..., gt=0.0)
    default_p_serve: float = Field(..., ge=0.0, le=1.0)


class IngestionParams(BaseModel):
    """Data ingestion directory and file specs."""

    raw_data_dir: str
    validated_data_dir: str
    validated_file_name: str


class LatencyParams(BaseModel):
    """Per-node real-time latency budgets (in milliseconds)."""

    state_monitor_ms: int = Field(..., gt=0)
    triggered_node_ms: int = Field(..., gt=0)


class LLMParams(BaseModel):
    """LLM provider and narrative generation parameters."""

    provider: str
    model_name: str
    max_tokens: int = Field(..., gt=0)
    temperature: float = Field(..., ge=0.0, le=1.0)
    request_timeout_s: float = Field(..., gt=0.0)


class ModelsParams(BaseModel):
    """Tier 1 ML model training and experiment tracking parameters."""

    calibration_method: str
    point_win_classifier: str
    solver_tolerance: float = Field(..., gt=0.0)
    train_test_split: float = Field(..., ge=0.01, le=0.99)
    random_state: int
    max_mean_absolute_calibration_error: float = Field(..., gt=0.0, le=0.10)
    min_holdout_auc_sanity: float = Field(..., ge=0.50, le=1.0)
    mlflow_experiment_classifier: str
    mlflow_experiment_pressure: str
    pressure_prior_alpha: float = Field(..., gt=0.0)
    pressure_prior_beta: float = Field(..., gt=0.0)
    pressure_prior_min_players_per_bucket: int = Field(..., ge=1)
    game_theory_prior_alpha: float = Field(default=2.0, gt=0.0)
    game_theory_prior_beta: float = Field(default=2.0, gt=0.0)
    game_theory_min_observations_per_cell: int = Field(default=5, ge=1)
    game_theory_anticipation_boost: float = Field(default=0.12, ge=0.0, le=0.5)
    game_theory_positioning_penalty: float = Field(default=0.05, ge=0.0, le=0.5)
    pressure_leverage_buckets: list[float]


class CIParams(BaseModel):
    """Code quality and CI/CD gate parameters."""

    line_ceiling: int = Field(..., gt=0)
    min_coverage_pct: int = Field(..., ge=0, le=100)


class Params(BaseModel):
    """Top-level configuration container for PULSE params.yaml."""

    thresholds: ThresholdsParams
    uncertainty: UncertaintyParams
    solver: SolverParams
    ingestion: IngestionParams
    latency: LatencyParams
    llm: LLMParams
    models: ModelsParams
    ci: CIParams


def load_params(config_path: Path | None = None) -> Params:
    """Load and validate params.yaml into a strongly typed Params Pydantic model.

    Args:
        config_path: Optional path to params.yaml. Resolves relative to repository
            root if None.

    Returns:
        Params: Validated Pydantic container with typed config parameters.

    Raises:
        ConfigException: If the file is missing, unparseable, or fails schema validation.
    """
    target_path = PROJECT_ROOT / "params.yaml" if config_path is None else config_path

    if not target_path.exists():
        raise ConfigException(f"Configuration file not found at [{target_path}]")

    try:
        with target_path.open("r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as e:
        raise ConfigException(f"Failed to parse YAML file [{target_path}]: {e}", sys) from e

    if not isinstance(raw_data, dict):
        raise ConfigException(
            f"Invalid YAML structure in [{target_path}]: expected dict, got {type(raw_data)}"
        )

    try:
        return Params(**raw_data)
    except ValidationError as ve:
        msg = f"Configuration validation failed for [{target_path}]: {ve}"
        raise ConfigException(msg, sys) from ve
