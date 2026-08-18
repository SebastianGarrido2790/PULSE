"""PULSE — API Wire Schemas & Request/Response Contracts.

Defines Pydantic v2 schemas for HTTP endpoints, SSE streaming payloads,
WebSocket framing, and match replay requests.

Authority: Phase 6 Decision D-10, prd.md FR-9, FR-11.
"""

from typing import Literal

from pydantic import BaseModel, Field

from src.core.game_theory import ExploitResult
from src.graph.state import (
    DecisionLogEntry,
    LeverageResult,
    PointContext,
    TacticalOutputResult,
)
from src.models.pressure_deviation import PressureDeviationResult


class StreamPointEvent(BaseModel):
    """Wire contract for point-level streaming events emitted over SSE and WebSocket transports."""

    event_type: Literal["point", "heartbeat", "error", "complete"] = Field(
        default="point",
        description="Event classification type",
    )
    match_id: str = Field(
        ...,
        description="Unique match identifier",
    )
    point_index: int = Field(
        ...,
        ge=0,
        description="0-indexed chronological point sequence number within the match",
    )
    point_context: PointContext = Field(
        ...,
        description="Contextual point score and player metadata",
    )
    tactical_output: TacticalOutputResult | None = Field(
        default=None,
        description="Resolved tactical narrative and assembled signal payload",
    )
    leverage_result: LeverageResult | None = Field(
        default=None,
        description="Point leverage calculation and Wilson uncertainty bounds",
    )
    pressure_result: PressureDeviationResult | None = Field(
        default=None,
        description="Empirical-Bayes pressure diagnostic result if node was triggered",
    )
    exploit_result: ExploitResult | None = Field(
        default=None,
        description="Game-theoretic minimax exploit result if node was triggered",
    )
    decision_log: list[DecisionLogEntry] = Field(
        default_factory=list,
        description="Node execution and conditional routing audit trail for this point",
    )
    error_message: str | None = Field(
        default=None,
        description="Detailed error message if event_type is 'error'",
    )


class MatchReplayRequest(BaseModel):
    """Request query/body parameters for historical match replay streaming."""

    speed_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        description="Playback speed multiplier (0.0 for instant zero-delay replay)",
    )
    match_format: Literal["bo3", "bo5"] = Field(
        default="bo3",
        description="Match format (default 'bo3' in Phase 6 demo scope; bo5 explicitly noted)",
    )


class MatchMetadataResponse(BaseModel):
    """Response schema summarizing metadata and available points for a charted match."""

    match_id: str = Field(
        ...,
        description="Unique match identifier",
    )
    total_points: int = Field(
        ...,
        ge=0,
        description="Total number of charted points in match sequence",
    )
    server_p1: str = Field(
        ...,
        description="Player 1 identifier",
    )
    returner_p2: str = Field(
        ...,
        description="Player 2 identifier",
    )
    surface: str = Field(
        ...,
        description="Match court surface (HARD, CLAY, GRASS)",
    )
    match_format: Literal["bo3", "bo5"] = Field(
        default="bo3",
        description="Match format",
    )


class HealthCheckResponse(BaseModel):
    """Response schema for service health status and artifact readiness."""

    status: str = Field(
        default="healthy",
        description="Overall service health indicator",
    )
    graph_ready: bool = Field(
        default=True,
        description="True if CompiledStateGraph is loaded in memory and ready for inference",
    )
    version: str = Field(
        default="0.1.0",
        description="PULSE service version",
    )
    artifacts_loaded: list[str] = Field(
        default_factory=list,
        description="List of verified, loaded model and lookup table artifact keys",
    )
