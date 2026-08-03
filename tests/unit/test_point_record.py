"""Unit tests for src/schemas/point_record.py (PointRecord domain model & pandera schema)."""

import pandas as pd
import pytest
from pydantic import ValidationError

from src.schemas.point_record import (
    PointOutcome,
    PointRecord,
    PointRecordSchema,
    ServeDirection,
    ServeNumber,
    Surface,
    ValidPointScore,
)


def test_point_record_valid_instantiation() -> None:
    """Test valid instantiation of PointRecord Pydantic model."""
    record = PointRecord(
        match_id="m1",
        point_id="m1_p1",
        server="p1",
        returner="p2",
        server_is_p1=True,
        surface=Surface.HARD,
        serve_number=1,
        serve_direction=ServeDirection.WIDE,
        p1_score=ValidPointScore.S15,
        p2_score=ValidPointScore.S30,
        p1_games=2,
        p2_games=1,
        p1_sets=0,
        p2_sets=0,
        rally_length=4,
        point_winner=PointOutcome.SERVER,
    )

    assert record.match_id == "m1"
    assert record.surface == Surface.HARD
    assert record.serve_number == ServeNumber.FIRST
    assert record.p1_score == "15"
    assert record.get_server_score_int() == 1
    assert record.get_returner_score_int() == 2


def test_point_record_string_coercion() -> None:
    """Test surface and serve direction string normalization via dict validation."""
    record = PointRecord.model_validate(
        {
            "match_id": "m1",
            "point_id": "m1_p2",
            "server": "p2",
            "returner": "p1",
            "server_is_p1": False,
            "surface": "clay",  # lowercase coerced to CLAY
            "serve_number": 2,
            "serve_direction": "T",
            "p1_score": "40",
            "p2_score": "AD",
            "point_winner": "returner",
        }
    )

    assert record.surface == Surface.CLAY
    assert record.serve_direction == ServeDirection.T
    assert record.p2_score == ValidPointScore.AD
    assert record.get_server_score_int() == 4
    assert record.get_returner_score_int() == 3


def test_point_record_invalid_score_rejection() -> None:
    """Test strict score coercion rejecting invalid score strings per Decision D-2a."""
    with pytest.raises(ValidationError):
        PointRecord.model_validate(
            {
                "match_id": "m1",
                "point_id": "m1_p3",
                "server": "p1",
                "returner": "p2",
                "server_is_p1": True,
                "surface": "HARD",
                "serve_number": 1,
                "p1_score": "150",  # invalid tennis score
                "p2_score": "30",
                "point_winner": "server",
            }
        )


def test_pandera_schema_validation_success() -> None:
    """Test Pandera PointRecordSchema validating a valid DataFrame."""
    df = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "point_id": "m1_p1",
                "server": "p1",
                "returner": "p2",
                "server_is_p1": True,
                "surface": "HARD",
                "serve_number": 1,
                "serve_direction": "wide",
                "p1_score": "15",
                "p2_score": "0",
                "p1_games": 1,
                "p2_games": 0,
                "p1_sets": 0,
                "p2_sets": 0,
                "rally_length": 3,
                "point_winner": "server",
                "break_point": False,
                "set_point": False,
                "match_point": False,
            }
        ]
    )

    validated_df = PointRecordSchema.validate(df)
    assert len(validated_df) == 1
