"""PULSE — SQLite Persistence Layer for Point Event Audit Trails.

Provides asynchronous database initialization and transactional writes for
decision audit logs and tactical output payloads per point event.

Authority: Phase 6 Decision D-4, prd.md FR-12.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiosqlite

from src.config.loader import load_params
from src.graph.state import DecisionLogEntry, TacticalOutputResult
from src.utils.exceptions import PersistenceException
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_db_path(db_path: Path | str | None = None) -> Path | str:
    """Resolve database path from argument or default configuration."""
    if db_path is not None:
        return db_path
    configured_path = load_params().api.db_path
    return Path(configured_path)


def _ensure_parent_dir(db_path: Path | str) -> None:
    """Ensure parent directory exists for file-based databases."""
    if isinstance(db_path, str) and (db_path == ":memory:" or db_path.startswith("file:")):
        return
    path_obj = Path(db_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)


async def init_db(db_path: Path | str | None = None) -> None:
    """Initialize SQLite database tables and indices idempotently.

    Args:
        db_path: Optional explicit database path. If None, loaded from params.yaml.

    Raises:
        PersistenceException: If table creation fails.
    """
    target = _resolve_db_path(db_path)
    _ensure_parent_dir(target)

    schema_sql = """
    CREATE TABLE IF NOT EXISTS decision_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT NOT NULL,
        point_index INTEGER NOT NULL,
        node TEXT NOT NULL,
        fired INTEGER NOT NULL,
        reason TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tactical_outputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT NOT NULL,
        point_index INTEGER NOT NULL,
        narrative TEXT NOT NULL,
        escalated INTEGER NOT NULL,
        raw_payload_json TEXT NOT NULL,
        is_llm_fallback INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_decision_logs_match_point
        ON decision_logs (match_id, point_index);

    CREATE INDEX IF NOT EXISTS idx_tactical_outputs_match_point
        ON tactical_outputs (match_id, point_index);
    """

    try:
        async with aiosqlite.connect(str(target)) as db:
            await db.executescript(schema_sql)
            await db.commit()
        logger.info("SQLite persistence initialized at [%s]", target)
    except Exception as e:
        msg = f"Failed to initialize SQLite database at [{target}]: {e}"
        logger.error(msg)
        raise PersistenceException(msg) from e


async def persist_point_event(
    match_id: str,
    point_index: int,
    decision_log: Sequence[DecisionLogEntry | dict[str, Any]] | None = None,
    tactical_output: TacticalOutputResult | dict[str, Any] | None = None,
    db_path: Path | str | None = None,
) -> None:
    """Persist decision log entries and tactical output for a single point event.

    Args:
        match_id: Unique identifier for the match.
        point_index: 0-indexed chronological point sequence number.
        decision_log: Optional sequence of DecisionLogEntry objects or dictionaries.
        tactical_output: Optional TacticalOutputResult object or dictionary.
        db_path: Optional explicit database path. If None, loaded from params.yaml.

    Raises:
        PersistenceException: If database write transaction fails.
    """
    target = _resolve_db_path(db_path)
    _ensure_parent_dir(target)

    try:
        async with aiosqlite.connect(str(target)) as db:
            # Persist decision log entries if present
            if decision_log:
                entries_to_insert: list[tuple[str, int, str, int, str]] = []
                for entry in decision_log:
                    if isinstance(entry, DecisionLogEntry):
                        node = entry.node
                        fired = 1 if entry.fired else 0
                        reason = entry.reason
                    elif isinstance(entry, dict):
                        node = str(entry.get("node", ""))
                        fired = 1 if entry.get("fired") else 0
                        reason = str(entry.get("reason", ""))
                    else:
                        continue
                    entries_to_insert.append((match_id, point_index, node, fired, reason))

                if entries_to_insert:
                    await db.executemany(
                        """
                        INSERT INTO decision_logs (match_id, point_index, node, fired, reason)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        entries_to_insert,
                    )

            # Persist tactical output if present
            if tactical_output is not None:
                if isinstance(tactical_output, TacticalOutputResult):
                    narrative = tactical_output.narrative
                    escalated = 1 if tactical_output.escalated else 0
                    raw_payload_json = json.dumps(tactical_output.raw_payload)
                    is_llm_fallback = 1 if tactical_output.is_llm_fallback else 0
                elif isinstance(tactical_output, dict):
                    narrative = str(tactical_output.get("narrative", ""))
                    escalated = 1 if tactical_output.get("escalated") else 0
                    raw_payload = tactical_output.get("raw_payload", {})
                    raw_payload_json = json.dumps(raw_payload)
                    is_llm_fallback = 1 if tactical_output.get("is_llm_fallback") else 0
                else:
                    narrative = ""
                    escalated = 0
                    raw_payload_json = "{}"
                    is_llm_fallback = 0

                await db.execute(
                    """
                    INSERT INTO tactical_outputs (
                        match_id, point_index, narrative, escalated,
                        raw_payload_json, is_llm_fallback
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        point_index,
                        narrative,
                        escalated,
                        raw_payload_json,
                        is_llm_fallback,
                    ),
                )

            await db.commit()
    except Exception as e:
        msg = f"Failed to persist point event [match={match_id}, point={point_index}]: {e}"
        logger.error(msg)
        raise PersistenceException(msg) from e


async def get_decision_logs(
    match_id: str,
    point_index: int | None = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve decision log records from SQLite database for auditing and testing.

    Args:
        match_id: Unique identifier for the match.
        point_index: Optional point index filter.
        db_path: Optional explicit database path.

    Returns:
        list[dict[str, Any]]: List of matching decision log row dictionaries.
    """
    target = _resolve_db_path(db_path)
    async with aiosqlite.connect(str(target)) as db:
        db.row_factory = aiosqlite.Row
        if point_index is not None:
            query = """
            SELECT id, match_id, point_index, node, fired, reason, created_at
            FROM decision_logs
            WHERE match_id = ? AND point_index = ?
            ORDER BY id ASC
            """
            params = (match_id, point_index)
        else:
            query = """
            SELECT id, match_id, point_index, node, fired, reason, created_at
            FROM decision_logs
            WHERE match_id = ?
            ORDER BY id ASC
            """
            params = (match_id,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_tactical_outputs(
    match_id: str,
    point_index: int | None = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve tactical output records from SQLite database for auditing and testing.

    Args:
        match_id: Unique identifier for the match.
        point_index: Optional point index filter.
        db_path: Optional explicit database path.

    Returns:
        list[dict[str, Any]]: List of matching tactical output row dictionaries.
    """
    target = _resolve_db_path(db_path)
    async with aiosqlite.connect(str(target)) as db:
        db.row_factory = aiosqlite.Row
        if point_index is not None:
            query = """
            SELECT id, match_id, point_index, narrative, escalated, raw_payload_json,
                   is_llm_fallback, created_at
            FROM tactical_outputs
            WHERE match_id = ? AND point_index = ?
            ORDER BY id ASC
            """
            params = (match_id, point_index)
        else:
            query = """
            SELECT id, match_id, point_index, narrative, escalated, raw_payload_json,
                   is_llm_fallback, created_at
            FROM tactical_outputs
            WHERE match_id = ?
            ORDER BY id ASC
            """
            params = (match_id,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                d["raw_payload"] = json.loads(d["raw_payload_json"])
                results.append(d)
            return results
