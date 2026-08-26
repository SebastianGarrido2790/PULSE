"""Unit tests for PULSE Post-Match Tactical Analytics & Reporting Engine.

Tests deterministic post-match aggregation, pivotal point extraction,
pressure resilience partitioning, game-theoretic audits, and Markdown report generation.

Authority: Phase 6.6 Post-Match Reporting Stage 1 Verification.
"""

import pytest

from src.analytics.match_report import (
    MatchReportPayload,
    compute_game_theory_audit,
    compute_match_summary,
    compute_pressure_resilience,
    evaluate_all_points,
    extract_top_pivotal_points,
    format_match_report_markdown,
    generate_executive_debrief,
    generate_match_report,
)
from src.schemas.point_record import (
    PointOutcome,
    PointRecord,
    ServeDirection,
    Surface,
    ValidPointScore,
)


@pytest.fixture
def sample_point_records() -> list[PointRecord]:
    """Generate a synthetic sequence of 10 point records for unit testing."""
    records: list[PointRecord] = []
    # Game 1: P1 serves, P1 wins 40-15 (5 points)
    # Point 0: 0-0
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_0",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.WIDE,
            p1_score=ValidPointScore.S0,
            p2_score=ValidPointScore.S0,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,
        )
    )
    # Point 1: 15-0
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_1",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.T,
            p1_score=ValidPointScore.S15,
            p2_score=ValidPointScore.S0,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.RETURNER,
        )
    )
    # Point 2: 15-15
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_2",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=2,
            serve_direction=ServeDirection.BODY,
            p1_score=ValidPointScore.S15,
            p2_score=ValidPointScore.S15,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,
        )
    )
    # Point 3: 30-15
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_3",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.WIDE,
            p1_score=ValidPointScore.S30,
            p2_score=ValidPointScore.S15,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,
        )
    )
    # Point 4: 40-15 (Game Point)
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_4",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.T,
            p1_score=ValidPointScore.S40,
            p2_score=ValidPointScore.S15,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,
        )
    )
    # High leverage point: Break point in Set 2 (Point 5)
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_5",
            server="Alexander Zverev",
            returner="Alex De Minaur",
            server_is_p1=False,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.WIDE,
            p1_score=ValidPointScore.S30,
            p2_score=ValidPointScore.S40,
            p1_games=4,
            p2_games=4,
            p1_sets=1,
            p2_sets=0,
            point_winner=PointOutcome.RETURNER,  # De Minaur converts Break Point
            break_point=True,
        )
    )
    # Match point in Set 2 (Point 6)
    records.append(
        PointRecord(
            match_id="test_match_001",
            point_id="pt_6",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.WIDE,
            p1_score=ValidPointScore.S40,
            p2_score=ValidPointScore.S30,
            p1_games=5,
            p2_games=4,
            p1_sets=1,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,  # De Minaur converts Match Point
            match_point=True,
        )
    )
    return records


def test_evaluate_all_points(sample_point_records: list[PointRecord]) -> None:
    """Test point-by-point leverage evaluation."""
    evals = evaluate_all_points(sample_point_records)
    assert len(evals) == len(sample_point_records)
    for ev in evals:
        assert 0.0 <= ev.delta_leverage <= 1.0
        assert 0.0 <= ev.leverage_low <= ev.leverage_high <= 1.0
        assert ev.point_winner_id in ("Alex De Minaur", "Alexander Zverev")


def test_compute_match_summary(sample_point_records: list[PointRecord]) -> None:
    """Test match summary statistics computation."""
    evals = evaluate_all_points(sample_point_records)
    summary = compute_match_summary(sample_point_records, evals)

    assert summary.match_id == "test_match_001"
    assert summary.player_1 == "Alex De Minaur"
    assert summary.player_2 == "Alexander Zverev"
    assert summary.winner == "Alex De Minaur"
    assert summary.total_points == len(sample_point_records)
    assert summary.p1_points_won == 6
    assert summary.p2_points_won == 1
    assert summary.break_point_count == 1
    assert summary.break_points_converted == 1
    assert summary.max_delta_leverage >= summary.mean_delta_leverage


def test_extract_top_pivotal_points(sample_point_records: list[PointRecord]) -> None:
    """Test extraction and ranking of top pivotal moments."""
    evals = evaluate_all_points(sample_point_records)
    pivotal = extract_top_pivotal_points(evaluations=evals, top_n=3)

    assert len(pivotal) == 3
    # Assert sorted descending by delta_leverage
    assert pivotal[0].delta_leverage >= pivotal[1].delta_leverage >= pivotal[2].delta_leverage
    # Match point or break point should have high leverage
    assert any(pt.is_match_point or pt.is_break_point for pt in pivotal)
    for pt in pivotal:
        assert pt.impact_narrative != ""


def test_compute_pressure_resilience(sample_point_records: list[PointRecord]) -> None:
    """Test pressure resilience metrics across leverage tiers."""
    evals = evaluate_all_points(sample_point_records)
    pressure_list = compute_pressure_resilience(evals, "Alex De Minaur", "Alexander Zverev")

    assert len(pressure_list) == 2
    for p in pressure_list:
        assert 0.0 <= p.routine_win_rate <= 1.0
        assert -1.0 <= p.pressure_shift_delta_p <= 1.0
        assert p.resilience_assessment != ""


def test_compute_game_theory_audit(sample_point_records: list[PointRecord]) -> None:
    """Test serve-return game theory audit."""
    audits = compute_game_theory_audit(sample_point_records)
    assert len(audits) == 2
    for audit in audits:
        assert audit.sample_size >= 0
        assert 0.0 <= audit.realized_serve_mix.wide_pct <= 1.0


def test_generate_match_report_end_to_end(sample_point_records: list[PointRecord]) -> None:
    """Test end-to-end match report generation and Markdown rendering."""
    report = generate_match_report(sample_point_records)

    assert isinstance(report, MatchReportPayload)
    assert report.summary.total_points == len(sample_point_records)
    assert len(report.pivotal_points) <= 5
    assert len(report.pressure_resilience) == 2
    assert report.executive_debrief != ""

    markdown = format_match_report_markdown(report)
    assert "# PULSE Match Intelligence Report" in markdown
    assert "Alex De Minaur" in markdown
    assert "Top Pivotal Moments Audit" in markdown
    assert "Pressure Resilience Diagnostic" in markdown
    assert "Game-Theoretic Serve & Return Execution Audit" in markdown


def test_generate_executive_debrief_grounding(sample_point_records: list[PointRecord]) -> None:
    """Verify that executive debrief accurately states computed numerical values."""
    evals = evaluate_all_points(sample_point_records)
    summary = compute_match_summary(sample_point_records, evals)
    pivotal = extract_top_pivotal_points(evaluations=evals, top_n=3)
    pressure_list = compute_pressure_resilience(evals, "Alex De Minaur", "Alexander Zverev")
    audits = compute_game_theory_audit(sample_point_records)

    debrief = generate_executive_debrief(summary, pivotal, pressure_list, audits)
    assert "Alex De Minaur" in debrief
    assert "Alexander Zverev" in debrief
    assert f"{summary.mean_delta_leverage:.1%}" in debrief
    assert f"{summary.max_delta_leverage:.1%}" in debrief
    assert f"{summary.high_leverage_point_count}" in debrief


def test_generate_executive_debrief_with_custom_client(
    sample_point_records: list[PointRecord],
) -> None:
    """Verify that a custom LLM callable debrief synthesizer is called when provided."""
    evals = evaluate_all_points(sample_point_records)
    summary = compute_match_summary(sample_point_records, evals)
    pivotal = extract_top_pivotal_points(evaluations=evals, top_n=3)
    pressure_list = compute_pressure_resilience(evals, "Alex De Minaur", "Alexander Zverev")
    audits = compute_game_theory_audit(sample_point_records)

    def mock_llm_synthesizer(payload: dict) -> str:
        return "Custom Grounded LLM Debrief: Alex De Minaur controlled the baseline tempo."

    debrief = generate_executive_debrief(
        summary, pivotal, pressure_list, audits, llm_client=mock_llm_synthesizer
    )
    assert debrief == "Custom Grounded LLM Debrief: Alex De Minaur controlled the baseline tempo."


@pytest.mark.asyncio
async def test_generate_match_report_async(sample_point_records: list[PointRecord]) -> None:
    """Verify async match report generation with attached Markdown report."""
    from src.analytics.match_report import generate_match_report_async

    report = await generate_match_report_async(sample_point_records)
    assert report.summary.match_id == "test_match_001"
    assert report.executive_debrief != ""
    assert report.markdown_report != ""
    assert "# PULSE Match Intelligence Report" in report.markdown_report


@pytest.mark.asyncio
async def test_generate_match_report_async_groq_mock(
    sample_point_records: list[PointRecord],
) -> None:
    """Verify async match report generation invokes Groq when configured and key is present."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.analytics.match_report import generate_match_report_async
    from src.config.loader import load_params

    cfg = load_params()
    mock_choice = MagicMock()
    mock_choice.message.content = "Groq Debrief: Dominant baseline performance by De Minaur."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test_key"}):
        with patch("groq.AsyncGroq", return_value=mock_client):
            report = await generate_match_report_async(sample_point_records, params=cfg)
            expected = "Groq Debrief: Dominant baseline performance by De Minaur."
            assert report.executive_debrief == expected
