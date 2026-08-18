# Phase 6 — Execution Workflow
**API & Streaming Interface — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 6 of 7 | **Version:** 1.0.0 | **Date:** 2026-08-17
**Status:** 🟡 Ready to execute — no code written yet
**Authority:** `phase6_implementation_plan_and_decisions.md` v1.0.0 (D-1–D-13, all approved)
**Scope of this document:** sequencing only, no code.

---

## How to Read This

11 stages (0–10), strictly ordered. Steps numbered continuously (1–39) so any step is unambiguously referenceable. Each step is tagged with the decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

---

## Stage 0 — Pre-Implementation Verification & Dependency Check

1. Confirm `src/api/`, `src/simulator/`, and `src/utils/persistence.py` don't yet exist — no Phase 6 file has been created.
2. Confirm `fastapi` is present in `pyproject.toml` (Phase 1 baseline); confirm `uvicorn` (the ASGI server actually needed to run the app) and `websockets` (needed for FastAPI's native WebSocket support) are present — add either if missing.
3. **Resolve the sync-vs-async SQLite driver question now, since D-4 didn't specify it.** Writing to SQLite synchronously inside an async event generator would block the event loop on every escalation event — the same cost that motivated making every graph node `async def` in Phase 4 (D-7a). Recommendation: `aiosqlite`. Confirm it's available; add if missing.
4. Confirm `httpx` (or FastAPI's `TestClient`, which depends on it) is available for Stage 8's integration tests.

**Gate 0:** dependencies confirmed or added; no Phase 6 files exist yet; the SQLite driver choice is settled before Stage 3 needs it.

---

## Stage 1 — Configuration & Schema Foundations

5. Add an `api:` section to `params.yaml`: host, port, `sse_keep_alive_interval_s: 15.0` (D-5), SQLite database path (D-4). **[D-4, D-5]**
6. Add a `simulator:` section to `params.yaml`: `default_interval_s` and a default `speed_multiplier` (D-6). **[D-6]**
7. Extend `src/config/loader.py`'s `Params` with `ApiParams`/`SimulatorParams` Pydantic models for the two new sections, following the exact pattern already used for `LLMParams`/`ThresholdsParams`.
8. Create `src/api/schemas.py` (D-10): `StreamPointEvent`, `MatchReplayRequest`, `MatchMetadataResponse`, `HealthCheckResponse`, per the approved resolution's named contracts. **[D-10]**

**Gate 1:** `Params` loads cleanly with the two new sections; every model in `src/api/schemas.py` passes a standalone Pydantic validation smoke test.

---

## Stage 2 — `PointRecord → PointContext` Conversion

9. Add `PointRecord.to_point_context(point_index: int) -> PointContext` to `schemas/point_record.py` (D-3) — `point_index` supplied explicitly by the caller per D-3b's row-order convention, never derived internally from a string field. **[D-3, D-3b]**
10. Implement the `server_is_p1`-flip logic for games and sets, mirroring the pattern already established by `get_server_score_int()`/`get_returner_score_int()` for point scores.
11. Hardcode `match_format="bo3"` per D-3a's approved, explicitly-disclosed narrow scope — add a docstring/comment stating bo5 matches are out of scope for now, not silently mishandled. **[D-3a]**
12. Write `tests/unit/test_point_record_conversion.py`: correct score/game/set mapping for both `server_is_p1=True` and `False`; confirm `match_format` is always `"bo3"` today, with the test itself documenting that as a known limitation rather than hiding it.

**Gate 2:** conversion tests pass; a manual spot-check against 2–3 real rows from `points.parquet` confirms scores/games/sets map correctly for both server-identity cases.

---

## Stage 3 — Persistence Layer

13. Create `src/utils/persistence.py`: a minimal SQLite schema (a `decision_log` table and a `tactical_output` table, or one combined table — sized to FR-12's traceability requirement, not over-built) using `aiosqlite` (Stage 0, step 3). **[D-4]**
14. Implement `init_db()` (creates tables if missing; called once at FastAPI startup) and `persist_point_event(match_id, point_index, decision_log, tactical_output)` (one async write per point).
15. Write `tests/unit/test_persistence.py`: a write followed by a read round-trips correctly; `init_db()` is idempotent against an existing database.

**Gate 3:** persistence tests pass against a temporary/in-memory SQLite database, not the real `artifacts/` path — tests stay hermetic.

---

## Stage 4 — Shared Event Generator

16. Create `generate_point_events(match_id, speed_multiplier)` as an async generator in `simulator/replay.py` — it's the component that actually drives replay, so it belongs where "replay" logic lives; `api/streaming.py` stays a thin transport-formatting layer, per D-1's own reasoning. **[D-1, D-2]**
17. Inside the generator: read the match's `PointRecord` rows from `points.parquet` in row order (D-3b); convert each via Stage 2's method; call `graph.ainvoke(state)` (D-2) to get the resolved `PulseGraphState`; call Stage 3's `persist_point_event()` (D-4); `await asyncio.sleep()` for the D-6 cadence (base interval ÷ speed multiplier); `yield` a `StreamPointEvent` (Stage 1) per point.
18. Implement mid-stream failure handling (D-13): wrap the per-point graph invocation in a try/except; on any exception, yield an error-flagged event (or raise a typed exception the transport layer catches) and terminate the generator — never swallow-and-continue. **[D-13]**
19. Write `tests/unit/test_replay_generator.py`: a short fixture match runs end-to-end, confirming one `StreamPointEvent` per point in the correct order, and that a forced mid-stream exception produces the expected error event and generator termination, not a silent skip.

**Gate 4:** generator tests pass, including the forced-failure case; a fixture match's point count matches the yielded-event count exactly (accounting for early termination in the failure-path test).

---

## Stage 5 — FastAPI Application & Lifespan

20. Create `src/api/main.py`: the FastAPI app instance and a `lifespan` context manager that calls `build_pulse_graph()` once and Stage 3's `init_db()` once, storing the compiled graph on `app.state.graph`. **[D-12]**
21. Register `GET /health` (D-11) returning process readiness and whatever artifact-version info is realistically and cheaply available — confirm what that actually is before promising specific fields in the response schema. **[D-11]**
22. Confirm the app runs via the established `uv run api.main` convention.

**Gate 5:** `uv run api.main` starts cleanly; `GET /health` returns 200 with the compiled graph confirmed loaded, not a stub response.

---

## Stage 6 — Streaming Routes

23. Create `src/api/streaming.py`: the SSE route (`GET /v1/matches/{match_id}/stream`) consuming Stage 4's generator, formatting each `StreamPointEvent` as an SSE `data:` frame, interleaving the configured heartbeat comment (D-5) on its own independent timer, not tied to point cadence. **[D-1, D-5]**
24. Add the WebSocket route (`/v1/matches/{match_id}/ws`) consuming the *same* generator pattern — confirm during implementation that no event-formatting logic is duplicated between the two routes; they should differ only in framing. **[D-1]**
25. Wire D-8's concurrency model explicitly: confirm by code review, not assumption, that each incoming connection instantiates its own generator call, with no shared/global generator state across connections. **[D-8]**

**Gate 6:** manual smoke test — two concurrent SSE connections to the same `match_id` produce independent, correctly-paced event sequences; the WebSocket route produces the same event content as the SSE route for the same match.

---

## Stage 7 — Replay Simulator CLI

26. Build the CLI entry point in `simulator/replay.py` as a thin driver around Stage 4's generator — confirm no duplication between the "library" generator and the "CLI" entry point; the CLI drives the same generator and prints/logs its output, it doesn't reimplement replay logic. **[D-6, D-9]**
27. Confirm runnable via `uv run simulator.replay --match-id <id> --speed-multiplier <n>`.

**Gate 7:** CLI runs against a real match end-to-end, producing the same event count/content as the API route does for the same `match_id` — a direct cross-check between the two consumers of Stage 4's shared generator.

---

## Stage 8 — Integration Tests

28. Write `tests/integration/test_api_streaming.py` using `TestClient`/`httpx.AsyncClient`: a full SSE stream for a short fixture match, asserting the event sequence matches what Stage 4's generator produces directly, and that persisted SQLite rows (Stage 3) match the streamed events one-to-one.
29. Add a WebSocket integration test against the same fixture, confirming content parity with the SSE test — this is the test that actually proves D-1 was implemented correctly, not just claimed.
30. Add a mid-stream-failure integration test (D-13): force a failure partway through a fixture match; confirm the client receives the error event, the connection closes cleanly, and the failure itself got persisted (Stage 3). **[D-13]**

**Gate 8:** all integration tests pass; SSE/WebSocket content parity confirmed by direct comparison, not "both seem to work."

---

## Stage 9 — Full Phase 6 Verification

31. `uv run ruff check .` and `uv run ruff format --check .` — 0 errors.
32. `uv run pyright` — 0 errors.
33. `python scripts/check_file_size.py` — confirm new files stay under the 1,000-line ceiling.
34. `uv run pytest --cov=src --cov-report=term-missing` — full suite green, coverage ≥70%, with `api/`, `simulator/`, and `utils/persistence.py` checked specifically since they're this phase's entire novel surface area.
35. Manual end-to-end run: start the API, open a real SSE connection to a real match, confirm the event sequence, confirm SQLite rows appear, confirm `GET /health` reports ready.

**Gate 9:** all green; the manual end-to-end run is the actual exit-criteria check — "a full historical match can be streamed end-to-end... SSE and WebSocket both verified."

---

## Stage 10 — ADR Logging & Documentation Closeout

36. Log a new ADR (e.g., ADR-012, continuing the ADR-010/ADR-011 numbering) into `system_design.md`, scoped to the decisions with real, lasting architectural weight — not every 🟢-recorded item:
    - **D-1** — shared async event generator with thin SSE/WebSocket transport adapters, not two independent implementations.
    - **D-4** — SQLite persistence layer for escalation-log traceability (FR-12), including the `aiosqlite` driver choice and why (event-loop blocking risk).
    - **D-6** — synthetic, deterministic replay cadence rather than reconstructed historical timing, and why (no real inter-point timestamps in the data; reproducibility NFR favors synthetic anyway).
    - **D-13** — fail-loud mid-stream error handling (explicit error event + connection close, never skip-and-continue) and the local-observability-for-now / Grafana-deferred call.
    Logged as a new dated entry, not a silent edit — the same convention `ADR-010 Amendment 1` and `ADR-011` already established.
37. Write a Phase 6 evaluation report mirroring the established pattern (`langgraph_orchestration_report.md`, `game_theory_report.md`): architecture summary, example `StreamPointEvent` payloads, verification results, exit-criteria sign-off table.
38. Update `technical_roadmap.md`'s Phase 6 entry to ✅ Complete.
39. Update `params.yaml`'s inline comments and any quickstart/README documentation referencing how to run the API and replay simulator — these become real, runnable commands for the first time in the project's history.

**Gate 10 (final):** ADR logged as a new dated entry; evaluation report complete; roadmap updated.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify + resolve driver choice) → Stage 1 (config + schemas) → Stage 2 (PointRecord conversion)
   → Stage 3 (persistence) → Stage 4 (shared event generator)
   → Stage 5 (FastAPI app + lifespan) → Stage 6 (streaming routes) → Stage 7 (replay CLI)
   → Stage 8 (integration tests) → Stage 9 (full verification) → Stage 10 (ADR + docs)
```

39 steps, 11 gates. No implementation starts until Stage 0's Gate passes.
