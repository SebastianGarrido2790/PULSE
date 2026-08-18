"""Unit tests for src/utils/persistence.py (SQLite audit persistence layer).

Verifies table initialization idempotency, transactional writes, and round-trip retrieval
using isolated temporary SQLite databases (Gate 3).
"""

from pathlib import Path

import pytest

from src.graph.state import DecisionLogEntry, TacticalOutputResult
from src.utils.persistence import (
    get_decision_logs,
    get_tactical_outputs,
    init_db,
    persist_point_event,
)


@pytest.mark.asyncio
async def test_init_db_idempotency(tmp_path: Path) -> None:
    """Verify init_db creates tables and can be safely called multiple times."""
    db_file = tmp_path / "test_session.db"

    # First call: creates tables
    await init_db(db_file)
    assert db_file.exists()

    # Second call: must succeed without error (idempotent)
    await init_db(db_file)


@pytest.mark.asyncio
async def test_persist_point_event_roundtrip(tmp_path: Path) -> None:
    """Verify persisting point events round-trips correctly for logs and tactical output."""
    db_file = tmp_path / "test_session.db"
    await init_db(db_file)

    decision_entries = [
        DecisionLogEntry(
            node="StateMonitorNode",
            fired=True,
            reason="State monitor always fires",
        ),
        DecisionLogEntry(
            node="PressureDiagnosticNode",
            fired=True,
            reason="Leverage delta 0.15 >= 0.10 threshold",
        ),
        DecisionLogEntry(
            node="StrategyExploitNode",
            fired=False,
            reason="Opponent observation count 12 < 30 gate",
        ),
    ]

    tactical = TacticalOutputResult(
        narrative="Elevated pressure point. Returner chokes on 2nd serve.",
        escalated=True,
        raw_payload={"delta_L": 0.15, "p_hat": 0.58},
        is_llm_fallback=False,
    )

    # Persist point 0
    await persist_point_event(
        match_id="test_match_001",
        point_index=0,
        decision_log=decision_entries,
        tactical_output=tactical,
        db_path=db_file,
    )

    # Retrieve decision logs
    logs = await get_decision_logs("test_match_001", point_index=0, db_path=db_file)
    assert len(logs) == 3
    assert logs[0]["node"] == "StateMonitorNode"
    assert logs[0]["fired"] == 1
    assert logs[1]["node"] == "PressureDiagnosticNode"
    assert logs[1]["fired"] == 1
    assert logs[2]["node"] == "StrategyExploitNode"
    assert logs[2]["fired"] == 0
    assert "12 < 30" in logs[2]["reason"]

    # Retrieve tactical outputs
    tactical_records = await get_tactical_outputs(
        "test_match_001", point_index=0, db_path=db_file
    )
    assert len(tactical_records) == 1
    rec = tactical_records[0]
    assert rec["match_id"] == "test_match_001"
    assert rec["point_index"] == 0
    assert rec["narrative"] == "Elevated pressure point. Returner chokes on 2nd serve."
    assert rec["escalated"] == 1
    assert rec["is_llm_fallback"] == 0
    assert rec["raw_payload"]["delta_L"] == 0.15


@pytest.mark.asyncio
async def test_persist_point_event_dict_inputs(tmp_path: Path) -> None:
    """Verify persist_point_event accepts dictionary representations."""
    db_file = tmp_path / "test_session_dicts.db"
    await init_db(db_file)

    dict_logs = [
        {"node": "StateMonitorNode", "fired": True, "reason": "Always on"},
    ]
    dict_tactical = {
        "narrative": "Routine hold.",
        "escalated": False,
        "raw_payload": {"delta_L": 0.03},
        "is_llm_fallback": False,
    }

    await persist_point_event(
        match_id="test_match_002",
        point_index=1,
        decision_log=dict_logs,
        tactical_output=dict_tactical,
        db_path=db_file,
    )

    logs = await get_decision_logs("test_match_002", db_path=db_file)
    assert len(logs) == 1
    assert logs[0]["node"] == "StateMonitorNode"

    tactical = await get_tactical_outputs("test_match_002", db_path=db_file)
    assert len(tactical) == 1
    assert tactical[0]["escalated"] == 0
    assert tactical[0]["raw_payload"] == {"delta_L": 0.03}
