"""PULSE — PointRecord Domain Schema & Pandera Validation Gate.

This module provides the authoritative data schema contracts for PULSE point-level data:
1. Pydantic v2 `PointRecord` model for runtime row-by-row and streaming validation.
2. Pandera `PointRecordSchema` for bulk DataFrame pipeline validation during data ingestion.
3. Shared Enum definitions for tennis domain primitives (Surface, ServeNumber, PointOutcome, etc.).
"""

from enum import Enum, StrEnum
from typing import TYPE_CHECKING

import pandera.pandas as pa
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from src.graph.state import PointContext


class Surface(StrEnum):
    """Tennis court surface type."""

    HARD = "HARD"
    CLAY = "CLAY"
    GRASS = "GRASS"


class ServeNumber(int, Enum):
    """Serve attempt number (1st or 2nd serve)."""

    FIRST = 1
    SECOND = 2


class ServeDirection(StrEnum):
    """Serve direction placement."""

    WIDE = "wide"
    BODY = "body"
    T = "T"


class PointOutcome(StrEnum):
    """Winner of the point relative to serving role."""

    SERVER = "server"
    RETURNER = "returner"


class ValidPointScore(StrEnum):
    """Valid tennis game point score strings (strict score coercion per Decision D-2a)."""

    S0 = "0"
    S15 = "15"
    S30 = "30"
    S40 = "40"
    AD = "AD"


SCORE_TO_INT: dict[ValidPointScore | str, int] = {
    ValidPointScore.S0: 0,
    ValidPointScore.S15: 1,
    ValidPointScore.S30: 2,
    ValidPointScore.S40: 3,
    ValidPointScore.AD: 4,
    "0": 0,
    "15": 1,
    "30": 2,
    "40": 3,
    "AD": 4,
}


class PointRecord(BaseModel):
    """Pydantic v2 domain model for a single point record in a tennis match.

    Attributes:
        match_id: Unique identifier for the match.
        point_id: Unique identifier for the point within the match.
        server: Player ID of the server.
        returner: Player ID of the returner.
        surface: Court surface (HARD, CLAY, GRASS).
        serve_number: Serve attempt number (1 or 2).
        serve_direction: Serve placement direction (wide, body, T), if charted.
        p1_score: Player 1 point score in current game ("0", "15", "30", "40", "AD").
        p2_score: Player 2 point score in current game ("0", "15", "30", "40", "AD").
        p1_games: Player 1 game count in current set.
        p2_games: Player 2 game count in current set.
        p1_sets: Player 1 set count in match.
        p2_sets: Player 2 set count in match.
        rally_length: Number of shots in the rally.
        point_winner: Point winner relative to role ("server" or "returner").
        break_point: True if this point is a break point.
        set_point: True if this point is a set point.
        match_point: True if this point is a match point.
        tournament_level: Optional tournament category tier code.
    """

    match_id: str = Field(..., description="Unique match identifier")
    point_id: str = Field(..., description="Unique point identifier")
    server: str = Field(..., description="Player ID serving the point")
    returner: str = Field(..., description="Player ID returning the point")
    server_is_p1: bool = Field(
        ...,
        description=(
            "True if `server` is player 1 per this match's canonical p1/p2 identity. "
            "Set explicitly at ingestion time from known source-data match metadata "
            "(e.g. comparing `server` against the match's recorded player1 field) -- "
            "never inferred from `server`'s string content (player IDs are not "
            "guaranteed to encode role information, e.g. an ID ending in '1' is not "
            "reliably player 1)."
        ),
    )
    surface: Surface = Field(..., description="Surface type")
    serve_number: int = Field(..., ge=1, le=2, description="Serve number (1 or 2)")
    serve_direction: ServeDirection | None = Field(default=None, description="Serve direction")
    p1_score: ValidPointScore = Field(..., description="Player 1 point score")
    p2_score: ValidPointScore = Field(..., description="Player 2 point score")
    p1_games: int = Field(default=0, ge=0, description="Player 1 games in set")
    p2_games: int = Field(default=0, ge=0, description="Player 2 games in set")
    p1_sets: int = Field(default=0, ge=0, description="Player 1 sets won")
    p2_sets: int = Field(default=0, ge=0, description="Player 2 sets won")
    rally_length: int = Field(default=0, ge=0, description="Rally length count")
    point_winner: PointOutcome = Field(..., description="Point winner role")
    break_point: bool = Field(default=False, description="Is break point flag")
    set_point: bool = Field(default=False, description="Is set point flag")
    match_point: bool = Field(default=False, description="Is match point flag")
    tournament_level: str | None = Field(default=None, description="Tournament level category")

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_surface(cls, v: str | Surface) -> Surface:
        """Coerce surface input strings to uppercase Surface enum."""
        if isinstance(v, str):
            return Surface(v.upper())
        return v

    @field_validator("serve_direction", mode="before")
    @classmethod
    def normalize_serve_direction(cls, v: str | ServeDirection | None) -> ServeDirection | None:
        """Coerce serve direction strings safely."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            val_lower = v.strip()
            if val_lower.lower() == "wide":
                return ServeDirection.WIDE
            if val_lower.lower() == "body":
                return ServeDirection.BODY
            if val_lower.upper() == "T":
                return ServeDirection.T
            return ServeDirection(v)
        return v

    def get_server_score_int(self) -> int:
        """Return the integer representation of the server's point score.

        Uses `server_is_p1`, set explicitly at ingestion time, rather than
        inferring role from `server`'s string content.
        """
        score = self.p1_score if self.server_is_p1 else self.p2_score
        return SCORE_TO_INT[score]

    def get_returner_score_int(self) -> int:
        """Return the integer representation of the returner's point score.

        Uses `server_is_p1`, set explicitly at ingestion time, rather than
        inferring role from `server`'s string content.
        """
        score = self.p2_score if self.server_is_p1 else self.p1_score
        return SCORE_TO_INT[score]

    def get_server_games_int(self) -> int:
        """Return the game count of the server in the current set."""
        return self.p1_games if self.server_is_p1 else self.p2_games

    def get_returner_games_int(self) -> int:
        """Return the game count of the returner in the current set."""
        return self.p2_games if self.server_is_p1 else self.p1_games

    def get_server_sets_int(self) -> int:
        """Return the set count of the server in the match."""
        return self.p1_sets if self.server_is_p1 else self.p2_sets

    def get_returner_sets_int(self) -> int:
        """Return the set count of the returner in the match."""
        return self.p2_sets if self.server_is_p1 else self.p1_sets

    def to_point_context(self, point_index: int) -> "PointContext":
        """Convert PointRecord domain model into a strongly typed PointContext.

        Args:
            point_index: 0-indexed chronological point sequence number (D-3b).

        Returns:
            PointContext: Graph input context formatted for LangGraph execution.

        Note:
            Per Phase 6 Decision D-3a, match replay simulation currently operates
            under an explicit Best-of-3 (bo3) demo scope. Best-of-5 matches are out
            of scope until tournament format inference is formalized in data ingestion.
        """
        from src.graph.state import PointContext

        return PointContext(
            match_id=self.match_id,
            point_index=point_index,
            server_id=self.server,
            returner_id=self.returner,
            surface=self.surface.value if isinstance(self.surface, Surface) else str(self.surface),
            serve_number=self.serve_number,
            point_score_server=self.get_server_score_int(),
            point_score_returner=self.get_returner_score_int(),
            game_score_server=self.get_server_games_int(),
            game_score_returner=self.get_returner_games_int(),
            set_score_server=self.get_server_sets_int(),
            set_score_returner=self.get_returner_sets_int(),
            match_format="bo3",
        )


class PointRecordSchema(pa.DataFrameModel):
    """Pandera DataFrame validation schema for bulk data ingestion pipeline gates."""

    match_id: pa.String = pa.Field(description="Unique match identifier")
    point_id: pa.String = pa.Field(description="Unique point identifier")
    server: pa.String = pa.Field(description="Player ID serving the point")
    returner: pa.String = pa.Field(description="Player ID returning the point")
    server_is_p1: pa.Bool = pa.Field(
        description="True if server is player 1, set explicitly at ingestion time"
    )
    surface: pa.String = pa.Field(isin=["HARD", "CLAY", "GRASS"], description="Surface type")
    serve_number: pa.Int = pa.Field(isin=[1, 2], description="Serve number")
    serve_direction: pa.String = pa.Field(
        nullable=True, isin=["wide", "body", "T"], description="Serve direction"
    )
    p1_score: pa.String = pa.Field(
        isin=["0", "15", "30", "40", "AD"], description="Player 1 point score"
    )
    p2_score: pa.String = pa.Field(
        isin=["0", "15", "30", "40", "AD"], description="Player 2 point score"
    )
    p1_games: pa.Int = pa.Field(ge=0, description="Player 1 games count")
    p2_games: pa.Int = pa.Field(ge=0, description="Player 2 games count")
    p1_sets: pa.Int = pa.Field(ge=0, description="Player 1 sets count")
    p2_sets: pa.Int = pa.Field(ge=0, description="Player 2 sets count")
    rally_length: pa.Int = pa.Field(ge=0, description="Rally length count")
    point_winner: pa.String = pa.Field(isin=["server", "returner"], description="Point winner role")
    break_point: pa.Bool = pa.Field(description="Is break point flag")
    set_point: pa.Bool = pa.Field(description="Is set point flag")
    match_point: pa.Bool = pa.Field(description="Is match point flag")

    class Config:  # type: ignore[reportIncompatibleVariableOverride]
        """Pandera schema validation configuration options."""

        coerce = True
        strict = False  # Allow additional metadata columns without failing ingestion
