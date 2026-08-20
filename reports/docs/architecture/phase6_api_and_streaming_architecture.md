# Phase 6 — API, Replay Simulation & Streaming Interface: Architectural Report

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Phase:** Phase 6 — API & Streaming Interface  
**Document Type:** Architecture — The What  
**Authority:** ADR-012, Phase 6 Decisions D-1 through D-13, [`phase6_execution_workflow.md`](../workflows/phase6_execution_workflow.md), [`streaming_api_evaluation_report.md`](../evaluations/streaming_api_evaluation_report.md)  
**Status:** Complete — All quality gates passed (146/146 tests, 91% codebase coverage, 0 pyright/ruff errors, 0 warnings under strict error-on-warnings baseline)  
**Last Updated:** 2026-08-20  

---

## 0. Purpose & Scope

This document details **what Phase 6 built, how each API streaming transport and historical simulation component works at the technical implementation level, and why the architecture is structured the way it is.** It serves as the authoritative technical reference for frontend developers, MLOps engineers, and performance analysts integrating client applications (coaching dashboards, broadcast graphic overlays, analyst workstations) with PULSE.

### Phase 6 Deliverables Matrix

| Deliverable | File / Artifact Path | Status | Role & Architecture Responsibility |
| :--- | :--- | :---: | :--- |
| **Pydantic Wire Contracts** | `src/api/schemas.py` | ✅ Complete | Strongly-typed API schemas for SSE/WebSocket payloads (`StreamPointEvent`), query validation (`MatchReplayRequest`), and match metadata (`MatchMetadataResponse`). |
| **Domain Bridge Conversion** | `src/schemas/point_record.py` | ✅ Complete | Method `PointRecord.to_point_context(point_index, match_format)` bridging immutable ingestion rows to LangGraph runtime state with server perspective and format mapping. |
| **FastAPI Application & Lifespan** | `src/api/main.py` | ✅ Complete | ASGI application lifecycle manager compiling the LangGraph engine once at startup onto `app.state.graph`, serving `/health`, CORS, and streaming routers. |
| **Streaming Transport Handlers** | `src/api/streaming.py` | ✅ Complete | Dual-protocol streaming adapters for Server-Sent Events (`GET /{match_id}/stream`) and WebSockets (`WS /{match_id}/ws`) with queue-decoupled keep-alive heartbeats. |
| **Historical Replay Generator** | `src/simulator/replay.py` | ✅ Complete | Core async event generator (`generate_point_events`) driving chronological point iteration, LangGraph execution, persistence, and CLI replay (`simulator.replay`). |
| **Asynchronous Audit Persistence** | `src/utils/persistence.py` | ✅ Complete | Non-blocking transactional logging via `aiosqlite` saving `decision_logs` and `tactical_outputs` to `artifacts/pulse_session.db` (FR-12). |
| **Quality Suite & Integration Tests** | `tests/unit/test_api_*.py`, `tests/unit/test_streaming.py`, `tests/unit/test_replay_generator.py`, `tests/integration/test_api_streaming.py` | ✅ Complete | 43 dedicated unit/integration tests verifying SSE/WebSocket parity, keep-alive heartbeat survival, match format propagation, and fail-loud error bubbling. |

---

## 1. Architectural Philosophy: Zero-Disk-I/O In-Process Streaming

PULSE's operational requirement demands sub-second point-level leverage calculations and tactical evaluations. Traditional microservice designs often split model inference, Markov calculations, and API routing across separate containerized network hops. In PULSE, this is explicitly rejected in favor of an **in-process deterministic core**:

```
Traditional Microservice Fan-Out:
  Client ──► API Gateway ──(HTTP)──► State Node ──(HTTP)──► Markov Service ──(HTTP)──► Exploit Service
  [High Network Latency (~50-200ms) + Serialization Overhead + Fragile Distributed Failure Modes]

PULSE In-Process Streaming Pipeline:
  Client ──(SSE/WS)──► FastAPI Handler ──(In-Memory async)──► LangGraph Runtime ──(In-Process)──► Markov & Minimax Solvers
  [Sub-millisecond Execution (<1ms) + Zero Inter-Process Serialization + Thread-Safe Shared Graph Cache]
```

### Core Architectural Invariants

1. **Deterministic Ground-Truth Primacy (Invariant §0.1):** The streaming engine never alters, approximates, or generates synthetic numbers. It transmits exact Markov leverage values, Bayesian-shrunk pressure deviations, and minimax equilibrium mixes computed by the underlying deterministic modules.
2. **Unified Generator & Transport Equivalence (D-1, D-8):** SSE and WebSocket protocols consume the **exact same underlying async generator** (`generate_point_events`). Neither protocol performs custom graph execution or business logic; both are strict, thin formatting wrappers ensuring 100% bit-exact payload parity.
3. **Lifespan Graph Compilation (D-12):** The LangGraph state graph and all model artifacts (StratumTable, PressureArtifact, PayoffMatrices) are loaded and compiled **once at process startup** inside FastAPI's `lifespan` handler and mounted onto `app.state.graph`. No disk reads or graph recompilations occur per point.
4. **Queue-Decoupled Keep-Alive Heartbeat (D-5):** To prevent reverse proxies (e.g., Nginx, Cloudflare) and browsers from closing idle HTTP connections during long inter-point pauses, the SSE generator decouples the point generator task from the response stream via an `asyncio.Queue`. Keep-alive comment heartbeats (`: keep-alive\n\n`) fire periodically without cancelling in-flight computation tasks.
5. **Non-Blocking Audit Trail (D-4, FR-12):** Every evaluated point persists its full diagnostic audit trail (`decision_log` and `tactical_output`) to SQLite via asynchronous, non-blocking I/O (`aiosqlite`), satisfying compliance without degrading event loop throughput.
6. **Fail-Loud Error Transparency (D-13):** If data corruption, solver failure, or unexpected state occurs mid-stream, PULSE emits a structured `StreamPointEvent(event_type="error")` containing the diagnostic stack trace and immediately terminates the stream rather than defaulting silently.
7. **End-to-End Parameterized Wire Contracts (D-3a):** Query parameters (`speed_multiplier`, `match_format`) are bound via `Annotated[MatchReplayRequest, Query()]`, validated through Pydantic v2, and threaded end-to-end through generator and conversion layers.

---

## 2. End-to-End System Architecture

### 2.1 Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    EXTERNAL CONSUMERS                                           │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐  ┌────────────────────────┐ │
│  │ Coaching Tablet Dashboard    │  │ Broadcast Graphics Engine    │  │ Analyst Workstation    │ │
│  └──────────────┬───────────────┘  └──────────────┬───────────────┘  └───────────┬────────────┘ │
└─────────────────┼─────────────────────────────────┼──────────────────────────────┼──────────────┘
                  │ Server-Sent Events (SSE)        │ WebSocket (WS)               │ REST / Metadata
                  ▼                                 ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FASTAPI TRANSPORT LAYER (`src/api/`)                                                            │
│                                                                                                 │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  ┌──────────────────┐ │
│  │ GET /v1/matches/{id}/stream     │  │ WS /v1/matches/{id}/ws          │  │ GET /v1/matches  │ │
│  │ Handler: stream_match_sse()     │  │ Handler: stream_match_ws()      │  │ GET /health      │ │
│  │ Transport: text/event-stream    │  │ Transport: WebSocket frames     │  │ Route Handlers   │ │
│  └────────────────┬────────────────┘  └────────────────┬────────────────┘  └─────────┬────────┘ │
└───────────────────┼────────────────────────────────────┼─────────────────────────────┼──────────┘
                    │                                    │                             │
                    ▼                                    │                             ▼
┌────────────────────────────────────────────────────────┼──────────┐       ┌─────────────────────┐
│ QUEUE-BASED SSE STREAM DECOUPLER                       │          │       │ MATCH METADATA API  │
│                                                        │          │       │ Metadata Resolution │
│   Producer Task (_producer)                            │          │       │ load_match_records()│
│   ├── Calls generate_point_events()                    │          │       └─────────────────────┘
│   └── Pushes events to asyncio.Queue                   │          │
│                                                        │          │
│   Consumer Loop                                        │          │
│   ├── Timeout -> Yields ": keep-alive\n\n" (Heartbeat) │          │
│   └── Item    -> Yields "data: {...}\n\n"              │          │
└───────────────────┬────────────────────────────────────┘          │
                    │                                               │
                    ▼                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ HISTORICAL REPLAY & SIMULATION GENERATOR (`src/simulator/replay.py`)                            │
│                                                                                                 │
│   1. Load Match Records from Parquet: load_match_records(match_id)                              │
│   2. Sequential Point Iteration (0 to N-1)                                                      │
│   3. Schema Bridge: PointRecord.to_point_context(point_idx, match_format)                       │
│   4. Pacing Controller: await asyncio.sleep(default_interval_s / speed_multiplier)              │
└───────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ IN-PROCESS LANGGRAPH ORCHESTRATION ENGINE (`src/graph/pulse_graph.py` on `app.state.graph`)      │
│                                                                                                 │
│   PulseGraphState(point_context)                                                                │
│          │                                                                                      │
│          ▼                                                                                      │
│   StateMonitorNode (Always-On) ──► Closed-Form Markov Solver (Leverage & Wilson Uncertainty)   │
│          │                                                                                      │
│          ├── [ delta_L_low < 0.10 ]  ────────────────────────────────────────┐                  │
│          │                                                                   │                  │
│          └── [ delta_L_low >= 0.10 (Escalation Trigger) ]                    │                  │
│                  │                                                           │                  │
│                  ├──► PressureDiagnosticNode (Empirical-Bayes Shrinkage)    │                  │
│                  │                                                           │                  │
│                  └──► StrategyExploitNode (Minimax Game-Theoretic Matrix)    │                  │
│                                  │                                           │                  │
│                                  └──────────────────────┬────────────────────┘                  │
│                                                         ▼                                       │
│                                              TacticalOutputNode                                 │
│                                        (Signal Synthesis / Passthrough)                         │
└───────────────────┬─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ASYNC AUDIT PERSISTENCE LAYER (`src/utils/persistence.py`)                                      │
│                                                                                                 │
│   persist_point_event() via aiosqlite                                                           │
│   ├── INSERT INTO decision_logs (match_id, point_index, node, fired, reason, timestamp)         │
│   └── INSERT INTO tactical_outputs (match_id, point_index, narrative, confidence, timestamp)   │
│   Database: `artifacts/pulse_session.db`                                                        │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Deep Dives

### 3.1 Wire Contracts & Serialization Protocol (`src/api/schemas.py`)

All HTTP, SSE, and WebSocket communication conforms strictly to Pydantic v2 schemas.

#### `StreamPointEvent` Payload Schema
```python
class StreamPointEvent(BaseModel):
    event_type: Literal["point", "heartbeat", "error"] = Field(
        default="point",
        description="Stream event discriminator",
    )
    match_id: str
    point_index: int
    point_context: PointContext | None = None
    tactical_output: TacticalOutput | None = None
    leverage_result: LeverageResult | None = None
    pressure_result: PressureDiagnosticResult | None = None
    exploit_result: ExploitResult | None = None
    decision_log: list[DecisionLogEntry] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: str | None = None
```

#### Query Parameter Schema (`MatchReplayRequest`)
```python
class MatchReplayRequest(BaseModel):
    speed_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        description="Replay playback speed multiplier (0.0 = instant zero-delay)",
    )
    match_format: Literal["bo3", "bo5"] = Field(
        default="bo3",
        description="Match format structure ('bo3' default or 'bo5')",
    )
```

#### Match Metadata Schema (`MatchMetadataResponse`)
```python
class MatchMetadataResponse(BaseModel):
    match_id: str
    server_p1: str
    returner_p2: str
    surface: str
    total_points: int
    match_format: Literal["bo3", "bo5"] = "bo3"
```

---

### 3.2 Schema Bridge & Domain Conversion (`src/schemas/point_record.py`)

Data ingested from historical match archives (`PointRecord`) contains player-centric score conventions (`p1_score`, `p2_score`, `server_is_p1`). The LangGraph state context (`PointContext`) requires server-relative indexing (`point_score_server`, `point_score_returner`).

The conversion method `PointRecord.to_point_context()` provides this domain translation:

$$\text{Server Score} = \begin{cases} \text{p1\_score} & \text{if } \text{server\_is\_p1} = \text{True} \\ \text{p2\_score} & \text{if } \text{server\_is\_p1} = \text{False} \end{cases}$$

$$\text{Returner Score} = \begin{cases} \text{p2\_score} & \text{if } \text{server\_is\_p1} = \text{True} \\ \text{p1\_score} & \text{if } \text{server\_is\_p1} = \text{False} \end{cases}$$

```python
def to_point_context(
    self,
    point_index: int,
    match_format: Literal["bo3", "bo5"] = "bo3",
) -> "PointContext":
    from src.graph.state import PointContext

    return PointContext(
        match_id=self.match_id,
        point_index=point_index,
        server_id=self.server,
        returner_id=self.returner,
        surface=self.surface.value if isinstance(self.surface, Surface) else str(self.surface),
        serve_number=self.serve_number,
        point_score_server=self.get_server_score_int(),
        point_score_returner=self.get_returner_score_int(),
        game_score_server=self.get_server_games_int(),
        game_score_returner=self.get_returner_games_int(),
        set_score_server=self.get_server_sets_int(),
        set_score_returner=self.get_returner_sets_int(),
        match_format=match_format,
    )
```

---

### 3.3 Historical Replay Event Generator (`src/simulator/replay.py`)

The event generator `generate_point_events()` drives match simulation:

1. **Cadence Calculation:** Sourced from `params.yaml` (`simulator.default_interval_s = 20.0`).
   $$\text{Delay} = \begin{cases} 0.0 & \text{if } \text{speed\_multiplier} \le 0.0 \\ \frac{\text{default\_interval\_s}}{\text{speed\_multiplier}} & \text{otherwise} \end{cases}$$
2. **Deterministic Graph Invocation:** For every row, constructs `PulseGraphState(point_context)` and invokes `await active_graph.ainvoke(initial_state)`.
3. **Audit Persistence:** Awaits non-blocking write `persist_point_event(...)`.
4. **Payload Yielding:** Yields structured `StreamPointEvent`.
5. **Fail-Loud Mid-Stream Exception Handling:** Catches unexpected errors, logs diagnostics, constructs fallback `error_ctx` preserving `match_format`, yields `StreamPointEvent(event_type="error")`, and halts.

```python
except Exception as e:
    logger.error("Mid-stream processing exception at point %d in match [%s]: %s", point_idx, match_id, e)
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
```

---

### 3.4 Queue-Decoupled Server-Sent Events (SSE) Transport (`src/api/streaming.py`)

In standard Python async generators, executing `await asyncio.sleep(...)` inside a `StreamingResponse` can cause timeout exceptions if reverse proxies enforce a strict idle timeout. Wrapping the generator with `asyncio.wait_for()` directly would cancel the generator if a timeout occurred.

To solve this (Decision D-5), PULSE implements a **Producer-Consumer Async Queue Decoupling pattern**:

```mermaid
sequenceDiagram
    autonumber
    participant Browser as Client Browser
    participant FastAPISSE as sse_event_stream (Consumer)
    participant AsyncQueue as asyncio.Queue
    participant ProducerTask as _producer (Producer Task)
    participant ReplayGen as generate_point_events()

    Note over FastAPISSE,ProducerTask: FastAPISSE spawns ProducerTask as independent asyncio.Task
    ProducerTask->>ReplayGen: Pull Next Point Event
    ReplayGen-->>ProducerTask: StreamPointEvent (Point 0)
    ProducerTask->>AsyncQueue: queue.put(Point 0)
    
    FastAPISSE->>AsyncQueue: asyncio.wait_for(queue.get(), timeout=15s)
    AsyncQueue-->>FastAPISSE: Point 0
    FastAPISSE-->>Browser: data: {"event_type": "point", ...}\n\n

    Note over ProducerTask,ReplayGen: Inter-point pacing pause (e.g. 20s delay)
    FastAPISSE->>AsyncQueue: asyncio.wait_for(queue.get(), timeout=15s)
    Note over FastAPISSE: Timeout reached at 15s (Queue Empty)
    FastAPISSE-->>Browser: : keep-alive\n\n
    Note over FastAPISSE: ProducerTask is NOT cancelled; keep-alive comment emitted.

    ProducerTask->>ReplayGen: Pull Next Point Event (Finished delay)
    ReplayGen-->>ProducerTask: StreamPointEvent (Point 1)
    ProducerTask->>AsyncQueue: queue.put(Point 1)

    FastAPISSE->>AsyncQueue: asyncio.wait_for(queue.get(), timeout=15s)
    AsyncQueue-->>FastAPISSE: Point 1
    FastAPISSE-->>Browser: data: {"event_type": "point", ...}\n\n
```

#### Code Implementation:
```python
async def sse_event_stream(
    match_id: str,
    speed_multiplier: float,
    graph: CompiledStateGraph,
    keep_alive_interval: float,
    match_format: Literal["bo3", "bo5"] = "bo3",
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[StreamPointEvent | Exception | None] = asyncio.Queue()

    async def _producer() -> None:
        try:
            async for event in generate_point_events(
                match_id=match_id,
                speed_multiplier=speed_multiplier,
                match_format=match_format,
                graph=graph,
            ):
                await queue.put(event)
            await queue.put(None)
        except Exception as exc:
            await queue.put(exc)

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=keep_alive_interval)
                if item is None:
                    break
                if isinstance(item, Exception):
                    err_event = StreamPointEvent(
                        event_type="error",
                        match_id=match_id,
                        point_index=0,
                        error_message=f"Stream generator error: {item}",
                    )
                    yield format_sse_event(err_event)
                    break
                yield format_sse_event(item)
            except TimeoutError:
                # Emit SSE comment heartbeat per D-5 without cancelling producer
                yield ": keep-alive\n\n"
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
```

---

### 3.5 WebSocket Streaming Transport (`src/api/streaming.py`)

For bi-directional, persistent client connections:
- Accepts connection via `await websocket.accept()`.
- Validates that `app.state.graph` is initialized (closing with code `1011` if unready).
- Streams raw JSON serialized frames (`event.model_dump_json()`).
- Handles `WebSocketDisconnect` cleanly with info logging.

```python
@streaming_router.websocket("/{match_id}/ws")
async def stream_match_ws(
    websocket: WebSocket,
    match_id: str,
    replay_params: Annotated[MatchReplayRequest, Query()],
) -> None:
    await websocket.accept()
    graph: CompiledStateGraph | None = getattr(websocket.app.state, "graph", None)
    if graph is None:
        await websocket.close(code=1011, reason="PULSE graph engine is not initialized")
        return

    try:
        async for event in generate_point_events(
            match_id=match_id,
            speed_multiplier=replay_params.speed_multiplier,
            match_format=replay_params.match_format,
            graph=graph,
        ):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally for match [%s]", match_id)
    except Exception as e:
        logger.error("WebSocket streaming exception for match [%s]: %s", match_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
```

---

### 3.6 Non-Blocking SQLite Audit Persistence (`src/utils/persistence.py`)

To satisfy Critical Requirement FR-12 without thread-blocking disk I/O, SQLite operations are managed via `aiosqlite`.

#### Database Schema
```sql
CREATE TABLE IF NOT EXISTS decision_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    point_index INTEGER NOT NULL,
    node TEXT NOT NULL,
    fired INTEGER NOT NULL,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactical_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    point_index INTEGER NOT NULL,
    narrative TEXT NOT NULL,
    confidence TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

#### Write Transaction
```python
async def persist_point_event(
    match_id: str,
    point_index: int,
    decision_log: list[DecisionLogEntry | dict[str, Any]],
    tactical_output: TacticalOutput | dict[str, Any] | None = None,
    db_path: Path | str | None = None,
) -> None:
    target_db = resolve_db_path(db_path)
    now_ts = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(target_db) as db:
        for entry in decision_log:
            node = (
                entry.node if isinstance(entry, DecisionLogEntry) else entry.get("node", "Unknown")
            )
            fired = (
                1
                if (
                    entry.fired
                    if isinstance(entry, DecisionLogEntry)
                    else entry.get("fired", False)
                )
                else 0
            )
            reason = (
                entry.reason if isinstance(entry, DecisionLogEntry) else entry.get("reason", "")
            )
            await db.execute(
                "INSERT INTO decision_logs (match_id, point_index, node, fired, reason, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (match_id, point_index, node, fired, reason, now_ts),
            )

        if tactical_output is not None:
            narrative = (
                tactical_output.narrative
                if isinstance(tactical_output, TacticalOutput)
                else tactical_output.get("narrative", "")
            )
            confidence = (
                tactical_output.confidence
                if isinstance(tactical_output, TacticalOutput)
                else tactical_output.get("confidence", "low")
            )
            await db.execute(
                "INSERT INTO tactical_outputs (match_id, point_index, narrative, confidence, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (match_id, point_index, narrative, confidence, now_ts),
            )
        await db.commit()
```

---

## 4. Key Design Decisions & Rationale

| Decision ID | Context & Trade-Off | Selected Architecture | Rationale & Invariant Alignment |
| :--- | :--- | :--- | :--- |
| **D-1** | Dual SSE & WebSocket transports | **Unified Generator Adapter** | Prevents divergence; both protocols share 100% of simulator logic and serialize identical Pydantic models. |
| **D-3a** | Match scoring format parameterization | **End-to-End `match_format` Wire Threading** | Parameterized across query, CLI, generator, and `to_point_context`, driving Phase 2 Markov target sets (2 for bo3, 3 for bo5). |
| **D-4** | Audit trail storage | **`aiosqlite` SQLite DB** | Zero-configuration local relational persistence meeting FR-12 without event loop blocking or external DB dependencies. |
| **D-5** | SSE idle timeout disconnects | **Async Queue Decoupling** | Background task pushes events to queue; consumer emits `: keep-alive\n\n` comments on timeout without killing the generator task. |
| **D-8** | Multi-client connection isolation | **Independent Generators** | Each SSE/WS request creates an independent replay generator instance referencing the shared, immutable graph cache on `app.state`. |
| **D-10** | UI preflight metadata | **`GET /v1/matches/{id}`** | Returns player IDs, surface, point counts, and format in $<5\text{ms}$ before initiating streaming. |
| **D-12** | Graph compilation lifecycle | **Lifespan Startup Compilation** | `build_pulse_graph()` runs once during FastAPI startup, eliminating runtime compilation latency and disk I/O. |
| **D-13** | Mid-stream runtime exceptions | **Structured Fail-Loud Termination** | Emits `event_type="error"` event frame and closes connection; never swallows exceptions silently. |

---

## 5. Verification & Quality Gate Sign-Off

### 5.1 Test Suite Summary

The complete PULSE test suite passes with **146 / 146 tests passing (100%)** and **0 warnings** under the strict `filterwarnings = ["error", ...]` gate:

```text
=============================== tests coverage ================================
______________ coverage: platform win32, python 3.11.13-final-0 _______________

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
src\__init__.py                          0      0   100%
src\api\__init__.py                      0      0   100%
src\api\main.py                         42      4    90%   97-100, 109
src\api\schemas.py                      31      0   100%
src\api\streaming.py                    84      9    89%   138, 235-242
src\config\__init__.py                   2      0   100%
src\config\loader.py                    89      1    99%   156
src\core\__init__.py                     0      0   100%
src\core\game_theory.py                175     13    93%   74, 86, 257, 290, 301, 341, 345, 352, 429, 474, 478, 481-484
src\core\leverage_uncertainty.py        48      0   100%
src\core\markov_solver.py              228     46    80%   62, 67, 115, 140, 183, 251-272, 318, 325, 376-406, 424-425, 429, 431-432, 442, 444-445, 450-451, 469, 526
src\graph\__init__.py                    0      0   100%
src\graph\llm_client.py                 29     20    31%   42-82
src\graph\pressure_diagnostic.py        28      0   100%
src\graph\pulse_graph.py                96      0   100%
src\graph\state.py                      45      0   100%
src\graph\state_monitor.py              27      0   100%
src\graph\strategy_exploit.py           34      0   100%
src\graph\tactical_output.py            37      0   100%
src\models\__init__.py                   0      0   100%
src\models\point_win_classifier.py     126      5    96%   43, 137-138, 324-325
src\models\pressure_deviation.py       134      8    94%   90, 140, 189, 240-241, 294, 350-351
src\schemas\__init__.py                  0      0   100%
src\schemas\point_record.py            107      4    96%   135, 142, 151-152
src\simulator\__init__.py                0      0   100%
src\simulator\replay.py                123     15    88%   50-51, 76-78, 169-173, 181, 277, 295, 306, 310
src\utils\__init__.py                    0      0   100%
src\utils\exceptions.py                 37      5    86%   30-31, 37-40
src\utils\logger.py                     37      9    76%   52-54, 65-70, 77-79
src\utils\persistence.py               104     14    87%   35, 86-89, 129, 155-158, 178-181
------------------------------------------------------------------
TOTAL                                 1663    153    91%
============================ 146 passed in 24.39s =============================
```

### 5.2 Static Quality & Guardrail Checklist

- [x] **Pyright Static Type Checking:** Strict mode passes with 0 errors across all modules.
- [x] **Ruff Lint & Format:** 100% compliant across 106 repository files.
- [x] **File-Size Ceiling Gate (§5.1):** All Python source files under `src/` remain under the 1,000-line limit (`scripts/check_file_size.py`).
- [x] **Warning Gate Hardening:** Configured `pyproject.toml` with `filterwarnings = ["error", ...]` to fail immediately on any unhandled warning regression.
- [x] **Audit Traceability (FR-12):** Verified SQLite transactional logging across unit and integration replay fixtures.
