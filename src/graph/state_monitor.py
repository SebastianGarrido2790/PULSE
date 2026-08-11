"""PULSE — State Monitor Node (src/graph/state_monitor.py).

Always-on orchestration graph node executed for every point in a tennis match stream.
Queries Tier 1 stratum classifier for point-win probability, evaluates Markov solver for
point leverage delta_L, and calculates analytical Wilson leverage confidence bounds.

Authority: FR-3, Phase 4 Decisions D-2, D-7a, D-9, D-10, ADR-001.
"""

from collections.abc import Callable
from typing import Any

from src.config.loader import Params, load_params
from src.core.leverage_uncertainty import propagate_leverage_uncertainty
from src.graph.state import DecisionLogEntry, LeverageResult, PulseGraphState
from src.models.point_win_classifier import StratumTable, resolve_point_win_probability
from src.utils.logger import get_logger

logger = get_logger(__name__)


def make_state_monitor_node(
    stratum_table: StratumTable, params: Params | None = None
) -> Callable[..., Any]:
    """Factory creating an async StateMonitorNode callable bound to loaded StratumTable.

    Per D-9 & D-10, closes over StratumTable and Params loaded once at graph build time.
    Per D-7a, returns an async node function to maintain uniform calling convention.

    Args:
        stratum_table: Phase 3 StratumTable lookup artifact.
        params: Optional Params configuration object.

    Returns:
        Callable[[PulseGraphState], Awaitable[dict[str, Any]]]: Async node function.
    """
    cfg = params if params is not None else load_params()

    async def state_monitor_node(state: PulseGraphState) -> dict[str, Any]:
        """Always-on node computing point leverage and Wilson uncertainty bounds.

        Args:
            state: Current PulseGraphState input object.

        Returns:
            dict[str, Any]: State update dictionary with key "leverage_result".
        """
        ctx = state.point_context
        logger.debug(
            f"StateMonitorNode executing for match [{ctx.match_id}] point [{ctx.point_index}] "
            f"server [{ctx.server_id}] surface [{ctx.surface}] serve_num [{ctx.serve_number}]"
        )

        # 1. Resolve point-win probability p_hat & observation count N
        stratum_res = resolve_point_win_probability(
            stratum_table=stratum_table,
            server_id=ctx.server_id,
            surface=ctx.surface,
            serve_number=ctx.serve_number,
            params=cfg,
        )

        # 2. Build MatchState domain object from context score fields
        match_state = ctx.to_match_state()

        # 3. Propagate Wilson uncertainty bounds through Markov solver to obtain leverage band
        leverage_band_res = propagate_leverage_uncertainty(
            state=match_state,
            wins=stratum_res.wins,
            sample_size=stratum_res.sample_size,
            confidence_level=cfg.uncertainty.confidence_level,
            min_observations=cfg.uncertainty.min_stratum_observations,
            default_p=cfg.solver.default_p_serve,
            fallback_margin=cfg.uncertainty.default_fallback_margin,
        )

        # 4. Construct LeverageResult matching Phase 4 graph state schema
        leverage_result = LeverageResult(
            delta_leverage=leverage_band_res.leverage_point,
            delta_leverage_low=leverage_band_res.leverage_low,
            delta_leverage_high=leverage_band_res.leverage_high,
            p_hat=stratum_res.p_hat,
            sample_size=stratum_res.sample_size,
            fallback_tier=int(stratum_res.fallback_tier),
        )

        # 5. Determine escalation decision and record audit log entries (D-3, D-4, D-5)
        thresh = cfg.thresholds.leverage_escalation
        lev_low = leverage_result.delta_leverage_low
        escalate = lev_low >= thresh

        if escalate:
            reason = f"Leverage lower bound {lev_low:.4f} >= threshold {thresh:.4f}"
            log_entries = [
                DecisionLogEntry(node="pressure_diagnostic", fired=True, reason=reason)
            ]
        else:
            reason = f"Leverage lower bound {lev_low:.4f} < threshold {thresh:.4f} (suppressed)"
            log_entries = [
                DecisionLogEntry(node="pressure_diagnostic", fired=False, reason=reason),
                DecisionLogEntry(node="strategy_exploit", fired=False, reason=reason),
            ]

        return {"leverage_result": leverage_result, "decision_log": log_entries}

    return state_monitor_node
