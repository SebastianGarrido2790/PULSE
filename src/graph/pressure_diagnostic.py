"""PULSE — Pressure Diagnostic Node (src/graph/pressure_diagnostic.py).

Triggered node executed when point leverage exceeds escalation threshold.
Queries Empirical-Bayes Pressure Deviation model for server's historical performance shift.

Authority: FR-4, Phase 4 Decisions D-2b, D-6, D-7a, D-9, D-10, ADR-001.
"""

from collections.abc import Callable
from typing import Any

from src.config.loader import Params, load_params
from src.graph.state import PulseGraphState
from src.models.pressure_deviation import (
    PressureModelArtifact,
    assign_leverage_bucket,
    get_pressure_deviation,
)
from src.utils.exceptions import ModelInferenceError
from src.utils.logger import get_logger

logger = get_logger(__name__)


def make_pressure_diagnostic_node(
    pressure_artifact: PressureModelArtifact, params: Params | None = None
) -> Callable[[PulseGraphState], Any]:
    """Factory creating an async PressureDiagnosticNode bound to PressureModelArtifact.

    Per D-9 & D-10, closes over PressureModelArtifact and Params loaded at graph build time.
    Per D-7a, returns an async node function to maintain uniform calling convention.

    Args:
        pressure_artifact: Loaded Phase 3 PressureModelArtifact container.
        params: Optional Params configuration object.

    Returns:
        Callable[[PulseGraphState], Awaitable[dict[str, Any]]]: Async node function.
    """
    cfg = params if params is not None else load_params()

    async def pressure_diagnostic_node(state: PulseGraphState) -> dict[str, Any]:
        """Triggered node looking up server pressure deviation in the current leverage bucket.

        Args:
            state: Current PulseGraphState input object.

        Returns:
            dict[str, Any]: State update dictionary with key "pressure_result".

        Raises:
            ModelInferenceError: If leverage_result is missing from state.
        """
        if state.leverage_result is None:
            raise ModelInferenceError(
                "PressureDiagnosticNode executed without leverage_result in graph state"
            )

        ctx = state.point_context
        delta_leverage = state.leverage_result.delta_leverage

        # 1. Map point leverage delta_L to leverage bucket (0=Routine, 1=Elevated, 2=Critical)
        bucket_idx = assign_leverage_bucket(
            leverage=delta_leverage,
            boundaries=cfg.models.pressure_leverage_buckets,
        )

        # 2. Query serving-time pressure deviation accessor
        pressure_res = get_pressure_deviation(
            artifact=pressure_artifact,
            server_id=ctx.server_id,
            leverage_bucket=bucket_idx,
        )

        if pressure_res is not None:
            dev_low = pressure_res.deviation_low_90
            dev_high = pressure_res.deviation_high_90
            logger.debug(
                f"PressureDiagnosticNode hit for [{ctx.server_id}] in bucket [{bucket_idx}]: "
                f"dev={pressure_res.pressure_deviation:+.4f} "
                f"bounds=[{dev_low:+.4f}, {dev_high:+.4f}] "
                f"sufficient={pressure_res.is_sufficient_sample}"
            )
        else:
            logger.debug(
                f"PressureDiagnosticNode miss (sparse player) for [{ctx.server_id}] "
                f"in bucket [{bucket_idx}]"
            )

        return {"pressure_result": pressure_res}

    return pressure_diagnostic_node
