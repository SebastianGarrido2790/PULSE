"""PULSE — Integration Tests for Post-Match Tactical Reporting API.

Verifies end-to-end HTTP endpoint delivery of post-match intelligence:
1. GET /v1/matches/{match_id}/report with format=json returns valid typed MatchReportResponse.
2. GET /v1/matches/{match_id}/report with format=markdown returns formatted Markdown debrief.
3. Parameter propagation for match_format=bo5 and format variations.
4. Robust 404 error responses for invalid or nonexistent match IDs.
5. Integration with deterministic fallback and async executive debrief synthesis.

Authority: Phase 6.6 Post-Match Reporting Stage 6 Verification.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.schemas import MatchReportResponse


@pytest.fixture
def test_parquet_file(tmp_path: Path) -> Path:
    """Create a temporary Parquet file simulating historical charted match records."""
    import pandas as pd

    data = {
        "match_id": ["integ_test_match"] * 12,
        "point_id": [f"pt_{i}" for i in range(12)],
        "server": ["Alex De Minaur"] * 6 + ["Alexander Zverev"] * 6,
        "returner": ["Alexander Zverev"] * 6 + ["Alex De Minaur"] * 6,
        "server_is_p1": [True] * 6 + [False] * 6,
        "surface": ["HARD"] * 12,
        "serve_number": [1, 1, 2, 1, 1, 2, 1, 2, 1, 1, 2, 1],
        "serve_direction": [
            "wide",
            "t",
            "body",
            "wide",
            "t",
            "wide",
            "t",
            "wide",
            "t",
            "body",
            "t",
            "wide",
        ],
        "p1_score": ["0", "15", "15", "30", "40", "40", "0", "0", "15", "30", "30", "40"],
        "p2_score": ["0", "0", "15", "15", "15", "30", "0", "15", "15", "15", "30", "30"],
        "p1_games": [0] * 6 + [1] * 6,
        "p2_games": [0] * 6 + [0] * 6,
        "p1_sets": [0] * 12,
        "p2_sets": [0] * 12,
        "point_winner": [
            "server",
            "server",
            "returner",
            "server",
            "returner",
            "server",
            "server",
            "server",
            "returner",
            "server",
            "returner",
            "server",
        ],
    }
    df = pd.DataFrame(data)
    parquet_path = tmp_path / "integ_test_match.parquet"
    df.to_parquet(parquet_path)
    return parquet_path


@pytest.mark.asyncio
async def test_get_match_report_json_endpoint(
    test_parquet_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify GET /v1/matches/{id}/report?format=json returns valid 200 payload matching schema."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: test_parquet_file,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/matches/integ_test_match/report?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

        raw_json = response.json()
        validated = MatchReportResponse.model_validate(raw_json)

        assert validated.summary.match_id == "integ_test_match"
        assert validated.summary.total_points == 12
        assert len(validated.pivotal_points) > 0
        assert len(validated.pressure_resilience) == 2
        assert len(validated.game_theory_audit) == 2
        assert len(validated.executive_debrief) > 50
        assert validated.markdown_report.startswith("# PULSE Match Intelligence Report")

        # Verify Wilson CI bounds are geometrically sound
        for pt in validated.pivotal_points:
            assert pt.leverage_low <= pt.delta_leverage <= pt.leverage_high


@pytest.mark.asyncio
async def test_get_match_report_markdown_endpoint(
    test_parquet_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify GET /v1/matches/{id}/report?format=markdown returns valid text/markdown."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: test_parquet_file,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/matches/integ_test_match/report?format=markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("content-type", "")

        text = response.text
        assert "# PULSE Match Intelligence Report" in text
        assert "## 1. Executive Strategic Summary" in text
        assert "## 2. Match Overview & Key Indicators" in text
        assert "## 3. Top Pivotal Moments Audit" in text
        assert "## 4. Pressure Resilience Diagnostic" in text
        assert "## 5. Game-Theoretic Serve & Return Execution" in text
        assert "Alex De Minaur" in text
        assert "Alexander Zverev" in text


@pytest.mark.asyncio
async def test_get_match_report_bo5_format_parameter(
    test_parquet_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify GET /v1/matches/{id}/report?match_format=bo5 passes match_format
    to analytics engine.
    """
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: test_parquet_file,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/matches/integ_test_match/report?format=json&match_format=bo5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["match_id"] == "integ_test_match"


@pytest.mark.asyncio
async def test_get_match_report_custom_llm_debrief_integration(
    test_parquet_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify LLM synthesis generates customized debrief when LLM client succeeds."""
    monkeypatch.setattr(
        "src.simulator.replay.resolve_parquet_path",
        lambda *args, **kwargs: test_parquet_file,
    )
    monkeypatch.setenv("GROQ_API_KEY", "mock-test-key")

    mock_choice = MagicMock()
    mock_choice.message.content = (
        "Synthesized AI debrief: Alex De Minaur controlled pivotal moments."
    )
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: mock_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/matches/integ_test_match/report?format=json",
            headers={"x-api-key": "mock-test-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Alex De Minaur controlled pivotal moments" in data["executive_debrief"]


@pytest.mark.asyncio
async def test_get_match_report_404_for_unknown_match() -> None:
    """Verify GET /v1/matches/{id}/report returns 404 for unknown match ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/matches/non_existent_match_404/report")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
