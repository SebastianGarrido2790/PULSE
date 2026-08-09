"""PULSE — Event-Driven LangGraph Orchestration Builder.

Loads Phase 3 ML artifacts and configuration parameters once at graph construction time
and compiles the event-driven conditional graph for live match state monitoring.

Authority: Phase 4 Decisions D-1 through D-11, ADR-001.
"""

from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.config.loader import Params, load_params
from src.graph.state import PulseGraphState
from src.models.point_win_classifier import StratumTable, load_stratum_table
from src.models.pressure_deviation import PressureModelArtifact, load_pressure_artifact
from src.utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_graph_artifacts(
    artifacts_dir: Path | None = None,
) -> tuple[StratumTable, PressureModelArtifact]:
    """Load Phase 3 ML artifacts (StratumTable and PressureModelArtifact) exactly once from disk.

    Args:
        artifacts_dir: Root directory containing models artifacts.
            Defaults to PROJECT_ROOT / "artifacts" / "models".

    Returns:
        tuple[StratumTable, PressureModelArtifact]: Loaded artifacts.

    Raises:
        ModelInferenceError: If artifacts are missing or corrupted.
    """
    base_dir = (
        artifacts_dir if artifacts_dir is not None else (PROJECT_ROOT / "artifacts" / "models")
    )
    classifier_dir = base_dir / "point_win_classifier"
    pressure_dir = base_dir / "pressure_deviation"

    logger.info(f"Loading Phase 3 StratumTable from [{classifier_dir}]")
    stratum_table = load_stratum_table(classifier_dir)

    logger.info(f"Loading Phase 3 PressureModelArtifact from [{pressure_dir}]")
    pressure_artifact = load_pressure_artifact(pressure_dir)

    t0_cnt = len(stratum_table.tier0_exact)
    p_cnt = len(pressure_artifact.results)
    logger.info(
        f"Artifacts loaded: StratumTable ({t0_cnt} entries), "
        f"PressureArtifact ({p_cnt} results)"
    )

    return stratum_table, pressure_artifact


def build_pulse_graph(
    artifacts_dir: Path | None = None,
    params: Params | None = None,
) -> CompiledStateGraph:
    """Construct and compile the PULSE LangGraph event-driven orchestration graph.

    Loads artifacts and configuration once at graph construction time (D-9) and injects
    them into node factory functions via closure binding (D-10).

    Args:
        artifacts_dir: Optional custom path to model artifacts directory.
        params: Optional pre-loaded Params object. Loaded via load_params() if None.

    Returns:
        CompiledStateGraph: Compiled LangGraph application instance.
    """
    cfg = params if params is not None else load_params()
    stratum_table, pressure_artifact = load_graph_artifacts(artifacts_dir=artifacts_dir)

    # Placeholder no-op node factory function for Gate 2 verification
    def make_placeholder_node(table: StratumTable, artifact: PressureModelArtifact, p: Params):
        async def placeholder_node(state: PulseGraphState) -> dict[str, Any]:
            thresh = p.thresholds.leverage_escalation
            logger.debug(
                f"Placeholder node executed. Stratum entries: {len(table.tier0_exact)}, "
                f"Pressure entries: {len(artifact.results)}, Escalation threshold: {thresh}"
            )
            return {}

        return placeholder_node

    builder = StateGraph(PulseGraphState)

    # Register placeholder node for initial skeleton verification
    placeholder_fn = make_placeholder_node(stratum_table, pressure_artifact, cfg)
    builder.add_node("state_monitor", placeholder_fn)
    builder.set_entry_point("state_monitor")

    compiled_graph = builder.compile()
    logger.info("PULSE LangGraph orchestration graph built and compiled successfully.")
    return compiled_graph
