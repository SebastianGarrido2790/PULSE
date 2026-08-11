# Phase 4 — Event-Driven Orchestration (LangGraph): Architectural Report

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Phase:** Phase 4 — Event-Driven Orchestration (LangGraph)  
**Document Type:** Architecture — The What  
**Authority:** ADR-001, ADR-010, [`phase4_execution_workflow.md`](../workflows/phase4_execution_workflow.md)  
**Status:** Complete — All quality gates passed (67/67 tests, 91% coverage, 0 pyright/ruff errors)  
**Last Updated:** 2026-08-11

---

## 0. Purpose & Scope

This document explains **what Phase 4 built, how each component works at the implementation level, and why the architecture is structured the way it is.** It is intended for coaches, performance analysts, broadcast engineers, and future developers who need to understand the event-driven orchestration layer without reading every line of source code.

**What Phase 4 covers:**

| Deliverable | File | Status |
|---|---|---|
| Pydantic v2 graph state schema & sub-models | `src/graph/state.py` | ✅ Complete |
| Always-on leverage monitor node | `src/graph/state_monitor.py` | ✅ Complete |
| Triggered pressure diagnostic node | `src/graph/pressure_diagnostic.py` | ✅ Complete |
| Triggered exploit stub node (sufficiency gate) | `src/graph/strategy_exploit.py` | ✅ Complete |
| LLM narrative synthesis terminal node | `src/graph/tactical_output.py` | ✅ Complete |
| Anthropic LLM thin wrapper | `src/graph/llm_client.py` | ✅ Complete |
| LangGraph conditional graph definition & compiler | `src/graph/pulse_graph.py` | ✅ Complete |
| DeepEval groundedness evaluation suite | `tests/evals/test_tactical_output_groundedness.py` | ✅ Complete |
| End-to-end integration test suite | `tests/integration/test_conditional_graph.py` | ✅ Complete |

**What Phase 4 does not cover:**

- `core/game_theory.py` minimax equilibrium solver (Phase 5)
- `StrategyExploitNode` full recommendation engine (Phase 5 stub in Phase 4)
- FastAPI streaming API layer (`api/main.py`, Phase 6)
- Historical match replay simulator (`simulator/replay.py`, Phase 6)

---

## 1. Architectural Philosophy: Inverting the Usual LLM-Agent Ratio

Most LLM-agent systems place the language model at the center of decision-making — the LLM determines _what_ to compute, _how_ to route, and _whether_ to escalate. PULSE deliberately inverts this ratio.

```
Traditional Agent:        LLM → decides → calls tools → synthesizes
PULSE Agent:              Math → proves → LLM phrases → human decides
```

The PULSE orchestration graph is built on three principles that flow directly from the project invariants:

1. **Deterministic routing.** Whether to escalate from `StateMonitorNode` to `PressureDiagnosticNode` is a Python inequality check — `delta_leverage_low >= 0.10` — not an LLM judgment call. No LLM ever makes a routing decision.

2. **Conditional topology.** The graph's execution path changes shape with match state. Routine points execute two nodes; high-leverage points execute four. This is not for efficiency — it is for correctness. Emitting a pressure deviation signal on a 0-0, 0-0, 0-0 routine point would violate the Sufficiency Gate invariant regardless of performance.

3. **LLM as a thin narrative layer.** The LLM's only responsibility is to phrase an already-fully-computed, already-validated set of numbers into a coach-readable sentence. It does not compute, approximate, or derive. If it fails, the pre-computed payload is returned directly — the fallback is complete, not degraded.

---

## 2. Full System Architecture Diagram

The diagram below shows every component involved in processing a single point event, end-to-end:

```
Point Event Arrives (PointContext)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  PulseGraphState (Pydantic v2)                        │
│  ┌──────────────────────────────────────────────┐     │
│  │ point_context: PointContext                  │     │
│  │ leverage_result: LeverageResult | None       │     │
│  │ pressure_result: PressureDeviationResult|None│     │
│  │ exploit_result: ExploitResult | None         │     │
│  │ tactical_output: TacticalOutputResult | None │     │
│  │ decision_log: Annotated[list, operator.add]  │     │
│  └──────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  StateMonitorNode (ALWAYS-ON)                         │
│  ┌─────────────────────────────────────────────┐      │
│  │ 1. resolve_point_win_probability()          │      │
│  │    └─ 4-tier stratum fallback → p_hat, N   │      │
│  │ 2. ctx.to_match_state() → MatchState        │      │
│  │ 3. propagate_leverage_uncertainty()         │      │
│  │    └─ Wilson CI [p_low, p_high] →           │      │
│  │       Markov(p_low), Markov(p_high)         │      │
│  │       → [delta_L_low, delta_L_high]         │      │
│  │ 4. LeverageResult construction              │      │
│  │ 5. DecisionLogEntry audit entries           │      │
│  └─────────────────────────────────────────────┘      │
│  Outputs: leverage_result, decision_log               │
└───────────────┬───────────────────────────────────────┘
                │
                ▼
  ┌─────────────────────────────────┐
  │  route_after_state_monitor()    │
  │  delta_leverage_low >= 0.10?    │
  └────────┬──────────────┬─────────┘
  YES (escalate)        NO (suppress)
           │                    │
           ▼                    │
┌──────────────────────┐        │
│ PressureDiagnosticNode│       │
│ (TRIGGERED)          │        │
│ 1. assign_leverage_  │        │
│    bucket(delta_L)   │        │
│ 2. get_pressure_     │        │
│    deviation()       │        │
│    └─ Empirical-Bayes│        │
│       lookup →       │        │
│       deviation,     │        │
│       90% CI         │        │
│ 3. DecisionLogEntry  │        │
│    for strategy_     │        │
│    exploit           │        │
│ Outputs: pressure_   │        │
│ result, decision_log │        │
└────────┬─────────────┘        │
         │                      │
         ▼                      │
┌──────────────────────┐        │
│ route_after_pressure │        │
│ _diagnostic()        │        │
│ delta_leverage_low   │        │
│ >= 0.10?             │        │
└────────┬─────────────┘        │
         │                      │
         ▼                      │
┌──────────────────────┐        │
│ StrategyExploitNode  │        │
│ (TRIGGERED, STUB)    │        │
│ 1. count_opponent_   │        │
│    observations()    │        │
│ 2. N >= 30?          │        │
│    YES → "module_    │        │
│    not_yet_impl"     │        │
│    NO  → "insuf-     │        │
│    ficient_data"     │        │
│ Output: exploit_     │        │
│ result               │        │
└────────┬─────────────┘        │
         │                      │
         └──────────┬───────────┘
                    │
                    ▼
  ┌─────────────────────────────────────┐
  │  TacticalOutputNode (ALWAYS-ON)     │
  │  1. assemble_signal_payload()       │
  │     → variable-shape dict           │
  │  2. is_escalated?                   │
  │     YES → call_narrative_llm()      │
  │       └─ Anthropic SDK async call   │
  │          └─ success → narrative     │
  │          └─ failure → passthrough   │
  │     NO  → template string (0 LLM)   │
  │  3. TacticalOutputResult            │
  │  Output: tactical_output            │
  └──────────────────┬──────────────────┘
                     │
                     ▼
              Tactical Signal Emitted
         (to FastAPI streaming layer, Phase 6)
```

---

## 3. Component Deep-Dives

### 3.1 `src/graph/state.py` — State Schema & Data Contracts

**Role:** Defines every data type that moves through the graph. All node inputs and outputs are validated against these models.

#### Data Model Hierarchy

```
PulseGraphState
├── point_context: PointContext
│   ├── match_id, point_index, server_id, returner_id
│   ├── surface, serve_number
│   ├── point/game/set scores (server & returner)
│   ├── match_format: "bo3" | "bo5"
│   └── to_match_state() → MatchState
│
├── leverage_result: LeverageResult | None
│   ├── delta_leverage         ← point estimate ΔL
│   ├── delta_leverage_low     ← Wilson CI lower bound ← ESCALATION GATE INPUT
│   ├── delta_leverage_high    ← Wilson CI upper bound
│   ├── p_hat                  ← point-win probability
│   ├── sample_size            ← observations backing p_hat
│   └── fallback_tier          ← 0=Exact, 1=Player, 2=Surface, 3=Default
│
├── pressure_result: PressureDeviationResult | None
│   ├── server_id, leverage_bucket
│   ├── pressure_deviation     ← serve win rate shift under pressure
│   ├── deviation_low_90, deviation_high_90  ← 90% credible interval
│   └── is_sufficient_sample
│
├── exploit_result: ExploitResult | None
│   ├── status                 ← "insufficient_data" | "module_not_yet_implemented"
│   ├── opponent_id, sample_size
│   ├── is_sufficient_sample
│   └── recommendation: str | None
│
├── tactical_output: TacticalOutputResult | None
│   ├── narrative              ← coach-readable text (LLM or template)
│   ├── escalated              ← True if threshold met
│   ├── raw_payload            ← assembled signal dictionary
│   └── is_llm_fallback        ← True if LLM unavailable
│
└── decision_log: Annotated[list[DecisionLogEntry], operator.add]
    └── DecisionLogEntry
        ├── node               ← target node name
        ├── fired              ← True/False
        └── reason             ← quantitative rationale string
```

#### The `operator.add` Reducer Pattern

The most architecturally significant detail in `state.py` is the `decision_log` field annotation:

```python
decision_log: Annotated[list[DecisionLogEntry], operator.add] = Field(
    default_factory=list
)
```

LangGraph's `StateGraph` uses this annotation to determine how to merge a node's returned update dictionary with the current state. Without `operator.add`, returning `{"decision_log": [entry]}` would **replace** the log. With `operator.add`, LangGraph calls `operator.add(existing_log, [entry])` — which is list concatenation — so entries accumulate across node executions.

**Why this matters:** It allows `StateMonitorNode` and `PressureDiagnosticNode` to each return their own `decision_log` key in their output dictionaries, and LangGraph automatically concatenates them into a unified audit trail. No in-place mutation, no `state.decision_log.append()`, no race condition risk.

---

### 3.2 `src/graph/state_monitor.py` — StateMonitorNode

**Role:** The always-on first node. Executes for every single point in the match, regardless of score state.

#### Factory Pattern (D-10)

`StateMonitorNode` is built using a **factory function** rather than a class or a plain function:

```python
def make_state_monitor_node(
    stratum_table: StratumTable, params: Params | None = None
) -> Callable[..., Any]:
    cfg = params if params is not None else load_params()

    async def state_monitor_node(state: PulseGraphState) -> dict[str, Any]:
        ...  # all logic here

    return state_monitor_node
```

The factory closes over `stratum_table` and `cfg` at graph build time. These are loaded exactly once from disk. The inner async function is the actual LangGraph node — it receives only `PulseGraphState` and returns a `dict`. This pattern eliminates per-point disk I/O and prevents repeated configuration parsing.

#### Execution Sequence (5 Steps)

```
Step 1: resolve_point_win_probability(stratum_table, server_id, surface, serve_number)
        → StratumResult(p_hat, wins, sample_size, fallback_tier)

        4-tier fallback hierarchy:
        Tier 0 (Exact):   player × surface × serve_number → p_hat from actual data
        Tier 1 (Player):  player × serve_number averaged across surfaces
        Tier 2 (Surface): population × surface × serve_number
        Tier 3 (Default): cfg.solver.default_p_serve (0.6 from params.yaml)

Step 2: ctx.to_match_state()
        → MatchState(point/game/set scores, server_id, match_format)
        (Cross-field validator rejects invalid score combinations, e.g. 4-4 deuce)

Step 3: propagate_leverage_uncertainty(state, wins, sample_size, confidence_level, ...)
        → Wilson CI: [p_low, p_high] from (wins, sample_size)
        → leverage_low  = compute_leverage(MatchState, p_low)   ← direct-extreme evaluation
        → leverage_high = compute_leverage(MatchState, p_high)  ← (ADR-005 Amendment 1)
        → LeverageBandResult(leverage_point, leverage_low, leverage_high)

Step 4: LeverageResult(
            delta_leverage      = leverage_band_res.leverage_point,
            delta_leverage_low  = leverage_band_res.leverage_low,   ← GATE INPUT
            delta_leverage_high = leverage_band_res.leverage_high,
            p_hat               = stratum_res.p_hat,
            sample_size         = stratum_res.sample_size,
            fallback_tier       = int(stratum_res.fallback_tier),
        )

Step 5: Escalation decision → DecisionLogEntry records
        if lev_low >= 0.10:
            [DecisionLogEntry(node="pressure_diagnostic", fired=True,  reason=...)]
        else:
            [DecisionLogEntry(node="pressure_diagnostic", fired=False, reason=...),
             DecisionLogEntry(node="strategy_exploit",   fired=False, reason=...)]

Return: {"leverage_result": leverage_result, "decision_log": log_entries}
```

---

### 3.3 `src/graph/pulse_graph.py` — Graph Definition & Routing

**Role:** The graph builder — wires nodes, conditional edges, and routing functions into a compiled `CompiledStateGraph`.

#### Routing Functions

Two routing functions implement the conditional topology. Both call the shared `should_escalate()` helper:

```python
def should_escalate(leverage_result: LeverageResult | None, threshold: float) -> bool:
    if leverage_result is None:
        return False
    return leverage_result.delta_leverage_low >= threshold
```

**`route_after_state_monitor(state, params)`**
- Reads `delta_leverage_low` from `state.leverage_result`
- If `>= 0.10` → routes to `"pressure_diagnostic"`
- Else → routes to `"tactical_output"` (skips all diagnostic nodes)
- Emits an OpenTelemetry span with `pulse.fired`, `pulse.reason` attributes

**`route_after_pressure_diagnostic(state, params)`**
- Re-evaluates the same threshold (same `leverage_result` is still in state)
- If `>= 0.10` → routes to `"strategy_exploit"`
- Else → routes to `"tactical_output"`
- This second check is architecturally necessary: routing logic lives in the routing layer, not in node output flags.

#### Graph Construction (`build_pulse_graph`)

```python
builder = StateGraph(PulseGraphState)

# 1. Register nodes (factory functions called here; artifacts bound via closure)
builder.add_node("state_monitor",       make_state_monitor_node(stratum_table, cfg))
builder.add_node("pressure_diagnostic", make_pressure_diagnostic_node(pressure_artifact, cfg))
builder.add_node("strategy_exploit",    make_strategy_exploit_node(stratum_table, cfg))
builder.add_node("tactical_output",     make_tactical_output_node(cfg))

# 2. Entry point
builder.set_entry_point("state_monitor")

# 3. Conditional edges
builder.add_conditional_edges(
    "state_monitor",
    route_after_state_monitor,
    {"pressure_diagnostic": "pressure_diagnostic", "tactical_output": "tactical_output"},
)
builder.add_conditional_edges(
    "pressure_diagnostic",
    route_after_pressure_diagnostic,
    {"strategy_exploit": "strategy_exploit", "tactical_output": "tactical_output"},
)

# 4. Fixed edges for the terminal path
builder.add_edge("strategy_exploit", "tactical_output")
builder.add_edge("tactical_output", END)

compiled_graph = builder.compile()
```

#### Artifact Loading (One-Time, D-9)

`load_graph_artifacts()` runs once when `build_pulse_graph()` is called — before any point event is processed. The artifacts (StratumTable, PressureModelArtifact) are deserialized from disk and stored in closures. Every subsequent point invocation uses in-memory lookups with zero disk I/O.

---

### 3.4 `src/graph/pressure_diagnostic.py` — PressureDiagnosticNode

**Role:** Triggered node. Executes only when `delta_leverage_low >= 0.10`.

#### Leverage Bucket Mapping

Before querying the pressure model, `delta_leverage` (the point estimate, not the lower bound) is mapped into a categorical bucket:

```
Bucket 0 (Routine):   delta_leverage < boundaries[0]           (< 0.10 in params.yaml)
Bucket 1 (Elevated):  boundaries[0] <= delta_leverage < boundaries[1]  (0.10 – 0.40)
Bucket 2 (Critical):  delta_leverage >= boundaries[1]           (>= 0.40)
```

This bucketing exists because the Empirical-Bayes pressure deviation model is trained per-player per-bucket, not per-player per-leverage-value. Bucketing prevents extreme overfitting to specific leverage values while preserving the meaningful distinction between moderately important points (Elevated) and match-defining points (Critical).

#### Execution Sequence

```
Step 1: Guard — if state.leverage_result is None: raise ModelInferenceError
        (Node only runs on escalated path; missing leverage_result is a bug, not a data gap)

Step 2: assign_leverage_bucket(delta_leverage, cfg.models.pressure_leverage_buckets)
        → bucket_idx ∈ {0, 1, 2}

Step 3: get_pressure_deviation(artifact, server_id=ctx.server_id, leverage_bucket=bucket_idx)
        → PressureDeviationResult | None

        Internally:
        artifact.results[f"{server_id}|{bucket_idx}"]
        Returns None if player-bucket combination has insufficient data

Step 4: DecisionLogEntry for strategy_exploit gate decision

Return: {"pressure_result": pressure_res, "decision_log": log_entries}
```

**Sparse-player handling:** If `get_pressure_deviation()` returns `None` (player not in artifact or bucket has too few observations), `pressure_result` is set to `None` in state. `TacticalOutputNode` skips it in payload assembly. The system never fabricates a pressure signal for players with insufficient data.

---

### 3.5 `src/graph/strategy_exploit.py` — StrategyExploitNode (Phase 4 Stub)

**Role:** Triggered node enforcing the ADR-003 data-sufficiency gate. Full minimax equilibrium solving is a Phase 5 deliverable.

#### The Sufficiency Gate (ADR-003)

```python
sample_size = count_opponent_observations(stratum_table, opponent_id)
is_sufficient = sample_size >= cfg.thresholds.exploit_min_sample_size  # 30 in params.yaml

if is_sufficient:
    status = "module_not_yet_implemented"   # Honest Phase 5 placeholder
else:
    status = "insufficient_data"             # Sufficiency Gate enforcement
```

**Why the gate runs even in the stub phase:**
The ADR-003 invariant applies to the _decision to emit an exploit signal_, not to the implementation of the exploit algorithm. Running the real gate now means Phase 5 can replace the `"module_not_yet_implemented"` status with real recommendations without touching the gate logic — the architectural boundary is already correct.

#### `count_opponent_observations()`

Uses the Phase 3 StratumTable's `tier1_player` lookup (opponent × serve_number) as a Phase-4-scoped proxy for opponent sample size. Phase 5 will supersede this with the real return-positioning dataset pipeline from `core/game_theory.py`.

```python
key1 = f"{opponent_id}|1"
key2 = f"{opponent_id}|2"
n1 = stratum_table.tier1_player[key1].sample_size if key1 in stratum_table.tier1_player else 0
n2 = stratum_table.tier1_player[key2].sample_size if key2 in stratum_table.tier1_player else 0
return n1 + n2
```

---

### 3.6 `src/graph/tactical_output.py` — TacticalOutputNode

**Role:** The terminal node. Always executes. Assembles whichever signals fired and conditionally invokes the LLM.

#### Variable-Shape Signal Payload

`assemble_signal_payload()` produces a dictionary that includes only fields present in state:

```python
payload = {"point_context": state.point_context.model_dump()}

if state.leverage_result is not None:
    payload["leverage_result"] = state.leverage_result.model_dump()
if state.pressure_result is not None:
    payload["pressure_result"] = state.pressure_result.model_dump()
if state.exploit_result is not None:
    payload["exploit_result"] = state.exploit_result.model_dump()
```

This variable-shape design is consistent with ADR-001: the payload structure honestly reflects which nodes fired. A routine-point payload has only `leverage_result`; a fully-escalated payload carries all three.

#### LLM Call Guard (D-7)

```python
is_escalated = (state.pressure_result is not None) or (state.exploit_result is not None)

if is_escalated:
    llm_text = await call_narrative_llm(raw_payload, params=cfg)
    if llm_text is not None:
        narrative = llm_text
        is_llm_fallback = False
    else:
        narrative = f"Escalated point{lev_str}. Signal payload assembled."
        is_llm_fallback = True
else:
    narrative = f"Routine point{lev_str}. No escalation required."
    is_llm_fallback = False
```

The escalation check reads `pressure_result` and `exploit_result` — not a flag in state, not the leverage value. This means the LLM guard is structurally coupled to actual node execution, not to a threshold that could drift out of sync with routing logic.

---

### 3.7 `src/graph/llm_client.py` — LLM Client

**Role:** Thin async wrapper around the Anthropic SDK. The only place an external API call occurs in PULSE Phase 4.

#### System Prompt Design

```
"You are an expert tennis performance analyst assistant. Phrase the pre-computed
match state and leverage signals into a short, coach-readable tactical note
(1-2 sentences). State numbers and statistics EXACTLY as provided in the input
payload. DO NOT invent, hallucinate, alter, or re-derive any probabilities,
leverage numbers, or player metrics."
```

The system prompt is deliberately minimal: one role, one output format, one hard constraint. Its only job is to prevent hallucination of numbers. The DeepEval groundedness suite (§5.1) enforces this constraint in CI.

#### Deterministic Fallback Behavior

```python
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    return None          # No key → immediate None (no retry)

try:
    response = await client.messages.create(...)
    return response.content[0].text.strip()
except Exception as e:
    logger.warning(f"LLM narrative synthesis failed ({type(e).__name__}: {e}).")
    return None          # Any exception → None (no secondary vendor)
```

`None` propagates to `TacticalOutputNode`, which sets `is_llm_fallback=True` and returns the raw structured payload. A deterministic passthrough is a complete fallback — it is not a degraded mode.

---

## 4. Design Patterns

### 4.1 Factory-Closure Pattern

Every node is built by a factory function:

```python
def make_<node>_node(artifact, params) -> Callable:
    cfg = ...         # bound once at graph build time
    artifact = ...    # bound once at graph build time

    async def <node>_node(state: PulseGraphState) -> dict:
        ...           # uses cfg and artifact from closure

    return <node>_node
```

**Benefits:**
- Artifacts (large Parquet-deserialized objects) are loaded once at startup, not per-point.
- Each node function has a minimal, testable signature: `(PulseGraphState) -> dict`.
- Factory-level injection enables unit testing with mock artifacts without monkey-patching.

### 4.2 Conditional Edge Topology

LangGraph's `add_conditional_edges()` accepts:
1. A source node name
2. A routing function `(state) -> str`
3. A mapping of return values to destination node names

```python
builder.add_conditional_edges(
    "state_monitor",
    route_after_state_monitor,
    {"pressure_diagnostic": "pressure_diagnostic", "tactical_output": "tactical_output"},
)
```

The routing function returns a string; LangGraph resolves the destination. This keeps routing logic in pure Python functions — independently testable without a running graph.

### 4.3 Pydantic v2 State with Reducer Annotations

All state fields are Pydantic `Field` declarations. Optional fields (`leverage_result`, `pressure_result`, `exploit_result`, `tactical_output`) default to `None`, representing "node has not yet fired." The `decision_log` field uses `Annotated` with `operator.add` to enable LangGraph's automatic list concatenation during state merging.

### 4.4 OpenTelemetry Span Emission

Every routing function emits an OTel span:

```python
with tracer.start_as_current_span("route_after_state_monitor") as span:
    span.set_attribute("pulse.target_node", "pressure_diagnostic")
    span.set_attribute("pulse.fired", fired)
    span.set_attribute("pulse.reason", reason)
```

This captures both fired and suppressed decisions in the telemetry trace. A future Grafana dashboard (Phase 6) can visualize escalation rate, suppression rate, and LLM call frequency per-point without any additional instrumentation work.

---

## 5. Quality Gates & Verification

### 5.1 DeepEval Groundedness Evaluation (`tests/evals/`)

Four test cases verify LLM narrative grounding:

1. **`test_escalated_narrative_grounded_in_payload`** — Numbers in the LLM narrative (percentages, bounds, leverage figures) must appear in `raw_payload`.
2. **`test_routine_narrative_is_template_no_hallucination`** — Routine-point narratives must not contain fabricated numbers from non-existent payloads.
3. **`test_llm_fallback_narrative_contains_no_numbers`** — When `is_llm_fallback=True`, narrative is a template string — verified to contain no digits.
4. **`test_groundedness_check_catches_hallucinated_number`** — Proves the check itself is sensitive: injecting a hallucinated number into a mock narrative causes the assertion to fail.

### 5.2 Integration Tests (`tests/integration/test_conditional_graph.py`)

Four integration scenarios verify the full async graph against a live compiled graph:

| Test | Verifies |
|---|---|
| `test_routine_point_no_escalation` | leverage_result only; decision_log shows suppression entries |
| `test_high_leverage_full_escalation` | All four nodes fire; LLM fallback on missing API key |
| `test_conditional_topology_node_execution_differs_by_match_state` | Routine vs. escalated states execute different node sets |
| `test_insufficient_data_exploit_suppression` | Sparse opponent triggers `"insufficient_data"` status |

### 5.3 Unit Tests (`tests/unit/`)

| Test File | Coverage Area |
|---|---|
| `test_graph_state.py` | Schema construction, `decision_log` reducer aggregation |
| `test_state_monitor.py` | Node output schema correctness |
| `test_pressure_diagnostic.py` | Bucket mapping, sparse-player `None` handling |
| `test_strategy_exploit.py` | Sufficiency gate: pass/fail branches |
| `test_tactical_output.py` | Escalated vs. routine paths, LLM fallback |
| `test_routing.py` | Routing function decisions across leverage bands |

---

## 6. Execution Paths: Worked Examples

### 6.1 Routine Point (Score: 0-0, 0-0, 0-0)

```
Nodes executed:  StateMonitorNode → TacticalOutputNode
LLM calls:       0
decision_log:    [fired=False: "pressure_diagnostic", fired=False: "strategy_exploit"]
Latency:         ~0.05ms (no ML inference beyond stratum lookup)

Output:
{
  "narrative": "Routine point (ΔL=0.001). No escalation required.",
  "escalated": false,
  "raw_payload": {
    "leverage_result": {
      "delta_leverage": 0.0001, "delta_leverage_low": 0.0000,
      "delta_leverage_high": 0.0002, "p_hat": 0.7319,
      "sample_size": 175948, "fallback_tier": 2
    }
  },
  "is_llm_fallback": false
}
```

### 6.2 High-Leverage Break Point (Final Set, 4-5, 30-40)

```
Nodes executed:  StateMonitorNode → PressureDiagnosticNode →
                 StrategyExploitNode → TacticalOutputNode
LLM calls:       1 (Anthropic API, ~800ms)
decision_log:    [fired=True: "pressure_diagnostic", fired=True: "strategy_exploit"]

Output:
{
  "narrative": "Carlos Alcaraz serve win rate drops -6.5% under elevated leverage
                (90% CI [-13.2%, -0.1%]). Exploit module pending Phase 5.",
  "escalated": true,
  "raw_payload": {
    "leverage_result": {
      "delta_leverage": 0.8842, "delta_leverage_low": 0.8691,
      "delta_leverage_high": 0.8985, "p_hat": 0.7319,
      "sample_size": 175948, "fallback_tier": 2
    },
    "pressure_result": {
      "server_id": "Carlos Alcaraz", "leverage_bucket": 2,
      "pressure_deviation": -0.0652,
      "deviation_low_90": -0.1324, "deviation_high_90": -0.0007,
      "is_sufficient_sample": true
    },
    "exploit_result": {
      "status": "module_not_yet_implemented",
      "opponent_id": "Jannik Sinner",
      "sample_size": 14025, "is_sufficient_sample": true,
      "recommendation": null
    }
  },
  "is_llm_fallback": false
}
```

### 6.3 High-Leverage Point with LLM Unavailable

```
Nodes executed:  StateMonitorNode → PressureDiagnosticNode →
                 StrategyExploitNode → TacticalOutputNode
LLM calls:       1 attempt → exception → None returned
is_llm_fallback: true

Output:
{
  "narrative": "Escalated point (ΔL=0.884). Signal payload assembled.",
  "escalated": true,
  "raw_payload": { ... same structure as 6.2 ... },
  "is_llm_fallback": true
}
```

The fallback output is a complete, human-readable, structured signal. No re-attempt, no secondary vendor call.

---

## 7. File Map & Dependency Graph

```
src/graph/
│
├── state.py              ← Data contracts (no external imports beyond Pydantic/Markov)
│   └── Imports: markov_solver.MatchState, models.pressure_deviation.PressureDeviationResult
│
├── state_monitor.py      ← Always-on node factory
│   └── Imports: state.py, core.leverage_uncertainty, models.point_win_classifier
│
├── pressure_diagnostic.py  ← Triggered node factory
│   └── Imports: state.py, models.pressure_deviation
│
├── strategy_exploit.py   ← Triggered stub node factory
│   └── Imports: state.py, models.point_win_classifier
│
├── tactical_output.py    ← Terminal node factory
│   └── Imports: state.py, llm_client.py
│
├── llm_client.py         ← Anthropic SDK wrapper (only external API surface in Phase 4)
│   └── Imports: anthropic, config.loader
│
└── pulse_graph.py        ← Graph builder + routing functions
    └── Imports: all of the above + langgraph, opentelemetry
```

**Dependency rule:** No module in `src/graph/` imports from another `src/graph/` module except through `pulse_graph.py`. Nodes do not know about each other — they only know `PulseGraphState`. This prevents coupling: adding a new node does not require modifying existing nodes, only `pulse_graph.py`.

---

## 8. Key Architectural Decisions (Summary)

| Decision | ADR / Code Location | Rationale |
|---|---|---|
| Conditional edge topology (not fixed pipeline) | ADR-001, D-1 | Routine points warrant zero diagnostic compute; emitting signals on every point violates Sufficiency Gate |
| Wilson lower bound as escalation gate | D-4 (Option B) | Wide uncertainty bands suppress escalation even if point estimate is high — honest about what the data supports |
| Factory-closure pattern for node binding | D-10 | One-time artifact loading; clean per-point async callable signature |
| `operator.add` reducer for `decision_log` | D-2a | LangGraph-native list accumulation without in-place mutation |
| Routing functions in `pulse_graph.py`, not in nodes | D-3 | Routing is a graph concern; nodes remain pure computation units |
| Single LLM vendor with passthrough fallback | D-7, §2 | Deterministic passthrough is a complete fallback; a second vendor adds complexity with no gain |
| LLM call guard reads `pressure_result`/`exploit_result` presence | D-7 | Structurally coupled to actual execution — cannot drift out of sync with routing threshold |
| DeepEval groundedness gate in CI | D-9 | Automated verification that LLM never fabricates numbers absent from input payload |

---

## 9. What Comes Next (Phase 5)

Phase 4 delivers the complete orchestration skeleton. Phase 5 fills the stub:

| Phase 5 Deliverable | Replaces Phase 4 Placeholder |
|---|---|
| `core/game_theory.py` — Nash equilibrium & best-response deviation solver | `"module_not_yet_implemented"` status in `ExploitResult` |
| Return-positioning dataset pipeline | `count_opponent_observations()` StratumTable proxy |
| `scipy.optimize.linprog` game-theory equilibrium computation | Placeholder `recommendation=None` |
| `StrategyExploitNode` full implementation | Phase 4 stub logic |

The Phase 4 architecture is specifically designed to make this transition seamless: `StrategyExploitNode` already enforces the real sufficiency gate, already returns the correct `ExploitResult` schema, and already connects correctly to `TacticalOutputNode`. Phase 5 only needs to implement the computation inside `StrategyExploitNode` — no schema changes, no routing changes, no state changes.
