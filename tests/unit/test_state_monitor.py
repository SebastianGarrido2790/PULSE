"""PULSE — Unit Tests for StateMonitorNode (src/graph/state_monitor.py).

Verifies node execution in isolation (no graph runtime) with fixture stratum tables.

Authority: Stage 3 Step 18, FR-3, Decision D-2.
"""

import pytest

from src.graph.state import PointContext, PulseGraphState
from src.graph.state_monitor import make_state_monitor_node
from src.models.point_win_classifier import StratumEntry, StratumTable


@pytest.fixture
def mock_stratum_table() -> StratumTable:
    """Provide a fixture StratumTable with known Tier 0 and Tier 1 entries."""
    tier0 = {
        "alcaraz_c|HARD|1": StratumEntry(wins=40, sample_size=50, p_hat=0.80),
    }
    tier1 = {
        "sinner_j|1": StratumEntry(wins=30, sample_size=40, p_hat=0.75),
    }
    tier2 = {
        "CLAY|2": StratumEntry(wins=100, sample_size=200, p_hat=0.50),
    }
    return StratumTable(
        tier0_exact=tier0,
        tier1_player=tier1,
        tier2_surface=tier2,
        global_default_p=0.62,
    )


@pytest.mark.asyncio
async def test_state_monitor_node_execution(mock_stratum_table: StratumTable) -> None:
    """Verify StateMonitorNode computes leverage and uncertainty for Tier 0 match state."""
    node_fn = make_state_monitor_node(mock_stratum_table)

    context = PointContext(
        match_id="match_test_001",
        point_index=5,
        server_id="alcaraz_c",
        returner_id="sinner_j",
        surface="HARD",
        serve_number=1,
        point_score_server=3,  # 40-40 (Deuce)
        point_score_returner=3,
        game_score_server=4,
        game_score_returner=4,
        set_score_server=1,
        set_score_returner=1,
    )
    state = PulseGraphState(
        point_context=context,
        leverage_result=None,  # StateMonitorNode computes this
    )

    update = await node_fn(state)

    assert "leverage_result" in update
    res = update["leverage_result"]

    assert res.p_hat == 0.80
    assert res.sample_size == 50
    assert res.fallback_tier == 0
    assert 0.0 <= res.delta_leverage <= 1.0
    assert 0.0 <= res.delta_leverage_low <= res.delta_leverage
    assert res.delta_leverage <= res.delta_leverage_high <= 1.0


@pytest.mark.asyncio
async def test_state_monitor_fallback_tier(mock_stratum_table: StratumTable) -> None:
    """Verify StateMonitorNode correctly falls back to Tier 3 for unmodeled players."""
    node_fn = make_state_monitor_node(mock_stratum_table)

    context = PointContext(
        match_id="match_test_002",
        point_index=0,
        server_id="unknown_player",
        returner_id="sinner_j",
        surface="GRASS",  # Not in tier2
        serve_number=2,
    )
    state = PulseGraphState(point_context=context, leverage_result=None)

    update = await node_fn(state)
    res = update["leverage_result"]

    assert res.fallback_tier == 3
    assert res.p_hat == 0.62
    assert res.sample_size == 0
    assert 0.0 <= res.delta_leverage <= 1.0
