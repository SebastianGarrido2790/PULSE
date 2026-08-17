# Phase 6 — Implementation Plan & Decisions
**API & Streaming Interface**

**Product:** PULSE | **Phase:** 6 of 7 | **Version:** 0.1.0 (Draft — Pending Approval) | **Date:** 2026-08-17
**Status:** 🟡 Planning — no code written
**Authority:** `technical_roadmap.md` (Phase 6), `prd.md` (FR-9, FR-11, FR-12, NFR Reproducibility/Observability), `system_design.md` (ADR ledger)
**Approval required from:** Sebastian, before any implementation begins

---

## 0. How to Read This Document

Same conventions as the Phase 4 and Phase 5 decisions documents:

- **Section 1** is the mandatory current-state audit. It drives Section 2.
- **Section 2** holds one entry per decision, tagged 🔴 **Decision required** (a real fork exists) or 🟢 **No input required** (constraints leave one defensible option, recorded for traceability only).
- Sub-decisions are nested under the primary decision they branch from.

---

## 1. Current State Audit

### 1.1 Phase 6 Deliverable Files

| File | Status | Notes |
|---|---|---|
| `src/api/main.py` | Does not exist. Phase 6 scope. | FastAPI app instance, startup, must be runnable via the project's established `uv run api.main` command convention. |
| `src/api/streaming.py` | Does not exist. Phase 6 scope. | SSE/WebSocket route handlers for `/v1/matches/{match_id}/stream`. |
| `src/simulator/replay.py` | Does not exist. Phase 6 scope. | Historical-match replay, runnable via `uv run simulator.replay --match-id <id>`. |
| API request/response Pydantic schemas | Not yet located anywhere. | Neither `src/schemas/point_record.py` (domain/ingestion) nor `src/graph/state.py` (internal graph state) is the right home for HTTP-facing contracts — no existing file fits. → **D-10**. |

### 1.2 Upstream Dependencies (Already Built, Not In Scope, Treated as Stable Contracts)

`src/graph/pulse_graph.py::build_pulse_graph()` — returns a `CompiledStateGraph`, loads all artifacts once at construction time (established since Phase 4). `src/graph/state.py::PulseGraphState`, `PointContext`, `TacticalOutputResult` — the per-point input/output contracts the graph already exposes. `src/schemas/point_record.py::PointRecord` — the source format read from `artifacts/validated_data/points.parquet`. All ✅ complete; not reopened here except where noted below.

### 1.3 Findings

**Finding A — no `PointRecord → PointContext` conversion exists yet, and there's an established precedent for where it should live.**
The graph consumes `PointContext`; the replay data is `PointRecord`. Nothing converts one to the other today. The project already has a precedent for exactly this kind of conversion: `PointContext.to_match_state()` lives *on the source type* (`PointContext`, in `graph/state.py`), converting itself into the destination (`MatchState`) — not the other way around. → **D-3**.

**Finding B — the roadmap's task list and the stack's own persistence commitment disagree on whether escalation-log persistence is in scope this phase.**
`AGENTS.md`'s stack section commits to "SQLite for session-level escalation logs during development" — but Phase 6's task list (FastAPI app, streaming, replay simulator, request/response schemas) never mentions writing to it. Meanwhile `prd.md` FR-12 — **Critical** priority, not just High — requires "every numeric output is traceable to a persisted, versioned artifact." If Phase 6 ships without ever calling into SQLite, that's not a deferred nice-to-have; it's a Critical-priority functional requirement going unsatisfied by the phase whose entire job is producing the events FR-12 is about. → **D-4**.

**Finding C — "real-time cadence" may not be reproducible from the actual data, and the project's own reproducibility requirement points the other way anyway.**
`prd.md`'s NFR table requires "full replay bit-identical under a fixed seed." Historical point-by-point charting data (the Match Charting Project format this project ingests) is not evidenced anywhere in this conversation to carry real inter-point wall-clock timestamps — points are sequenced, not timed. Trying to reconstruct "real-time" gaps from data that likely doesn't have them would also work against the bit-identical-under-a-fixed-seed requirement, which is far more naturally satisfied by a synthetic, parameterized, deterministic cadence. → **D-6**, the central finding of this document.

**Finding D — an explicitly deferred decision from the stack section lands in this phase.**
`AGENTS.md`'s observability line reads "dashboard TBD (local/Grafana), decided at Phase 6" — not a gap I'm inferring, a decision the project already flagged as belonging here. → **D-... (see D-13, folded into the observability decision)**.

### 1.4 Configuration State

`params.yaml` has no Phase 6 keys yet: no replay cadence/speed-multiplier default, no SSE heartbeat interval, no API host/port. New keys needed pending D-5, D-6.

---

## 2. Decisions

### D-1 🔴 SSE vs. WebSocket — What "Fallback" Actually Means Here

**Context:** the roadmap says "SSE and WebSocket fallback." This event stream is unidirectional (server → client only; nothing in the domain requires the client to send messages back mid-stream), which is exactly SSE's native shape and more than WebSocket's bidirectional model actually needs.

| Option | Description | Trade-off |
|---|---|---|
| **A — Two fully independent implementations** | Separate route handlers for SSE and WebSocket, each with its own event-formatting and connection-lifecycle logic. | Duplicates logic across two code paths for the same underlying event sequence — a bug fix or schema change has to be made twice. |
| **B — One shared async event generator, two thin transport adapters** | A single internal generator produces the sequence of per-point events (driven by the replay simulator + graph); the SSE route and the WebSocket route each just consume that generator and format it for their transport. | One source of truth for the event sequence; each adapter is a few lines of formatting/framing code, not a parallel implementation. |

**Recommendation: Option B.** SSE is the natural primary transport for this domain (simpler, HTTP-native, browsers auto-reconnect via `EventSource`); WebSocket exists here as a compatibility option for clients that need it, not because the domain needs bidirectional messaging. Sharing one generator keeps that asymmetry honest instead of building two equally-weighted implementations for a stream that's only ever supposed to flow one direction.

---

### D-2 🔴 Graph Invocation Pattern — `ainvoke()` Per Point vs. `astream()` Exposing Node-Level Events

**Context:** LangGraph's compiled graph supports both a single-call `ainvoke()` (returns final state) and `astream()` (yields an event per node execution within a single graph run). The roadmap's stated granularity is per-*point* streaming, not per-*node-within-a-point* streaming.

| Option | Mechanism | Trade-off |
|---|---|---|
| **A — `ainvoke()` per point** | The replay loop calls `graph.ainvoke(state)` once per point, gets back the fully-resolved `PulseGraphState`, and the API streams `tactical_output` (plus whatever else is needed) as one event per point. | Matches the stated requirement exactly; keeps the public API contract limited to point-level outcomes, not internal graph topology. |
| **B — `astream()` exposing per-node events** | Each point's graph run streams its own internal node-by-node execution as sub-events to the client. | Leaks internal implementation detail (which nodes exist, their names, their firing order) into a public-facing contract that never asked for it — and doubles the event vocabulary the API has to document and version. |

**Recommendation: Option A.** Nothing in the roadmap, `prd.md`, or the graph's own design asks for node-level visibility over the wire; `decision_log` already exists inside the resolved state for anyone who needs the fire/suppress detail, without exposing it as a separate streaming concern.

---

### D-3 🔴 `PointRecord → PointContext` Conversion — Location

**Context:** Finding A. Nothing converts today. `point_record.py` has now been reviewed directly, in full — it confirms the conversion is mechanical (`get_server_score_int()`/`get_returner_score_int()` already exist for scores; games and sets need the identical `server_is_p1`-flip logic, not yet written anywhere), and surfaces two real sub-decisions the conversion function has to resolve, not just implement.

| Option | Description | Trade-off |
|---|---|---|
| **A — `PointRecord.to_point_context()`, added to `schemas/point_record.py`** | Follows the exact precedent `PointContext.to_match_state()` already set — the conversion method lives on the source type. | Requires reopening a Phase 2 file for a small, additive, non-breaking method — not a redesign. |
| **B — standalone function in `simulator/replay.py`** | Keeps Phase 6 self-contained; touches nothing outside its own scope. | Breaks the established "conversion lives on the source type" pattern for no reason other than avoiding a one-method addition to a stable file. |

**Recommendation: Option A**, for precedent-consistency — this is the same reasoning that put the pressure-deviation lookup accessor in `models/pressure_deviation.py` rather than inline in a Phase 4 node, and the payoff-matrix accessor pattern in Phase 5: shared conversion logic belongs with the type that owns it, not wherever it happens to be needed first.

**D-3a 🔴 — `match_format` (bo3/bo5) has no reliable source on `PointRecord`.** `PointContext.match_format` is `Literal["bo3", "bo5"]`, defaulting to `"bo3"` if not supplied. `PointRecord` has no such field — the closest candidate is `tournament_level: str | None`, which is explicitly optional/nullable and not documented anywhere as a controlled vocabulary the conversion could reliably map to bo3/bo5 (e.g., "does 'Grand Slam' always mean men's bo5, and what about women's matches at the same tournament level, which are bo3?"). Left unresolved, every replayed match would silently default to `"bo3"`, which would compute genuinely wrong leverage numbers for any bo5 match — not a crash, not a suppressed signal, a **confidently wrong number**, which is the one failure mode this project's Sufficiency Gate philosophy exists to prevent. Options: **(A)** infer from `tournament_level` with an explicit, documented mapping and a loud warning (not a silent default) when a record's `tournament_level` doesn't match anything in that mapping; **(B)** accept the `"bo3"` default explicitly, but only for a documented, narrow demo scope (e.g., replay is only offered for known-bo3 matches until this is resolved properly), rather than letting it apply silently to every match including bo5 ones. **Recommendation: Option B for now, explicitly scoped and disclosed** — a real mapping from `tournament_level` strings to match format needs source-data investigation this document can't do, and a disclosed narrow scope is honest; a silent default across all matches is not.

**D-3b 🟢 — `point_index` derivation.** `PointContext.point_index` needs a 0-indexed integer; `PointRecord` has no such field, only a string `point_id`. Recommendation: derive it from row order within the match's slice of `points.parquet` (grouped by `match_id`), not by parsing `point_id`'s string suffix — row order is a structural property of the ingested data, while string-parsing a suffix pattern is fragile against any future change in how `point_id` is formatted upstream. Recorded for completeness; worth one quick sanity check during implementation that ingestion actually preserves chronological row order per match (very likely, but cheap to confirm once rather than assume).

---

### D-4 🔴 Escalation-Log Persistence — Build Now or Defer

**Context:** Finding B. This is the strongest-evidenced decision in this document — FR-12 is Critical priority, not a soft target.

| Option | Description | Trade-off |
|---|---|---|
| **A — Build minimal SQLite persistence this phase** | Every `decision_log` entry (and the resolved `tactical_output`) gets written to SQLite as it's produced, alongside being streamed to the client. Matches the stack's own stated choice; satisfies FR-12 for the first time anywhere in the project. | Adds a small new component (a SQLite writer) to a phase that's already building three new files — a real but contained scope addition. |
| **B — Defer explicitly to Phase 7** | Phase 6 ships streaming-only, no persistence; the roadmap gets formally amended to move this task to Phase 7 (Observability, CI/CD, Shadow-Mode Acceptance), same as Finding A/B got formally reconciled after Phase 4. | Leaves FR-12 — Critical priority — unsatisfied through the one phase whose entire job is producing the events FR-12 is about, and through however long Phase 7 takes to start. |

**Recommendation: Option A.** FR-12's Critical priority is hard to read as anything other than "this needs to exist before the phase that generates these events is considered done," and the stack section didn't mention SQLite speculatively — it committed to it. If Option B is preferred anyway, it should be a deliberate, recorded trade-off against a Critical requirement, not a silent gap.

---

### D-5 🔴 SSE Heartbeat / Keep-Alive Strategy

**Context:** long-lived SSE connections behind proxies or load balancers can be silently dropped without periodic traffic. Routine points (the majority, by design — zero LLM calls, near-instant resolution) could leave long gaps between meaningful events during a slow-cadence replay.

| Option | Description | Trade-off |
|---|---|---|
| **A — Periodic SSE comment heartbeat** | Emit a `: keep-alive\n\n` comment line on a fixed interval (new `params.yaml` key) regardless of whether a real point event is due. | Standard, low-cost SSE pattern; keeps intermediary connections alive without polluting the actual event stream (comments are invisible to `EventSource` listeners). |
| **B — No heartbeat; rely on point cadence alone** | Assume points arrive often enough to keep the connection alive. | Fragile — breaks exactly when it matters least conveniently (a slow-cadence replay, or a real future live feed with genuine between-point gaps), and silently, since a dropped idle connection doesn't necessarily surface as an error until the next real event fails to arrive. |

**Recommendation: Option A.** Cheap, standard, and removes a failure mode that would otherwise depend on how fast the replay happens to be configured.

---

### D-6 🔴 Replay Cadence & Speed-Multiplier Semantics

**Context:** Finding C — the central finding of this document. The roadmap's "real-time cadence" and "configurable speed multiplier" language reads as if it's reproducing actual historical timing, but that timing likely doesn't exist in the source data, and the project's own reproducibility requirement (bit-identical under a fixed seed) points toward a synthetic model regardless.

| Option | Description | Trade-off |
|---|---|---|
| **A — Reconstruct real historical inter-point timing, if present in the data** | Use actual timestamps between points, scaled by the speed multiplier. | Contingent on data that, on current evidence, likely doesn't exist at this granularity in the ingested charting format — a VERIFY this document can't resolve without checking `point_record.py`'s actual fields. |
| **B — Synthetic, fixed, configurable interval per point** | Emit each point after a fixed delay (a new `params.yaml` default, e.g. `replay_default_interval_s`), multiplied by the speed multiplier for faster/slower playback. Same interval regardless of what "really" happened between those two points historically. | Fully deterministic and trivially reproducible — directly satisfies the bit-identical-under-a-fixed-seed NFR, since there's no real-world timing variability to reproduce inconsistently in the first place. "Real-time cadence" becomes "a plausible, configurable playback pace," not a literal historical reconstruction — a real, visible narrowing of what the roadmap's wording implies. |

**Recommendation: Option B**, unless a VERIFY against `point_record.py`'s actual fields turns up real inter-point timestamps — in which case this decision should be revisited, not assumed. Flagged as the first thing to check before implementation, the same way Phase 5's D-1 was.

---

### D-7 🟢 No Authentication on the Streaming Endpoint

Nothing in `prd.md`, the roadmap, or the stack's secrets handling implies an auth requirement for this endpoint — PULSE at this stage is a local/advisory demo tool with no live data feed (explicitly out of scope) and no multi-tenant concern. Recorded for completeness; revisit if a real deployment target with external users is ever scoped.

---

### D-8 🔴 Concurrency Model — Per-Connection Independent Replay vs. Shared Broadcast

**Context:** can multiple clients watch the same match simultaneously, or open different matches at once?

| Option | Description | Trade-off |
|---|---|---|
| **A — Each connection drives its own independent replay generator** | A new SSE/WS connection starts its own point-by-point walk through the requested match from the beginning, independent of any other connection. | Simple, and matches how the compiled graph already behaves — `.ainvoke()` takes a fresh state per call with no shared mutable state, so nothing about the existing architecture needs to change. Two clients watching the same match just get two independent, identically-paced walks through it. |
| **B — One shared background task per match, broadcasting to all subscribers** | A single replay runs per active match; multiple connections subscribe to the same feed and see the same point at the same time. | Only matters if simultaneous shared viewing of one live run is an actual requirement — it isn't stated anywhere in this phase's scope — and adds real complexity (subscriber management, backpressure, one client's slow consumption affecting others) for a feature nobody asked for yet. |

**Recommendation: Option A.** Nothing currently requires shared viewing; building for it now is scope the roadmap doesn't ask for.

---

### D-9 🟢 `main.py` / `streaming.py` Responsibility Split

The roadmap's own deliverables list already fixes this: `api/main.py` owns the FastAPI app instance and startup; `api/streaming.py` owns the route handlers. Recorded for completeness — there's no real second way to divide two files whose names and roles are already specified.

---

### D-10 🔴 Where API Request/Response Schemas Live

**Context:** per 1.1, no existing location fits.

| Option | Description | Trade-off |
|---|---|---|
| **A — New `src/api/schemas.py`** | HTTP-facing request/response models live alongside the API layer that defines them. | Mirrors the precedent `graph/state.py` already set — each layer owns its own schema file rather than overloading `schemas/`, which was scoped for domain/ingestion contracts. |
| **B — Extend `src/schemas/`** | Add API models to the existing schemas package. | Blurs a package that's meant to be about domain data contracts (`PointRecord`) with a different concern (HTTP wire contracts) that happens to also use Pydantic. |

**Recommendation: Option A**, for the same reasons `graph/state.py` exists as its own file rather than folding `PulseGraphState` into `schemas/`.

---

### D-11 🟢 Health-Check Endpoint

Not in the roadmap's task list, but effectively required by the project's own `docker compose up --build` command and standard container-orchestration practice. A minimal `GET /health` returning process/graph-readiness status. Recorded for completeness.

---

### D-12 🟢 Graph Construction Lifecycle Within FastAPI

`build_pulse_graph()` is called exactly once, at FastAPI startup (via a `lifespan` context manager, the current FastAPI convention), and the compiled graph is stored on `app.state` — never rebuilt per-request. This is forced by the same "load once, at construction time" principle established in Phase 4 (D-9) for every artifact this graph depends on; rebuilding per-request would reload `StratumTable`, `PressureModelArtifact`, and the payoff-matrix artifact on every single connection. Recorded for completeness.

---

### D-13 🔴 Mid-Stream Failure Handling & the Deferred Observability-Dashboard Decision

**Context:** two related items land here — Finding D (the explicitly-deferred dashboard choice) and how "fail loud" (an established project invariant) actually behaves inside a long-lived connection, which is genuinely ambiguous in a way it isn't for a single request/response call.

**Mid-stream failure — options:**

| Option | Description | Trade-off |
|---|---|---|
| **A — Per-connection error event, then close** | If the solver or any node raises mid-replay, emit an explicit SSE `event: error` (or WS equivalent) with the failure detail, then close that one connection. Other connections and the service itself are unaffected. | Matches "fail loud" — the client is told honestly that something broke, not left hanging or silently skipped past — without letting one bad point take down the whole service, which fail-loud never asked for. |
| **B — Skip the failed point, continue the stream** | Log the error, move to the next point, keep the connection open. | Directly contradicts the fail-loud invariant — this is exactly the "silently defaulted" behavior the project explicitly rules out for deterministic-core failures. |

**Recommendation: Option A.**

**Observability dashboard — deferred decision, now due:**

| Option | Description | Trade-off |
|---|---|---|
| **A — Local (e.g., a lightweight self-hosted view of OTel spans)** | No new external dependency; matches the project's current local/demo-stage footprint. | Less polished, but proportionate to where the project actually is right now. |
| **B — Grafana** | More capable, closer to a real production observability stack. | Real new infrastructure to stand up and maintain for a project that has no live data feed yet and one developer — likely premature. |

**Recommendation: Option A**, deferring Grafana until there's an actual deployment target that justifies it — consistent with how this project has generally sequenced complexity (defer what isn't load-bearing yet, per the same instinct that kept Phase 5's exception handling minimal until real failure modes existed). This is a genuine judgment call, not a forced one — flagged 🔴 for a real decision, not dressed up as inevitable.

---

## 3. Decision Summary

| ID | Title | Status |
|---|---|---|
| D-1 | SSE primary, WebSocket as thin adapter over one shared event generator | 🔴 Pending |
| D-2 | `ainvoke()` per point, not `astream()` node-level events | 🔴 Pending |
| D-3 | `PointRecord.to_point_context()` added to `schemas/point_record.py` | 🔴 Pending |
| D-4 | Build minimal SQLite escalation-log persistence this phase (FR-12 is Critical) | 🔴 Pending |
| D-5 | SSE keep-alive heartbeat, interval in `params.yaml` | 🔴 Pending |
| D-6 | Synthetic fixed-interval replay cadence, not reconstructed real timing | 🔴 Pending — VERIFY data first |
| D-7 | No authentication on the streaming endpoint | 🟢 Recorded |
| D-8 | Per-connection independent replay, not shared broadcast | 🔴 Pending |
| D-9 | `main.py`/`streaming.py` split — already fixed by the roadmap | 🟢 Recorded |
| D-10 | New `src/api/schemas.py` for HTTP contracts | 🔴 Pending |
| D-11 | `GET /health` endpoint | 🟢 Recorded |
| D-12 | Graph built once at FastAPI startup, stored on `app.state` | 🟢 Recorded |
| D-13 | Fail-loud error event + close on mid-stream failure; local dashboard over Grafana for now | 🔴 Pending |

**Before any implementation:** D-6 depends on checking `src/schemas/point_record.py`'s actual fields for real inter-point timestamps — if they exist, D-6 needs to be revisited before Stage 1 of an execution workflow, not assumed away.

No implementation begins until the 🔴 items above are resolved.
