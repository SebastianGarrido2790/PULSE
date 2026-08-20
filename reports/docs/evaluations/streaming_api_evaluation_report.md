# Phase 6 — API & Streaming Interface: Architecture & Evaluation Report

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Component:** Phase 6 — API & Streaming Interface (`src/api/`, `src/simulator/`, `src/utils/persistence.py`)  
**Status:** Complete, Validated (ADR-012, D-1 through D-13)  
**Date:** 2026-08-19  

---

## 1. Executive Summary

Phase 6 delivers PULSE's real-time streaming infrastructure and historical match replay simulation engine. It exposes the in-process LangGraph orchestration core, closed-form Markov leverage solver, and game-theoretic minimax exploit module to external consumers (coaching dashboards, analyst workstations, and broadcast overlays) via standardized Server-Sent Events (SSE) and WebSocket transports.

In accordance with PULSE's core philosophy ("deterministic math is ground truth; the agent is a thin layer on top of it"), the streaming interface operates as a **zero-disk-I/O in-process streaming pipeline** capable of processing and streaming points in $<1\text{ms}$ with full audit traceability to SQLite.

### Key Architectural Highlights:
1. **Unified Event Generator & Thin Transport Adapters (D-1):** A single async generator (`generate_point_events()`) in `src/simulator/replay.py` produces the authoritative sequence of point events. The SSE route (`/v1/matches/{match_id}/stream`) and WebSocket route (`/v1/matches/{match_id}/ws`) act as lightweight transport formatters with bit-exact payload parity.
2. **Process-Startup Lifespan Graph Loading (D-12):** The FastAPI `lifespan` context manager compiles `build_pulse_graph()` once at startup onto `app.state.graph`, ensuring no graph rebuilding or disk reads occur per point during live or replayed matches.
3. **Asynchronous SQLite Audit Persistence (D-4):** Implemented `src/utils/persistence.py` with `aiosqlite`, recording `decision_logs` and `tactical_outputs` transactionally to `artifacts/pulse_session.db`, fulfilling Critical requirement FR-12 without event loop blocking.
4. **SSE Keep-Alive Heartbeat (D-5):** Periodic `: keep-alive\n\n` comments fire on a configurable timer (`api.sse_keep_alive_interval_s: 15.0`) during idle replay gaps to prevent proxy drops without polluting `EventSource` message listeners.
5. **Deterministic Replay Cadence (D-6):** Configurable synthetic interval pacing (`simulator.default_interval_s: 2.0` scaled by `--speed-multiplier <n>`, with `0.0` for instant replay), satisfying NFR bit-identical reproducibility under fixed seeds.
6. **Per-Connection Independent Concurrency (D-8):** Purely stateless `CompiledStateGraph.ainvoke()` execution guarantees multi-client concurrent streams run independently with zero shared mutable state.
7. **Fail-Loud Mid-Stream Handling (D-13):** Solver or graph exceptions emit a structured `StreamPointEvent(event_type="error", ...)` and cleanly terminate the connection without skipping points or failing silently.

---

## 2. Architecture & Data Flow

```
                      ┌──────────────────────────────────────────────────────────┐
                      │                     FastAPI Runtime                      │
                      │  lifespan -> build_pulse_graph() -> app.state.graph      │
                      └────────────────────────────┬─────────────────────────────┘
                                                   │
                ┌──────────────────────────────────┴──────────────────────────────────┐
                │                                                                     │
   [SSE Request: GET .../stream]                                         [WS Connection: .../ws]
                │                                                                     │
                ▼                                                                     ▼
      src/api/streaming.py                                                  src/api/streaming.py
     (sse_event_stream adapter)                                            (WebSocket frame adapter)
                │                                                                     │
                └──────────────────────────────────┬──────────────────────────────────┘
                                                   │
                                                   ▼
                                        src/simulator/replay.py
                                     (generate_point_events generator)
                                                   │
                     ┌─────────────────────────────┼─────────────────────────────┐
                     │                             │                             │
                     ▼                             ▼                             ▼
           PointRecord Ingestion         LangGraph StateGraph           SQLite Persistence
         (points.parquet row order)     (graph.ainvoke(PointContext))  (persist_point_event via aiosqlite)
                     │                             │                             │
                     └─────────────────────────────┼─────────────────────────────┘
                                                   │
                                                   ▼
                                       StreamPointEvent Payload
                                  (Yielded to SSE/WS Transport)
```

---

## 3. Wire Contracts & Example Payloads

All public HTTP and streaming contracts are strictly defined in `src/api/schemas.py`.

### 3.1 Point Event Payload (`StreamPointEvent`)

```json
{
  "event_type": "point",
  "match_id": "20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev",
  "point_index": 0,
  "point_context": {
    "match_id": "20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev",
    "point_index": 0,
    "server_id": "Alex De Minaur",
    "returner_id": "Alexander Zverev",
    "surface": "HARD",
    "serve_number": 1,
    "point_score_server": 0,
    "point_score_returner": 0,
    "game_score_server": 0,
    "game_score_returner": 0,
    "set_score_server": 0,
    "set_score_returner": 0,
    "match_format": "bo3"
  },
  "tactical_output": {
    "narrative": "Routine point (ΔL=0.000). No escalation required.",
    "escalated": false,
    "raw_payload": {
      "point_context": { "...": "..." },
      "leverage_result": {
        "delta_leverage": 1.79988e-08,
        "delta_leverage_low": 1.95597e-09,
        "delta_leverage_high": 1.49001e-07,
        "p_hat": 0.707438,
        "sample_size": 3213,
        "fallback_tier": 0
      }
    },
    "is_llm_fallback": false
  },
  "leverage_result": {
    "delta_leverage": 1.79988e-08,
    "delta_leverage_low": 1.95597e-09,
    "delta_leverage_high": 1.49001e-07,
    "p_hat": 0.707438,
    "sample_size": 3213,
    "fallback_tier": 0
  },
  "pressure_result": null,
  "exploit_result": null,
  "decision_log": [
    {
      "node": "pressure_diagnostic",
      "fired": false,
      "reason": "Leverage lower bound 0.0000 < threshold 0.1000 (suppressed)"
    },
    {
      "node": "strategy_exploit",
      "fired": false,
      "reason": "Leverage lower bound 0.0000 < threshold 0.1000 (suppressed)"
    }
  ],
  "error_message": null
}
```

### 3.2 Health Check Payload (`HealthCheckResponse`)

```json
{
  "status": "healthy",
  "graph_ready": true,
  "version": "0.1.0",
  "artifacts_loaded": [
    "stratum_table",
    "pressure_model_artifact",
    "payoff_matrices"
  ]
}
```

### 3.3 Match Metadata Payload (`MatchMetadataResponse`)

```json
{
  "match_id": "20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev",
  "total_points": 207,
  "server_p1": "Alex De Minaur",
  "returner_p2": "Alexander Zverev",
  "surface": "HARD",
  "match_format": "bo3"
}
```

---

## 4. Route Inventory & Transport Table

| HTTP Method / Protocol | Path | Handler | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | `health_check()` | Service health, readiness flag, and loaded artifact keys (D-11). |
| `GET` | `/v1/matches` | `list_available_matches()` | Returns all available match IDs in dataset. |
| `GET` | `/v1/matches/{match_id}` | `get_match_metadata()` | Returns metadata summary (`MatchMetadataResponse`) for UI preflight (D-10). |
| `GET` (SSE) | `/v1/matches/{match_id}/stream` | `stream_match_sse()` | Streams `StreamPointEvent` frames with `: keep-alive\n\n` comments (D-1, D-5). |
| `WebSocket` | `/v1/matches/{match_id}/ws` | `stream_match_ws()` | Bi-directional transport streaming raw JSON event strings (D-1, D-8). |

---

## 5. Replay Simulator CLI Usage

The replay engine is executable via the console script entry point registered in `pyproject.toml`:

```bash
# List available match IDs from the points dataset (3,337 matches)
uv run simulator.replay --list-matches

# Replay a specific match at 5x speed (bo3 default)
uv run simulator.replay --match-id 20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev --speed-multiplier 5.0

# Replay a specific match with bo5 format
uv run simulator.replay --match-id 20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev --match-format bo5

# Instant zero-delay execution (for benchmarks and CI)
uv run simulator.replay --match-id 20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev --speed-multiplier 0
```

---

## 6. Verification & Test Suite Summary

The Phase 6 implementation was validated across unit, integration, and end-to-end evaluation suites:

| Test Module | Test Focus | Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/unit/test_api_schemas.py` | Pydantic wire models, JSON schema validation, score bounds | 6 | 🟢 PASSED |
| `tests/unit/test_point_record_conversion.py` | `PointRecord.to_point_context()`, score flip logic, bo3 & bo5 scope | 5 | 🟢 PASSED |
| `tests/unit/test_persistence.py` | SQLite table initialization, async writes, query helpers | 3 | 🟢 PASSED |
| `tests/unit/test_api_main.py` | Lifespan context manager, graph compilation, health check endpoint | 2 | 🟢 PASSED |
| `tests/unit/test_streaming.py` | SSE formatting, keep-alive heartbeat, slow generator survival, metadata route, MatchReplayRequest validation, bo5 parameter propagation, error bubbling, uninitialized graph, WS frames | 14 | 🟢 PASSED |
| `tests/unit/test_replay_generator.py` | Generator cadence, bo5 propagation, fallback context format, fail-loud exceptions, CLI options | 10 | 🟢 PASSED |
| `tests/integration/test_api_streaming.py` | Full SSE & WS parity, SQLite audit verification, forced mid-stream failure | 3 | 🟢 PASSED |
| **Existing Phase 1–5 Test Suites** | Deterministic solver, ML layer, LangGraph, game theory minimax | 103 | 🟢 PASSED |
| **Total Test Suite** | **Comprehensive Full Repository Verification** | **146** | 🟢 **146/146 (100%, 0 warnings)** |

### Literal Code Coverage Breakdown (`pytest --cov=src`):
- **Total Codebase Coverage:** **91%** (1,663 statements, 153 missed — exceeding ≥70% requirement).
- `src/api/main.py`: **90%** (42 statements, 4 missed)
- `src/api/schemas.py`: **100%** (31 statements, 0 missed)
- `src/api/streaming.py`: **89%** (84 statements, 9 missed)
- `src/simulator/replay.py`: **88%** (123 statements, 15 missed)
- `src/utils/persistence.py`: **87%** (104 statements, 14 missed)
- `src/schemas/point_record.py`: **96%** (107 statements, 4 missed)
- `src/config/loader.py`: **99%** (89 statements, 1 missed)

---

## 7. Exit Criteria Sign-Off Table

| Exit Criterion | Target / Requirement | Implemented Result | Status |
| :--- | :--- | :--- | :---: |
| **SSE Streaming Route** | Real-time point streaming with keep-alive | `GET /v1/matches/{id}/stream` with `: keep-alive\n\n` comments | 🟢 **PASSED** |
| **WebSocket Streaming Route** | Real-time bidirectional transport fallback | `/v1/matches/{id}/ws` with bit-exact SSE payload parity | 🟢 **PASSED** |
| **Match Metadata Route** | Preflight match metadata resolution | `GET /v1/matches/{id}` returning `MatchMetadataResponse` | 🟢 **PASSED** |
| **Wire Contract Model Binding** | Structured query validation | `Annotated[MatchReplayRequest, Query()]` with bo3/bo5 parameterization | 🟢 **PASSED** |
| **Replay Simulator CLI** | Replay match with configurable speed | `uv run simulator.replay --match-id <id> --speed-multiplier <n> --match-format <bo3\|bo5>` | 🟢 **PASSED** |
| **Lifespan Startup Graph** | Zero graph compilation disk I/O per point | Graph built once in `lifespan` and stored on `app.state.graph` | 🟢 **PASSED** |
| **SQLite Audit Persistence** | FR-12 escalation log traceability | `aiosqlite` transactional persistence to `artifacts/pulse_session.db` | 🟢 **PASSED** |
| **Fail-Loud Mid-Stream Handling** | D-13 error transparency | Emits `event_type="error"` on solver/graph failure & halts stream | 🟢 **PASSED** |
| **Test Suite Passing Rate** | 100% test pass rate | 146 / 146 tests passed (0 warnings) | 🟢 **PASSED** |
| **Code Coverage** | $\ge 70\%$ source coverage | 91% total source coverage | 🟢 **PASSED** |
| **Type Check & Linting** | Strict Pyright & Ruff compliance | 0 pyright errors, 0 ruff errors, all files < 1,000 lines | 🟢 **PASSED** |


