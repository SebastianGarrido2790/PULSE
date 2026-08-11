"""PULSE — Integration Tests for Event-Driven LangGraph Orchestration Graph.

Verifies end-to-end graph execution across match states, proving the conditional topology:
1. Routine point (low leverage): only StateMonitorNode runs; pressure/exploit suppressed.
2. High-leverage, sparse opponent data: pressure diagnostic runs; exploit degrades.
3. High-leverage, sufficient opponent data: pressure diagnostic and exploit stub run.
4. Named assertion proving visited node paths differ across match states (Phase 4 Exit Criteria).

Authority: Phase 4 Decisions D-1 through D-11, ADR-001, FR-3 through FR-7.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.graph.pulse_graph import build_pulse_graph
from src.graph.state import PointContext, PulseGraphState


@pytest.fixture
def compiled_graph():
    """Construct and compile the real PULSE orchestration graph once for integration tests."""
    return build_pulse_graph()


@pytest.mark.integration
@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_routine_point_no_escalation(mock_llm: AsyncMock, compiled_graph) -> None:
    """Fixture 1 — Routine Point: low leverage (0-0, 0-0, 0-0), zero escalation, zero LLM calls."""
    context = PointContext(
        match_id="match_integ_001",
        point_index=1,
        server_id="Carlos Alcaraz",
        returner_id="Carlos Alcaraz",
        surface="HARD",
        serve_number=1,
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=0,
        set_score_returner=0,
    )
    initial_state = PulseGraphState(point_context=context)

    final_state = await compiled_graph.ainvoke(initial_state)

    # 1. Assert StateMonitorNode computed leverage below threshold
    assert final_state["leverage_result"] is not None
    assert final_state["leverage_result"].delta_leverage_low < 0.10

    # 2. Assert pressure and exploit nodes did NOT run
    assert final_state.get("pressure_result") is None
    assert final_state.get("exploit_result") is None

    # 3. Assert decision log records 2 suppressions
    log = final_state["decision_log"]
    assert len(log) == 2
    assert log[0].node == "pressure_diagnostic" and log[0].fired is False
    assert log[1].node == "strategy_exploit" and log[1].fired is False

    # 4. Assert zero LLM calls were made on routine point (D-7 cost guard)
    assert mock_llm.call_count == 0
    tactical = final_state["tactical_output"]
    assert tactical is not None
    assert tactical.escalated is False
    assert "Routine point" in tactical.narrative


@pytest.mark.integration
@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_high_leverage_sparse_data(mock_llm: AsyncMock, compiled_graph) -> None:
    """Fixture 2 — High Leverage, Sparse Opponent: pressure diagnostic runs, exploit degrades."""
    mock_llm.return_value = "Carlos Alcaraz serve win rate drops under elevated leverage."

    # Final set (1-1 in sets, 4-5 in games, 30-40 Break Point: dL_low ~0.87 >= 0.10)
    context = PointContext(
        match_id="match_integ_002",
        point_index=10,
        server_id="Carlos Alcaraz",
        returner_id="sparse_player_999",  # Sparse opponent (< 30 sample size)
        surface="HARD",
        serve_number=1,
        point_score_server=2,
        point_score_returner=3,
        game_score_server=4,
        game_score_returner=5,
        set_score_server=1,
        set_score_returner=1,
    )
    initial_state = PulseGraphState(point_context=context)

    final_state = await compiled_graph.ainvoke(initial_state)

    # 1. Assert high leverage triggered escalation
    assert final_state["leverage_result"] is not None
    assert final_state["leverage_result"].delta_leverage_low >= 0.10

    # 2. Assert pressure diagnostic fired and found player bucket
    assert final_state.get("pressure_result") is not None
    assert final_state["pressure_result"].server_id == "Carlos Alcaraz"

    # 3. Assert exploit node ran and degraded gracefully (status: insufficient_data)
    assert final_state.get("exploit_result") is not None
    assert final_state["exploit_result"].status == "insufficient_data"
    assert final_state["exploit_result"].is_sufficient_sample is False

    # 4. Assert decision log records both nodes firing
    log = final_state["decision_log"]
    assert len(log) == 2
    assert log[0].node == "pressure_diagnostic" and log[0].fired is True
    assert log[1].node == "strategy_exploit" and log[1].fired is True

    # 5. Assert LLM narrative synthesis was invoked for escalated point
    assert mock_llm.call_count == 1
    assert final_state["tactical_output"].escalated is True


@pytest.mark.integration
@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_high_leverage_sufficient_data(mock_llm: AsyncMock, compiled_graph) -> None:
    """Fixture 3 — High Leverage, Sufficient Opponent: pressure diagnostic & exploit stub run."""
    mock_llm.return_value = (
        "Carlos Alcaraz under pressure: -6.5% serve win rate. Exploit module pending."
    )

    # Final set (1-1 in sets, 4-5 in games, 30-40 Break Point: dL_low ~0.87 >= 0.10)
    context = PointContext(
        match_id="match_integ_003",
        point_index=12,
        server_id="Carlos Alcaraz",
        returner_id="Carlos Alcaraz",  # Opponent with >= 30 sample size in stratum table
        surface="HARD",
        serve_number=1,
        point_score_server=2,
        point_score_returner=3,
        game_score_server=4,
        game_score_returner=5,
        set_score_server=1,
        set_score_returner=1,
    )
    initial_state = PulseGraphState(point_context=context)

    final_state = await compiled_graph.ainvoke(initial_state)

    # 1. Assert pressure diagnostic fired
    assert final_state.get("pressure_result") is not None
    assert final_state["pressure_result"].server_id == "Carlos Alcaraz"

    # 2. Assert exploit node ran and passed sufficiency gate (status: module_not_yet_implemented)
    assert final_state.get("exploit_result") is not None
    assert final_state["exploit_result"].status == "module_not_yet_implemented"
    assert final_state["exploit_result"].is_sufficient_sample is True
    assert final_state["exploit_result"].recommendation is None

    # 3. Assert zero suppressions in decision log
    log = final_state["decision_log"]
    assert len(log) == 2
    assert all(entry.fired is True for entry in log)

    # 4. Assert LLM narrative synthesis was invoked
    assert mock_llm.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
@patch("src.graph.tactical_output.call_narrative_llm", new_callable=AsyncMock)
async def test_conditional_topology_node_execution_differs_by_match_state(
    mock_llm: AsyncMock, compiled_graph
) -> None:
    """Step 49 — Named Exit Criteria Assertion: prove visited node sets differ across states."""
    mock_llm.return_value = "High leverage narrative."

    # State A: Routine point (0-0, 0-0, 0-0)
    ctx_routine = PointContext(
        match_id="m_diff_1",
        point_index=1,
        server_id="Carlos Alcaraz",
        returner_id="Carlos Alcaraz",
        surface="HARD",
        serve_number=1,
        point_score_server=0,
        point_score_returner=0,
        game_score_server=0,
        game_score_returner=0,
        set_score_server=0,
        set_score_returner=0,
    )
    res_routine = await compiled_graph.ainvoke(PulseGraphState(point_context=ctx_routine))

    # State B: High leverage point (30-40, 4-5 games, 1-1 sets)
    ctx_escalated = PointContext(
        match_id="m_diff_2",
        point_index=10,
        server_id="Carlos Alcaraz",
        returner_id="Carlos Alcaraz",
        surface="HARD",
        serve_number=1,
        point_score_server=2,
        point_score_returner=3,
        game_score_server=4,
        game_score_returner=5,
        set_score_server=1,
        set_score_returner=1,
    )
    res_escalated = await compiled_graph.ainvoke(PulseGraphState(point_context=ctx_escalated))

    # Extract non-None output keys (representing executed node outputs)
    routine_executed_outputs = {
        k for k in ["pressure_result", "exploit_result"] if res_routine.get(k) is not None
    }
    escalated_executed_outputs = {
        k for k in ["pressure_result", "exploit_result"] if res_escalated.get(k) is not None
    }

    # CRITICAL PHASE 4 EXIT CRITERIA ASSERTION:
    # Prove that the conditional graph topology changes its execution path dynamically
    # based on match state (routine = empty diagnostic set, escalated = non-empty set).
    err_msg = (
        f"CRITICAL FAILURE: Graph topology did not change! "
        f"Routine: {routine_executed_outputs}, Escalated: {escalated_executed_outputs}"
    )
    assert routine_executed_outputs != escalated_executed_outputs, err_msg
    assert len(routine_executed_outputs) == 0
    assert len(escalated_executed_outputs) == 2
