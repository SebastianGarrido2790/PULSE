# Phase 4 — Execution Workflow

**Event-Driven Orchestration (LangGraph) — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 4 of 7 | **Version:** 1.0.0 | **Date:** 2026-08-08
**Status:** 🟢 Stage 5 Complete — Gate 5 Passed (Ready for Stage 6)
**Authority:** `reports/docs/decisions/phase4_implementation_plan_and_decisions.md` (v1.0.0, Approved) — every step below traces to a specific approved decision ID
**Scope of this document:** sequencing only. It translates D-1 through D-11 into an ordered task list with explicit dependencies and verification gates. No implementation begins from this document alone — it's the map, not the code.

---

## How to Read This

11 stages, strictly ordered — each stage depends on the one before it. Steps within a stage are numbered continuously across the whole document (1–56) so any step can be referenced unambiguously. Each step is tagged with the decision(s) it implements, in brackets. A **Gate** closes every stage: nothing in the next stage starts until the gate passes.

---

## Stage 0 — Pre-Implementation Verification ✅

_Resolves the two VERIFY items the approved plan explicitly gates on. Nothing else starts until this stage closes._

1. Inspect `src/models/pressure_deviation.py` — confirm whether `assign_leverage_bucket()` is already defined there. **[D-6, VERIFY]**
2. If not found there, inspect `scripts/train_pressure.py` and confirm it's currently defined only inside the training script. **[D-6, VERIFY]**
3. If script-only: relocate `assign_leverage_bucket()` into `src/models/pressure_deviation.py`; update `scripts/train_pressure.py` to import it from there instead of defining it locally. Re-run `uv run pytest tests/unit/test_pressure_deviation.py` to confirm zero regressions from the move. **[D-6]**
4. Create the `src/graph/` package (`__init__.py`) if it doesn't already exist, per the project structure.
5. Confirm the Phase 3 artifacts (`stratum_table.json`, the pressure-deviation artifact) referenced by `dvc.lock` are present and loadable — Stage 2's artifact loader depends on this. **[D-9]**

**Gate 0:** `assign_leverage_bucket()` confirmed importable from `src/models/pressure_deviation.py`; `src/graph/` exists; both Phase 3 artifacts load cleanly.

---

## Stage 1 — Shared Graph State Schema & Configuration ✅

_Nothing downstream can be built without this — every node reads and writes this shape._

6. Create `src/graph/state.py`. Define the `PulseGraphState` Pydantic `BaseModel` exactly per the approved field table: `point_context`, `leverage_result` (always populated), `pressure_result: Optional`, `exploit_result: Optional`, `tactical_output`, `decision_log`. **[D-2, D-2a]**
7. In the same file, define the nested sub-models it references: a leverage-result model (`ΔL`, `ΔL_low`, `ΔL_high`, `p_hat`, `sample_size`, `fallback_tier`) and a decision-log-entry model (`node`, `fired: bool`, `reason: str`). **[D-2]**
8. Add the LLM configuration block to `params.yaml` — provider, model name (Haiku-class), `max_tokens`, `temperature`, request timeout — no hardcoded values in `tactical_output.py` later. **[D-7]**
9. Explicitly confirm no new `params.yaml` key is needed for the escalation-threshold logic itself — D-4 (Option B, lower-bound gating) uses only the existing `thresholds.leverage_escalation`, no new coefficient. Record this as a deliberate no-op, not an oversight. **[D-4]**
10. Explicitly confirm no new `dvc.yaml` stage is needed — orchestration code isn't a DVC-tracked artifact producer. Record as a deliberate no-op. **[audit §1.4]**

**Gate 1:** `PulseGraphState` and its sub-models exist and pass a standalone Pydantic validation smoke test (construct one instance with dummy data); `params.yaml` diff reviewed and limited to the LLM block.

---

## Stage 2 — Artifact Loading Utility ✅

_Defines how the once-only load from D-9 actually happens, before any node needs it._

11. In `src/graph/pulse_graph.py`, implement a graph-construction entry point (e.g. `build_pulse_graph(params)`) whose first responsibility, before any node is registered, is to load `StratumTable` (via `load_stratum_table()`) and the `PressureModelArtifact` (via `load_pressure_artifact()`) exactly once. **[D-9]**
12. Decide and document the injection mechanism nodes will use to reach these loaded artifacts: factory functions that close over the artifacts and return the actual per-node callable (per D-10's function-based style), rather than reloading or passing raw artifacts through graph state. **[D-9, D-10]**

**Gate 2:** `build_pulse_graph()` skeleton loads both artifacts and `Params` exactly once and exposes them to a placeholder no-op node, confirmed by a throwaway print/log check (not a committed test — the real test comes once nodes exist).

---

## Stage 3 — `StateMonitorNode` ✅

_Always-on node (FR-3). Built and unit-tested in isolation before anything conditional touches it._

13. Create `src/graph/state_monitor.py`. Implement `make_state_monitor_node(stratum_table, params)`, a factory returning an `async` node callable — async from the outset, per D-7a, even though this particular node makes no network call, to keep every node in the graph on one consistent calling convention. **[D-9, D-10, D-7a]**
14. Inside the node: call `resolve_point_win_probability()` against the loaded stratum table → `p_hat`, `sample_size`, `fallback_tier`. **[upstream contract, unchanged]**
15. Call `compute_leverage()` → the point-estimate `ΔL`. **[upstream contract, unchanged]**
16. Call `propagate_leverage_uncertainty()` → `ΔL_low`, `ΔL_high` (direct-extreme bounds, ADR-005 Amendment 1). **[upstream contract, unchanged]**
17. Populate `state.leverage_result` with all six fields from Stage 1's schema. No conditional logic inside this node — it always runs, always writes, never checks a threshold itself (FR-3; thresholding is Stage 6's job, not this node's). **[D-2]**
18. Write `tests/unit/test_state_monitor.py` — a pure node-level test (fixture stratum table, no graph, no LangGraph machinery) asserting the output schema is populated correctly for a known input.

**Gate 3:** `test_state_monitor.py` passes; `state_monitor.py` stays under the 1,000-line ceiling; `ruff`/`pyright` clean on this file.

---

## Stage 4 — `PressureDiagnosticNode` ✅

_Triggered node #1. Depends on Stage 0's relocation and a new accessor this stage adds._

19. In `src/models/pressure_deviation.py`, add `get_pressure_deviation(artifact, server_id, bucket) -> PressureDeviationResult | None` — the serving-time lookup that was missing from the audit, built next to `load_pressure_artifact()` per the approved D-6 ownership decision. The `"server_id|bucket_idx"` key-construction logic lives here once, reused by both training and serving. **[D-6]**
20. Confirm `assign_leverage_bucket()` (relocated or confirmed in Stage 0) is importable alongside it in the same module. **[D-6]**
21. Create `src/graph/pressure_diagnostic.py`. Implement `make_pressure_diagnostic_node(pressure_artifact, params)`, an async factory-built node per the same pattern as Stage 3. **[D-9, D-10, D-7a]**
22. Inside: bucket the point's `ΔL` via `assign_leverage_bucket()`, then call the new `get_pressure_deviation()` accessor; write the result (or `None` on a sparse-player miss, which is not an error condition) into `state.pressure_result`. **[D-2b]**
23. Write `tests/unit/test_pressure_diagnostic.py` covering both the found and the sparse-player-miss cases.

**Gate 4:** unit tests pass; `ruff`/`pyright` clean; no `src/` → `scripts/` import direction anywhere in this stage's new code.

---

## Stage 5 — `StrategyExploitNode` (Stub) ✅

_Triggered node #2. Resolves Finding A concretely — the sufficiency gate is real, the recommendation payload is a flagged placeholder._

24. Before writing the node: confirm what data is actually available in Phase 2/3 artifacts to feed an honest sample-size sufficiency check, since the full opponent return-positioning dataset is Phase 5 scope (`core/game_theory.py`). If no opponent-specific observation count is currently exposed, add a small, narrowly-scoped `count_opponent_observations(server_id)` helper here — strictly a count, not the return-positioning model itself, which stays in Phase 5. Flag explicitly in code comments that this counter is Phase-4-scoped and will likely be superseded by Phase 5's real data pipeline. **[D-1]**
25. Create `src/graph/strategy_exploit.py`. Implement `make_strategy_exploit_node(params)`, async factory-built node. **[D-9, D-10, D-7a]**
26. Inside: run the real sufficiency gate — compare the observation count from step 24 against `thresholds.exploit_min_sample_size` (ADR-003). If sufficient: return a structurally valid payload flagged `status: "module_not_yet_implemented"`, carrying the real sample size for transparency, not a fabricated recommendation. If insufficient: return an explicit `"insufficient_data"` result (FR-6 — graceful degradation, not an error). **[D-1]**
27. Write `tests/unit/test_strategy_exploit.py` covering both branches.

**Gate 5:** both branches tested and passing; the stub payload is unambiguously distinguishable downstream from a real Phase-5 recommendation (this matters for D-8's groundedness check later).

---

## Stage 6 — Conditional Edges: Diagnostic Branch

_Wires Stages 3–5 together. This is where D-3, D-4, D-4a, and D-5 all become real code paths for the first time._

28. In `pulse_graph.py`, implement one shared escalation-gate function, e.g. `should_escalate(leverage_result, threshold) -> bool`, using the approved D-4 rule: `ΔL_low ≥ threshold` — the lower confidence bound, not the point estimate. Both routing functions below call this same function; no duplicated threshold logic. **[D-4, D-4a]**
29. Implement the routing function after `StateMonitorNode`: decide whether to visit `PressureDiagnosticNode` using `should_escalate()`; append a `DecisionLogEntry` to `state.decision_log` recording fire-or-suppress and the reason — logged here, in the routing function, because a suppressed node is never invoked and cannot log itself (D-3's consequence). **[D-3, D-5]**
30. Implement the routing function after `PressureDiagnosticNode`: decide whether to visit `StrategyExploitNode` using the same `should_escalate()` **and** the sufficiency check (FR-5); log fire-or-suppress with reason, same pattern. **[D-4a, D-5]**
31. Register `add_conditional_edges` for both routing functions in the (still-partial) `StateGraph` object; leave their "did not fire" branches pointing at a temporary placeholder — the real terminal node doesn't exist until Stage 7. **[D-3]**
32. Add an OpenTelemetry span inside each routing function, tagged fired/suppressed plus reason, per the approved telemetry note attached to D-5. **[D-5]**
33. Write `tests/unit/test_routing.py` — feed synthetic `PulseGraphState` objects with known leverage bands and sample sizes directly into the routing functions (no full graph execution needed), asserting correct next-node decisions and correct `decision_log` entries.

**Gate 6:** routing unit tests pass for all four combinations of (leverage above/below threshold) × (sample size sufficient/insufficient); every suppression case produces exactly one logged entry.

---

## Stage 7 — `TacticalOutputNode` and Graph Finalization

_The terminal node. Once this exists, `pulse_graph.py` can be compiled end to end._

34. Create `src/graph/llm_client.py`. Implement a thin wrapper, e.g. `call_narrative_llm(payload, params) -> str | None`, around the Anthropic SDK call (Haiku-class model, per D-7). On any exception — timeout, network, rate limit — it returns `None` rather than raising, which is the deterministic-passthrough fallback the harness requires, not an error state. **[D-7]**
35. Create `src/graph/tactical_output.py`. Implement `make_tactical_output_node(params)`, async factory-built node. **[D-9, D-10, D-7a]**
36. Inside: assemble the structured signal payload strictly from whichever of `leverage_result` / `pressure_result` / `exploit_result` are non-`None` on the incoming state (FR-7's variable output shape, via D-2b's presence-check pattern) — this assembly happens before any LLM call and does not depend on it. **[D-2b]**
37. Guard the LLM call: only invoke `call_narrative_llm()` when at least one of `pressure_result` or `exploit_result` is non-`None`. A routine, non-escalated point gets its `tactical_output` populated directly from `leverage_result` with **no LLM call at all** — this keeps inference cost at zero for the overwhelming majority of points, consistent with "cents per escalation, not per point" in the project charter's cost story. **[D-7]**
38. Write the LLM's returned text (or `None` on failure/no-call) into `state.tactical_output.narrative`, alongside the always-present structured payload from step 36.
39. Back in `pulse_graph.py`: register `tactical_output_node`, route every prior branch's "did not fire" and "did fire" endpoints into it as the unconditional terminal step (replacing Stage 6's placeholder), add the edge to `END`, and call `.compile()` on the finished `StateGraph`.
40. Write `tests/unit/test_tactical_output.py`, mocking the LLM client to cover: successful narrative generation, LLM failure → structured-payload-only fallback, and a leverage-only (no escalation) case confirming zero LLM calls are made.

**Gate 7:** `build_pulse_graph()` returns a fully compiled, runnable graph; all four node-level unit test files pass; `ruff`/`pyright`/file-size-ceiling clean across every new file.

---

## Stage 8 — DeepEval Groundedness Test

_Closes Finding B, scoped exactly as approved — one check, not a general eval suite._

41. Confirm `deepeval` is already present in `pyproject.toml` (it's listed among Phase 1's baseline dependencies) — add only if genuinely missing. **[D-8]**
42. Create `tests/evals/test_tactical_output_groundedness.py`. Scope: does `tactical_output.narrative` introduce any number, confidence claim, or exploit recommendation not present in the structured payload it was built from — nothing broader. **[D-8]**
43. Decide the eval's data source for determinism: use recorded/cached LLM responses for the fixtures that ship in CI (consistent with the project's stated "100% reproducible across local and CI environments" testing principle), with an optional live-call mode for manual runs against the real API. **[D-8, testing conventions]**
44. Include at least one fixture built from Stage 5's stub `StrategyExploitNode` payload specifically, to confirm the groundedness check catches a narrative that invents a real recommendation out of a `"module_not_yet_implemented"` placeholder — this is the highest-risk case this eval exists to catch. **[D-1, D-8]**

**Gate 8:** groundedness eval passes on recorded fixtures; the stub-payload fixture from step 44 is included and passing.

---

## Stage 9 — Integration Test Suite

_Proves the whole graph, not just its parts — this is Phase 4's literal exit criteria._

45. Create `tests/integration/test_conditional_graph.py`. **[D-11]**
46. Fixture 1 — **Routine point**: leverage estimate and lower bound both well below `leverage_escalation`. Assert: only `StateMonitorNode` fires; `pressure_result` and `exploit_result` are `None`; `decision_log` shows two suppressions with correct reasons; `tactical_output.narrative` is `None` and no LLM call was made.
47. Fixture 2 — **High-leverage, low-data**: `ΔL_low ≥ threshold`, opponent sample size below `exploit_min_sample_size`. Assert: `PressureDiagnosticNode` fires, `StrategyExploitNode` is suppressed with reason `"insufficient_sample_size"`, `tactical_output` reflects a pressure-only signal.
48. Fixture 3 — **High-leverage, high-data**: `ΔL_low ≥ threshold` and sample size sufficient. Assert: all three diagnostic nodes fire, `StrategyExploitNode` returns the Stage 5 stub payload, `decision_log` shows zero suppressions, and `tactical_output` honestly reflects the stub's placeholder status rather than a fabricated recommendation.
49. Add one explicit, named assertion across all three fixtures confirming the visited node sets differ from each other — this is the literal wording of Phase 4's own exit criteria, not just an implication of three separate test functions.

**Gate 9:** all three fixtures pass; the cross-fixture node-set-differs assertion passes.

---

## Stage 10 — Full Phase 4 Verification

_The same CI gate every prior phase was held to — nothing new invented for this phase._

50. `uv run ruff check .` and `uv run ruff format --check .` — 0 errors.
51. `uv run pyright` — 0 errors.
52. `python scripts/check_file_size.py` — confirm every new `src/graph/*.py` file is under the 1,000-line ceiling.
53. `uv run pytest --cov=src --cov-report=term-missing` — full suite (units from Stages 3–7, eval from Stage 8, integration from Stage 9) green, coverage ≥ 70%.
54. Re-confirm `dvc.yaml` is unchanged (sanity re-check against Stage 1's step 10 decision, not a new action).

**Gate 10:** all of the above green. This is the point at which Phase 4 is functionally complete.

---

## Stage 11 — Documentation Closeout

55. Write `phase4_walkthrough.md`, mirroring `walkthrough.md`'s Phase 3 structure (overview, exit-criteria table, diagnostic results) — but only after Stage 10 passes, not before.
56. Formally close both audit findings at their source: correct the Phase 3/4/5 mis-numbering in `system_design.md`'s Component Inventory and `technical_roadmap.md`'s Phase 5 section (Finding A), add `graph/strategy_exploit.py` to Phase 4's Deliverables list, and update wherever the DeepEval groundedness test is scheduled so it reads "Phase 4" consistently across `phase3_ml_layer_architecture.md`, `technical_roadmap.md`, and `test_suite_report.md` (Finding B). Then mark `technical_roadmap.md`'s Phase 4 entry ✅ Complete.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify) → Stage 1 (schema+config) → Stage 2 (artifact loading)
   → Stage 3 (StateMonitorNode) → Stage 4 (PressureDiagnosticNode) → Stage 5 (StrategyExploitNode stub)
   → Stage 6 (conditional edges, diagnostic branch) → Stage 7 (TacticalOutputNode + graph compile)
   → Stage 8 (groundedness eval) → Stage 9 (integration suite) → Stage 10 (CI gate) → Stage 11 (docs)
```

56 steps, 11 gates. No implementation starts until you confirm this sequencing.
