"""PULSE — Historical Match Replay & Streaming Event Generator.

Drives match replay simulation point-by-point, invokes the LangGraph orchestration
graph for leverage calculation and conditional tactical escalation, persists audit records
to SQLite, and yields structured StreamPointEvent payloads with configurable cadence.

Authority: Phase 6 Decisions D-1, D-2, D-4, D-6, D-8, D-13.
"""

import asyncio
import functools
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from langgraph.graph.state import CompiledStateGraph

from src.api.schemas import StreamPointEvent
from src.config.loader import Params, load_params
from src.graph.pulse_graph import build_pulse_graph
from src.graph.state import PointContext, PulseGraphState
from src.schemas.point_record import PointRecord, infer_match_format
from src.utils.exceptions import IngestionException, PersistenceException
from src.utils.logger import get_logger
from src.utils.persistence import persist_point_event

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_parquet_path(parquet_path: Path | str | None = None) -> Path:
    """Resolve the path to the validated points parquet dataset."""
    if parquet_path is not None:
        return Path(parquet_path)
    cfg = load_params()
    return PROJECT_ROOT / cfg.ingestion.validated_data_dir / cfg.ingestion.validated_file_name


@functools.lru_cache(maxsize=8)
def _read_distinct_matches_cached(parquet_path_str: str, mtime_ns: int) -> list[str]:
    p = Path(parquet_path_str)
    if not p.exists():
        return []
    df = pd.read_parquet(p, columns=["match_id"])
    return sorted(df["match_id"].drop_duplicates().tolist())


def get_available_matches(parquet_path: Path | str | None = None) -> list[str]:
    """Return a list of all distinct match IDs available in the dataset.

    Args:
        parquet_path: Optional explicit path to points.parquet.

    Returns:
        list[str]: Sorted list of unique match IDs.
    """
    resolved_path = resolve_parquet_path(parquet_path)
    if not resolved_path.exists():
        logger.warning("Dataset not found at [%s]", resolved_path)
        return []

    mtime_ns = resolved_path.stat().st_mtime_ns
    return _read_distinct_matches_cached(str(resolved_path), mtime_ns)


def load_match_records(
    match_id: str,
    parquet_path: Path | str | None = None,
) -> list[PointRecord]:
    """Load chronological point records for a given match from parquet dataset.

    Args:
        match_id: Unique identifier for the match.
        parquet_path: Optional explicit path to points.parquet.

    Returns:
        list[PointRecord]: Ordered list of PointRecord domain objects.

    Raises:
        IngestionException: If the dataset is missing or the match ID is not found.
    """
    resolved_path = resolve_parquet_path(parquet_path)
    if not resolved_path.exists():
        msg = f"Points dataset not found at [{resolved_path}]"
        logger.error(msg)
        raise IngestionException(msg)

    df = pd.read_parquet(resolved_path)
    match_df = df[df["match_id"] == match_id].reset_index(drop=True)

    if len(match_df) == 0:
        msg = f"Match ID [{match_id}] not found in points dataset [{resolved_path}]"
        logger.error(msg)
        raise IngestionException(msg)

    dict_rows: list[dict[str, Any]] = match_df.to_dict(orient="records")  # type: ignore[assignment,reportCallIssue]
    records: list[PointRecord] = [PointRecord.model_validate(row) for row in dict_rows]
    logger.info("Loaded %d points for match [%s]", len(records), match_id)
    return records


async def generate_point_events(
    match_id: str,
    speed_multiplier: float = 1.0,
    match_format: Literal["bo3", "bo5"] = "bo3",
    graph: CompiledStateGraph | None = None,
    parquet_path: Path | str | None = None,
    db_path: Path | str | None = None,
    params: Params | None = None,
) -> AsyncGenerator[StreamPointEvent, None]:
    """Asynchronously generate streaming point events for a tennis match.

    Walks the match chronologically point-by-point, runs graph inference,
    persists decision and tactical logs to SQLite, and yields a StreamPointEvent
    at the configured replay cadence (D-6).

    Args:
        match_id: Unique match identifier to replay.
        speed_multiplier: Playback speed multiplier (0.0 for instant zero-delay playback).
        match_format: Match scoring structure ('bo3' or 'bo5', default 'bo3').
        graph: Optional pre-compiled LangGraph instance. Built automatically if None.
        parquet_path: Optional custom path to points.parquet dataset.
        db_path: Optional custom SQLite database path for persistence.
        params: Optional pre-loaded Params configuration container.

    Yields:
        StreamPointEvent: Structured point-level payload or error event.

    Authority: Phase 6 Decisions D-1, D-2, D-4, D-6, D-8, D-13.
    """
    cfg = params if params is not None else load_params()
    active_graph = graph if graph is not None else build_pulse_graph(params=cfg)

    # Compute cadence delay (D-6)
    base_interval = cfg.simulator.default_interval_s
    if speed_multiplier <= 0.0:
        delay = 0.0
    else:
        delay = base_interval / speed_multiplier

    # Load match records in row order (D-3b)
    try:
        records = load_match_records(match_id, parquet_path=parquet_path)
    except Exception as e:
        logger.error("Failed to load match records for [%s]: %s", match_id, e)
        fallback_ctx = PointContext(
            match_id=match_id,
            point_index=0,
            server_id="unknown",
            returner_id="unknown",
            surface="HARD",
            serve_number=1,
            match_format=match_format,
        )
        yield StreamPointEvent(
            event_type="error",
            match_id=match_id,
            point_index=0,
            point_context=fallback_ctx,
            error_message=f"Failed to load match records for [{match_id}]: {e}",
        )
        return

    # Process points sequentially
    effective_format = infer_match_format(records, match_format)
    for point_idx, record in enumerate(records):
        point_context: PointContext | None = None
        try:
            point_context = record.to_point_context(
                point_index=point_idx, match_format=effective_format
            )
            initial_state = PulseGraphState(point_context=point_context)

            # Invoke graph deterministically per point (D-2)
            resolved = await active_graph.ainvoke(initial_state)

            if isinstance(resolved, PulseGraphState):
                leverage_res = resolved.leverage_result
                pressure_res = resolved.pressure_result
                exploit_res = resolved.exploit_result
                tactical_out = resolved.tactical_output
                decision_log = resolved.decision_log
            elif isinstance(resolved, dict):
                leverage_res = resolved.get("leverage_result")
                pressure_res = resolved.get("pressure_result")
                exploit_res = resolved.get("exploit_result")
                tactical_out = resolved.get("tactical_output")
                decision_log = resolved.get("decision_log", [])
            else:
                raise PersistenceException(f"Unexpected graph output type: {type(resolved)}")

            # Persist point event audit trail (D-4)
            await persist_point_event(
                match_id=match_id,
                point_index=point_idx,
                decision_log=decision_log,
                tactical_output=tactical_out,
                db_path=db_path,
            )

            event = StreamPointEvent(
                event_type="point",
                match_id=match_id,
                point_index=point_idx,
                point_context=point_context,
                tactical_output=tactical_out,
                leverage_result=leverage_res,
                pressure_result=pressure_res,
                exploit_result=exploit_res,
                decision_log=decision_log,
            )

            if delay > 0.0:
                await asyncio.sleep(delay)

            yield event

        except Exception as e:
            # Fail-loud mid-stream error handling (D-13)
            logger.error(
                "Mid-stream processing exception at point %d in match [%s]: %s",
                point_idx,
                match_id,
                e,
            )
            error_ctx = point_context or PointContext(
                match_id=match_id,
                point_index=point_idx,
                server_id=record.server,
                returner_id=record.returner,
                surface=record.surface.value,
                serve_number=record.serve_number,
                match_format=match_format,
            )
            yield StreamPointEvent(
                event_type="error",
                match_id=match_id,
                point_index=point_idx,
                point_context=error_ctx,
                error_message=f"Mid-stream execution error at point index {point_idx}: {e}",
            )
            return


def run_cli() -> None:
    """CLI entrypoint for replaying historical matches point-by-point (PULSE simulator)."""
    import argparse
    import io

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="simulator.replay",
        description="PULSE Historical Match Replay Simulator CLI",
    )
    parser.add_argument(
        "--match-id",
        type=str,
        default=None,
        help="Match ID to replay from points dataset",
    )
    parser.add_argument(
        "--speed-multiplier",
        type=float,
        default=1.0,
        help="Playback speed multiplier (0 for instant replay)",
    )
    parser.add_argument(
        "--match-format",
        type=str,
        choices=["bo3", "bo5"],
        default="bo3",
        help="Match scoring format ('bo3' or 'bo5', default 'bo3')",
    )
    parser.add_argument(
        "--list-matches",
        action="store_true",
        help="List available match IDs and exit",
    )
    args = parser.parse_args()

    if args.list_matches:
        matches = get_available_matches()
        sys.stdout.write(f"Available matches ({len(matches)}):\n")
        for m in matches[:20]:
            sys.stdout.write(f"  - {m}\n")
        if len(matches) > 20:
            sys.stdout.write(f"  ... and {len(matches) - 20} more.\n")
        return

    if not args.match_id:
        parser.print_help()
        sys.exit(1)

    async def _run() -> int:
        point_count = 0
        error_encountered = False
        async for event in generate_point_events(
            match_id=args.match_id,
            speed_multiplier=args.speed_multiplier,
            match_format=args.match_format,
        ):
            sys.stdout.write(event.model_dump_json(indent=2) + "\n")
            point_count += 1
            if event.event_type == "error":
                error_encountered = True

        logger.info(
            "Replay CLI completed for match [%s]: %d events processed.",
            args.match_id,
            point_count,
        )
        return 1 if error_encountered else 0

    exit_code = asyncio.run(_run())
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    run_cli()
