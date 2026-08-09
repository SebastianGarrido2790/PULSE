"""PULSE — LangGraph State Schema & Data Contracts.

Defines the Pydantic v2 graph state model and nested sub-models passed across
the event-driven orchestration nodes in pulse_graph.py.

Authority: Phase 4 Decisions D-2, D-2a, D-2b.
"""

from typing import Any

from pydantic import BaseModel, Field

from src.models.pressure_deviation import PressureDeviationResult


class PointContext(BaseModel):
    """Contextual metadata for the point being evaluated by the orchestration graph."""

    match_id: str = Field(..., description="Unique match identifier")
    point_index: int = Field(..., ge=0, description="0-indexed point index in match sequence")
    server_id: str = Field(..., description="Player ID serving the point")
    returner_id: str = Field(..., description="Player ID returning the point")
    surface: str = Field(..., description="Court surface (HARD, CLAY, GRASS)")
    serve_number: int = Field(..., ge=1, le=2, description="Serve attempt number (1 or 2)")


class LeverageResult(BaseModel):
    """Leverage calculation result and Wilson uncertainty bounds computed by StateMonitorNode."""

    delta_leverage: float = Field(..., ge=0.0, le=1.0, description="Point leverage delta_L")
    delta_leverage_low: float = Field(
        ..., ge=0.0, le=1.0, description="Lower Wilson leverage bound"
    )
    delta_leverage_high: float = Field(
        ..., ge=0.0, le=1.0, description="Upper Wilson leverage bound"
    )
    p_hat: float = Field(..., ge=0.0, le=1.0, description="Point-win probability estimate")
    sample_size: int = Field(..., ge=0, description="Observation count backing p_hat estimate")
    fallback_tier: int = Field(
        ...,
        ge=0,
        le=3,
        description="Stratum fallback tier (0=Exact, 1=Player, 2=Surface, 3=Default)",
    )


class ExploitResult(BaseModel):
    """Strategy exploit result payload computed by StrategyExploitNode (stub in Phase 4)."""

    status: str = Field(..., description="Execution status e.g. 'module_not_yet_implemented'")
    opponent_id: str = Field(..., description="Opponent player ID being analyzed")
    sample_size: int = Field(..., ge=0, description="Opponent observation count")
    is_sufficient_sample: bool = Field(
        ..., description="True if sample_size >= exploit_min_sample_size"
    )
    recommendation: str | None = Field(
        default=None, description="Exploit recommendation string if available"
    )


class TacticalOutputResult(BaseModel):
    """Assembled tactical narrative and pre-computed signal payload from TacticalOutputNode."""

    narrative: str = Field(..., description="Coach-readable narrative synthesis")
    escalated: bool = Field(..., description="True if leverage escalation threshold was met")
    raw_payload: dict[str, Any] = Field(..., description="Assembled pre-computed signal dictionary")
    is_llm_fallback: bool = Field(
        default=False, description="True if LLM call failed and raw signal passthrough was used"
    )


class DecisionLogEntry(BaseModel):
    """Audit log entry capturing node execution status and decision rationale."""

    node: str = Field(..., description="Target graph node name")
    fired: bool = Field(..., description="True if node was executed; False if suppressed")
    reason: str = Field(..., description="Rationale string for firing or suppressing the node")


class PulseGraphState(BaseModel):
    """Pydantic v2 graph state contract for LangGraph event-driven orchestration.

    Every node reads from and updates fields on this state object.
    Optional fields default to None to represent non-fired / suppressed nodes (D-2b).
    """

    point_context: PointContext
    leverage_result: LeverageResult
    pressure_result: PressureDeviationResult | None = Field(
        default=None, description="Populated only if PressureDiagnosticNode fires"
    )
    exploit_result: ExploitResult | None = Field(
        default=None, description="Populated only if StrategyExploitNode fires"
    )
    tactical_output: TacticalOutputResult | None = Field(
        default=None, description="Populated by TacticalOutputNode"
    )
    decision_log: list[DecisionLogEntry] = Field(
        default_factory=list, description="Appended by graph routing functions for audit tracking"
    )
