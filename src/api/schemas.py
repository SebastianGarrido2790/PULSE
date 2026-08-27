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
    point_context: PointContext | None = Field(
        default=None,
        description="Contextual point score and player metadata (None on error events)",
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


# ---------------------------------------------------------------------------
# Post-Match Reporting & Tactical Intelligence Wire Schemas
# ---------------------------------------------------------------------------


class PivotalPointEntry(BaseModel):
    """Wire schema representing a top pivotal inflection moment in a match."""

    point_index: int = Field(..., ge=0, description="0-indexed point number")
    set_num: int = Field(..., ge=1, description="Set number in which point occurred")
    game_score: str = Field(..., description="Game score at point start (e.g. '5-2')")
    point_score: str = Field(..., description="Point score in game (e.g. '40-30')")
    server_id: str = Field(..., description="Player ID serving the point")
    returner_id: str = Field(..., description="Player ID returning the point")
    point_winner_id: str = Field(..., description="Player ID who won the point")
    point_winner_role: str = Field(..., description="Role of winner ('server' or 'returner')")
    delta_leverage: float = Field(..., ge=0.0, le=1.0, description="Point leverage (delta L)")
    leverage_low: float = Field(..., ge=0.0, le=1.0, description="Wilson 95% CI lower bound")
    leverage_high: float = Field(..., ge=0.0, le=1.0, description="Wilson 95% CI upper bound")
    p_hat_server: float = Field(..., ge=0.0, le=1.0, description="Estimated server win probability")
    match_win_prob_before: float = Field(
        ..., ge=0.0, le=1.0, description="P1 match win probability before point"
    )
    is_break_point: bool = Field(default=False, description="Whether point was a break point")
    is_set_point: bool = Field(default=False, description="Whether point was a set point")
    is_match_point: bool = Field(default=False, description="Whether point was a match point")
    impact_narrative: str = Field(..., description="Strategic impact summary narrative")


class PlayerPressureMetrics(BaseModel):
    """Wire schema for player performance partitioned across leverage tiers."""

    player_id: str = Field(..., description="Player identifier")
    total_points: int = Field(..., ge=0, description="Total points played by this player")
    routine_points_count: int = Field(
        ..., ge=0, description="Count of routine points (delta L < 0.10)"
    )
    routine_win_rate: float = Field(..., ge=0.0, le=1.0, description="Win rate on routine points")
    elevated_points_count: int = Field(
        ..., ge=0, description="Count of elevated points (0.10 <= delta L < 0.25)"
    )
    elevated_win_rate: float = Field(..., ge=0.0, le=1.0, description="Win rate on elevated points")
    critical_points_count: int = Field(
        ..., ge=0, description="Count of critical points (delta L >= 0.25)"
    )
    critical_win_rate: float = Field(..., ge=0.0, le=1.0, description="Win rate on critical points")
    pressure_shift_delta_p: float = Field(
        ..., description="Pressure performance shift: critical win rate minus routine win rate"
    )
    resilience_assessment: str = Field(
        ..., description="Qualitative rating (e.g. 'Elevated / Clutch', 'Steady', 'Vulnerable')"
    )


class ServeDirectionBreakdown(BaseModel):
    """Wire schema for serve direction frequencies and percentages."""

    wide_count: int = Field(default=0, ge=0)
    body_count: int = Field(default=0, ge=0)
    t_count: int = Field(default=0, ge=0)
    total_charted: int = Field(default=0, ge=0)
    wide_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    body_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    t_pct: float = Field(default=0.0, ge=0.0, le=1.0)


class GameTheoryExploitAudit(BaseModel):
    """Wire schema for game-theoretic audit comparing realized serve mix vs Nash."""

    server_id: str = Field(..., description="Server player identifier")
    returner_id: str = Field(..., description="Returner player identifier")
    court_side: Literal["deuce", "ad", "all"] = Field(..., description="Court side context")
    realized_serve_mix: ServeDirectionBreakdown = Field(
        ..., description="Realized serve direction distribution"
    )
    nash_serve_mix: dict[str, float] = Field(
        default_factory=dict, description="Game-theoretic Nash equilibrium serve mix"
    )
    returner_bias: dict[str, float] = Field(
        default_factory=dict, description="Observed returner anticipation bias distribution"
    )
    exploit_gain_delta_ev: float = Field(
        default=0.0, description="Expected point-win gain (+EV) from exploiting returner bias"
    )
    sample_size: int = Field(..., ge=0, description="Number of charted serves in this context")
    sufficiency_gated: bool = Field(
        default=False, description="True if sample size was below sufficiency gate (N < 10)"
    )


class MatchSummaryStats(BaseModel):
    """High-level statistical summary for a completed match."""

    match_id: str = Field(..., description="Unique match identifier")
    surface: str = Field(..., description="Court surface (HARD, CLAY, GRASS)")
    player_1: str = Field(..., description="Player 1 identifier")
    player_2: str = Field(..., description="Player 2 identifier")
    winner: str = Field(..., description="Winner player identifier")
    final_score: str = Field(..., description="Final match score (sets and games)")
    total_points: int = Field(..., ge=0, description="Total points in match")
    p1_points_won: int = Field(..., ge=0, description="Points won by Player 1")
    p2_points_won: int = Field(..., ge=0, description="Points won by Player 2")
    p1_win_pct: float = Field(..., ge=0.0, le=1.0, description="Player 1 point win percentage")
    p2_win_pct: float = Field(..., ge=0.0, le=1.0, description="Player 2 point win percentage")
    mean_delta_leverage: float = Field(
        ..., ge=0.0, le=1.0, description="Average point leverage across all points"
    )
    max_delta_leverage: float = Field(
        ..., ge=0.0, le=1.0, description="Maximum single-point leverage in match"
    )
    high_leverage_point_count: int = Field(
        ..., ge=0, description="Number of points where delta L >= escalation threshold (5%)"
    )
    break_point_count: int = Field(..., ge=0, description="Total break points in match")
    break_points_converted: int = Field(..., ge=0, description="Break points converted")


class MatchReportResponse(BaseModel):
    """Comprehensive API response schema for post-match tactical reporting."""

    summary: MatchSummaryStats = Field(..., description="High-level match overview")
    pivotal_points: list[PivotalPointEntry] = Field(
        ..., description="Top pivotal inflection moments"
    )
    pressure_resilience: list[PlayerPressureMetrics] = Field(
        ..., description="Pressure performance breakdown per player"
    )
    game_theory_audit: list[GameTheoryExploitAudit] = Field(
        ..., description="Serve and return game-theoretic evaluation"
    )
    executive_debrief: str = Field(..., description="LLM or templated grounded strategic debrief")
    markdown_report: str = Field(
        default="", description="Pre-rendered GitHub-flavored Markdown report"
    )
