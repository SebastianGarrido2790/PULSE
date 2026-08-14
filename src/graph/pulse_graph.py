"""PULSE — Event-Driven LangGraph Orchestration Builder.

Loads Phase 3 ML artifacts and configuration parameters once at graph construction time
and compiles the event-driven conditional graph for live match state monitoring.

Authority: Phase 4 Decisions D-1 through D-11, ADR-001.
"""

from collections.abc import Callable
from pathlib import Path

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from opentelemetry import trace

from src.config.loader import Params, load_params
from src.core.game_theory import PayoffMatrix, load_payoff_matrices
from src.graph.pressure_diagnostic import make_pressure_diagnostic_node
from src.graph.state import LeverageResult, PulseGraphState
from src.graph.state_monitor import make_state_monitor_node
from src.graph.strategy_exploit import make_strategy_exploit_node
from src.graph.tactical_output import make_tactical_output_node
from src.models.point_win_classifier import StratumTable, load_stratum_table
from src.models.pressure_deviation import PressureModelArtifact, load_pressure_artifact
from src.utils.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer("pulse.graph")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_graph_artifacts(
    artifacts_dir: Path | None = None,
) -> tuple[StratumTable, PressureModelArtifact, dict[str, PayoffMatrix]]:
    """Load Phase 3 and Phase 5 ML artifacts exactly once from disk.

    Args:
        artifacts_dir: Root directory containing models artifacts.
            Defaults to PROJECT_ROOT / "artifacts" / "models".

    Returns:
        tuple[StratumTable, PressureModelArtifact, dict[str, PayoffMatrix]]: Loaded artifacts.

    Raises:
        ModelInferenceError: If artifacts are missing or corrupted.
    """
    base_dir = (
        artifacts_dir if artifacts_dir is not None else (PROJECT_ROOT / "artifacts" / "models")
    )
    classifier_dir = base_dir / "point_win_classifier"
    pressure_dir = base_dir / "pressure_deviation"
    game_theory_dir = base_dir / "game_theory"

    logger.info(f"Loading Phase 3 StratumTable from [{classifier_dir}]")
    stratum_table = load_stratum_table(classifier_dir)

    logger.info(f"Loading Phase 3 PressureModelArtifact from [{pressure_dir}]")
    pressure_artifact = load_pressure_artifact(pressure_dir)

    logger.info(f"Loading Phase 5 Payoff Matrices from [{game_theory_dir}]")
    payoff_matrices = load_payoff_matrices(game_theory_dir)

    t0_cnt = len(stratum_table.tier0_exact)
    p_cnt = len(pressure_artifact.results)
    gt_cnt = len(payoff_matrices)
    logger.info(
        f"Artifacts loaded: StratumTable ({t0_cnt} entries), "
        f"PressureArtifact ({p_cnt} results), PayoffMatrices ({gt_cnt} strata)"
    )

    return stratum_table, pressure_artifact, payoff_matrices


def should_escalate(leverage_result: LeverageResult | None, threshold: float) -> bool:
    """Check if lower confidence bound delta_leverage_low >= leverage_escalation threshold.

    Authority: Phase 4 Decision D-4 (Option B - Lower Bound Gating), D-4a.

    Args:
        leverage_result: Computed LeverageResult from StateMonitorNode (or None).
        threshold: Leverage escalation threshold from params.yaml.

    Returns:
        bool: True if delta_leverage_low >= threshold; False otherwise.
    """
    if leverage_result is None:
        return False
    return leverage_result.delta_leverage_low >= threshold


def make_route_after_state_monitor(
    params: Params | None = None,
) -> Callable[[PulseGraphState], str]:
    """Factory creating a route_after_state_monitor closure bound to Params (D-9, D-10).

    Args:
        params: Optional Params configuration object.

    Returns:
        Callable[[PulseGraphState], str]: Routing function.
    """
    cfg = params if params is not None else load_params()
    threshold = cfg.thresholds.leverage_escalation

    def route_after_state_monitor(state: PulseGraphState) -> str:
        """Route after StateMonitorNode: check leverage escalation for PressureDiagnosticNode.

        Authority: Decisions D-3, D-4, D-5. Logs fire/suppress DecisionLogEntry and emits OTel span.

        Args:
            state: Current PulseGraphState input object.

        Returns:
            str: Destination node name ("pressure_diagnostic" or "tactical_output").
        """
        lev_res = state.leverage_result
        lev_low = lev_res.delta_leverage_low if lev_res is not None else 0.0
        escalate = should_escalate(lev_res, threshold)

        if escalate:
            fired = True
            reason = f"Leverage lower bound {lev_low:.4f} >= threshold {threshold:.4f}"
            destination = "pressure_diagnostic"
        else:
            fired = False
            reason = f"Leverage lower bound {lev_low:.4f} < threshold {threshold:.4f} (suppressed)"
            destination = "tactical_output"

        with tracer.start_as_current_span("route_after_state_monitor") as span:
            span.set_attribute("pulse.target_node", "pressure_diagnostic")
            span.set_attribute("pulse.fired", fired)
            span.set_attribute("pulse.reason", reason)

        logger.debug(f"Routing after StateMonitorNode -> [{destination}] ({reason})")
        return destination

    return route_after_state_monitor


def make_route_after_pressure_diagnostic(
    params: Params | None = None,
) -> Callable[[PulseGraphState], str]:
    """Factory creating a route_after_pressure_diagnostic closure bound to Params (D-9, D-10).

    Args:
        params: Optional Params configuration object.

    Returns:
        Callable[[PulseGraphState], str]: Routing function.
    """
    cfg = params if params is not None else load_params()
    threshold = cfg.thresholds.leverage_escalation

    def route_after_pressure_diagnostic(state: PulseGraphState) -> str:
        """Route after PressureDiagnosticNode: check leverage escalation for StrategyExploitNode.

        Authority: Decisions D-3, D-4a, D-5. Logs fire/suppress DecisionLogEntry & OTel span.

        Args:
            state: Current PulseGraphState input object.

        Returns:
            str: Destination node name ("strategy_exploit" or "tactical_output").
        """
        lev_res = state.leverage_result
        lev_low = lev_res.delta_leverage_low if lev_res is not None else 0.0
        escalate = should_escalate(lev_res, threshold)

        if escalate:
            fired = True
            reason = f"Leverage lower bound {lev_low:.4f} >= threshold {threshold:.4f}"
            destination = "strategy_exploit"
        else:
            fired = False
            reason = f"Leverage lower bound {lev_low:.4f} < threshold {threshold:.4f} (suppressed)"
            destination = "tactical_output"

        with tracer.start_as_current_span("route_after_pressure_diagnostic") as span:
            span.set_attribute("pulse.target_node", "strategy_exploit")
            span.set_attribute("pulse.fired", fired)
            span.set_attribute("pulse.reason", reason)

        logger.debug(f"Routing after PressureDiagnosticNode -> [{destination}] ({reason})")
        return destination

    return route_after_pressure_diagnostic


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
    stratum_table, pressure_artifact, payoff_matrices = load_graph_artifacts(
        artifacts_dir=artifacts_dir
    )

    builder = StateGraph(PulseGraphState)

    # 1. Register node factory functions
    builder.add_node("state_monitor", make_state_monitor_node(stratum_table, cfg))
    builder.add_node("pressure_diagnostic", make_pressure_diagnostic_node(pressure_artifact, cfg))
    builder.add_node("strategy_exploit", make_strategy_exploit_node(payoff_matrices, cfg))
    builder.add_node("tactical_output", make_tactical_output_node(cfg))

    # 2. Wire entry point and conditional edges
    builder.set_entry_point("state_monitor")

    builder.add_conditional_edges(
        "state_monitor",
        make_route_after_state_monitor(cfg),
        {
            "pressure_diagnostic": "pressure_diagnostic",
            "tactical_output": "tactical_output",
        },
    )

    builder.add_conditional_edges(
        "pressure_diagnostic",
        make_route_after_pressure_diagnostic(cfg),
        {
            "strategy_exploit": "strategy_exploit",
            "tactical_output": "tactical_output",
        },
    )

    builder.add_edge("strategy_exploit", "tactical_output")
    builder.add_edge("tactical_output", END)

    compiled_graph = builder.compile()
    logger.info("PULSE LangGraph orchestration graph built and compiled successfully.")
    return compiled_graph
