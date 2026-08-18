"""Unit tests for PointRecord.to_point_context() conversion (Phase 6 Decision D-3).

Verifies score, game, and set perspective mapping for both server_is_p1=True and False,
and tests conversion on real rows from artifacts/validated_data/points.parquet.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.graph.state import PointContext
from src.schemas.point_record import (
    PointOutcome,
    PointRecord,
    ServeDirection,
    Surface,
    ValidPointScore,
)


def test_point_record_to_point_context_server_is_p1_true() -> None:
    """Verify PointContext mapping when server is Player 1."""
    record = PointRecord(
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_id="pt_001",
        server="Carlos Alcaraz",
        returner="Novak Djokovic",
        server_is_p1=True,
        surface=Surface.GRASS,
        serve_number=1,
        serve_direction=ServeDirection.WIDE,
        p1_score=ValidPointScore.S40,
        p2_score=ValidPointScore.S30,
        p1_games=4,
        p2_games=3,
        p1_sets=1,
        p2_sets=0,
        rally_length=6,
        point_winner=PointOutcome.SERVER,
    )

    ctx = record.to_point_context(point_index=0)

    assert isinstance(ctx, PointContext)
    assert ctx.match_id == "2023-wimbledon-f-alcaraz-djokovic"
    assert ctx.point_index == 0
    assert ctx.server_id == "Carlos Alcaraz"
    assert ctx.returner_id == "Novak Djokovic"
    assert ctx.surface == "GRASS"
    assert ctx.serve_number == 1
    # Server is P1: scores map directly (P1 -> server, P2 -> returner)
    assert ctx.point_score_server == 3  # 40 -> 3
    assert ctx.point_score_returner == 2  # 30 -> 2
    assert ctx.game_score_server == 4
    assert ctx.game_score_returner == 3
    assert ctx.set_score_server == 1
    assert ctx.set_score_returner == 0
    # Phase 6 Decision D-3a scope
    assert ctx.match_format == "bo3"


def test_point_record_to_point_context_server_is_p1_false() -> None:
    """Verify PointContext perspective flip when server is Player 2."""
    record = PointRecord(
        match_id="2023-wimbledon-f-alcaraz-djokovic",
        point_id="pt_002",
        server="Novak Djokovic",
        returner="Carlos Alcaraz",
        server_is_p1=False,
        surface=Surface.GRASS,
        serve_number=2,
        serve_direction=ServeDirection.T,
        p1_score=ValidPointScore.S15,
        p2_score=ValidPointScore.AD,
        p1_games=3,
        p2_games=4,
        p1_sets=0,
        p2_sets=1,
        rally_length=12,
        point_winner=PointOutcome.SERVER,
    )

    ctx = record.to_point_context(point_index=15)

    assert isinstance(ctx, PointContext)
    assert ctx.match_id == "2023-wimbledon-f-alcaraz-djokovic"
    assert ctx.point_index == 15
    assert ctx.server_id == "Novak Djokovic"
    assert ctx.returner_id == "Carlos Alcaraz"
    assert ctx.surface == "GRASS"
    assert ctx.serve_number == 2
    # Server is P2: scores flip (P2 -> server, P1 -> returner)
    assert ctx.point_score_server == 4  # AD -> 4
    assert ctx.point_score_returner == 1  # 15 -> 1
    assert ctx.game_score_server == 4  # p2_games -> 4
    assert ctx.game_score_returner == 3  # p1_games -> 3
    assert ctx.set_score_server == 1  # p2_sets -> 1
    assert ctx.set_score_returner == 0  # p1_sets -> 0
    assert ctx.match_format == "bo3"


def test_point_record_to_point_context_match_state_roundtrip() -> None:
    """Verify that PointContext produces a valid MatchState for Markov solver."""
    record = PointRecord(
        match_id="test_match",
        point_id="pt_010",
        server="P2",
        returner="P1",
        server_is_p1=False,
        surface=Surface.HARD,
        serve_number=1,
        p1_score=ValidPointScore.S30,
        p2_score=ValidPointScore.S40,
        p1_games=2,
        p2_games=5,
        p1_sets=0,
        p2_sets=1,
        point_winner=PointOutcome.RETURNER,
    )

    ctx = record.to_point_context(point_index=9)
    match_state = ctx.to_match_state()

    assert match_state.point_score_server == 3  # P2 is server (40 -> 3)
    assert match_state.point_score_returner == 2  # P1 is returner (30 -> 2)
    assert match_state.game_score_server == 5
    assert match_state.game_score_returner == 2
    assert match_state.set_score_server == 1
    assert match_state.set_score_returner == 0
    assert match_state.server_id == "P2"
    assert match_state.match_format == "bo3"


def test_spot_check_real_parquet_records() -> None:
    """Spot-check conversion against real rows from artifacts/validated_data/points.parquet."""
    parquet_path = Path("artifacts/validated_data/points.parquet")
    if not parquet_path.exists():
        pytest.skip("points.parquet not available in artifacts")

    df = pd.read_parquet(parquet_path)
    assert len(df) > 0

    # Pick sample rows: one where server_is_p1 is True, one where False
    p1_rows = df[df["server_is_p1"] == True]  # noqa: E712
    p2_rows = df[df["server_is_p1"] == False]  # noqa: E712

    assert len(p1_rows) > 0, "Expected at least one row where server_is_p1 is True"
    assert len(p2_rows) > 0, "Expected at least one row where server_is_p1 is False"

    # Spot-check P1 serving row
    sample_p1 = p1_rows.iloc[0].to_dict()
    record_p1 = PointRecord.model_validate(sample_p1)
    ctx_p1 = record_p1.to_point_context(point_index=0)

    assert ctx_p1.server_id == record_p1.server
    assert ctx_p1.returner_id == record_p1.returner
    assert ctx_p1.game_score_server == record_p1.p1_games
    assert ctx_p1.game_score_returner == record_p1.p2_games
    assert ctx_p1.set_score_server == record_p1.p1_sets
    assert ctx_p1.set_score_returner == record_p1.p2_sets

    # Spot-check P2 serving row
    sample_p2 = p2_rows.iloc[0].to_dict()
    record_p2 = PointRecord.model_validate(sample_p2)
    ctx_p2 = record_p2.to_point_context(point_index=1)

    assert ctx_p2.server_id == record_p2.server
    assert ctx_p2.returner_id == record_p2.returner
    assert ctx_p2.game_score_server == record_p2.p2_games
    assert ctx_p2.game_score_returner == record_p2.p1_games
    assert ctx_p2.set_score_server == record_p2.p2_sets
    assert ctx_p2.set_score_returner == record_p2.p1_sets
