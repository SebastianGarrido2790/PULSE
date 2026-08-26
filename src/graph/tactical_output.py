"""PULSE — Tactical Output Node (src/graph/tactical_output.py).

Terminal node assembling pre-computed signals and conditionally synthesizing coach-readable
narratives via configured LLM provider (Groq Cloud free-tier, Anthropic) only on escalated points.
Maintains zero LLM calls on routine points.

Authority: FR-7, Phase 4 Decisions D-2b, D-7, D-7a, D-9, D-10, ADR-001, Free-Tier LLM ADR.
"""

from collections.abc import Callable
from typing import Any

from src.config.loader import Params, load_params
from src.graph.llm_client import call_narrative_llm
from src.graph.state import PulseGraphState, TacticalOutputResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


def assemble_signal_payload(state: PulseGraphState) -> dict[str, Any]:
    """Assemble structured signal payload from non-None results on state (FR-7, D-2b).

    Args:
        state: Current PulseGraphState input object.

    Returns:
        dict[str, Any]: Variable-shape signal dictionary.
    """
    payload: dict[str, Any] = {
        "point_context": state.point_context.model_dump(),
    }
    if state.leverage_result is not None:
        payload["leverage_result"] = state.leverage_result.model_dump()
    if state.pressure_result is not None:
        payload["pressure_result"] = state.pressure_result.model_dump()
    if state.exploit_result is not None:
        payload["exploit_result"] = state.exploit_result.model_dump()
    return payload


def make_tactical_output_node(
    params: Params | None = None,
) -> Callable[..., Any]:
    """Factory creating an async TacticalOutputNode bound to Params configuration.

    Per D-7 & D-7a, invokes call_narrative_llm ONLY when pressure_result or exploit_result
    is present. For routine non-escalated points, executes zero LLM calls.

    Args:
        params: Optional Params configuration object.

    Returns:
        Callable[[PulseGraphState], Awaitable[dict[str, Any]]]: Async node function.
    """
    cfg = params if params is not None else load_params()

    async def tactical_output_node(state: PulseGraphState) -> dict[str, Any]:
        """Terminal node assembling signals and synthesizing optional LLM narrative.

        Args:
            state: Current PulseGraphState input object.

        Returns:
            dict[str, Any]: State update dictionary with key "tactical_output".
        """
        # 1. Assemble structured pre-computed signal payload (FR-7)
        raw_payload = assemble_signal_payload(state)

        # 2. Check escalation status (D-7 guard: LLM call ONLY on escalation)
        is_escalated = (state.pressure_result is not None) or (state.exploit_result is not None)

        lev_str = (
            f" (ΔL={state.leverage_result.delta_leverage:.3f})"
            if state.leverage_result is not None
            else ""
        )

        if is_escalated:
            logger.debug("Point is escalated. Calling LLM for narrative synthesis...")
            llm_text = await call_narrative_llm(raw_payload, params=cfg)

            if llm_text is not None:
                narrative = llm_text
                is_llm_fallback = False
            else:
                narrative = f"Escalated point{lev_str}. Signal payload assembled."
                is_llm_fallback = True
        else:
            logger.debug("Routine point (non-escalated). Zero LLM calls made.")
            narrative = f"Routine point{lev_str}. No escalation required."
            is_llm_fallback = False

        tactical_output = TacticalOutputResult(
            narrative=narrative,
            escalated=is_escalated,
            raw_payload=raw_payload,
            is_llm_fallback=is_llm_fallback,
        )

        logger.debug(
            f"TacticalOutputNode complete: escalated={is_escalated} "
            f"fallback={is_llm_fallback} narrative_len={len(narrative)}"
        )

        return {"tactical_output": tactical_output}

    return tactical_output_node
