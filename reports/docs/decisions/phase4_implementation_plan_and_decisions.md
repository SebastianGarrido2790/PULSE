# Phase 4 — Implementation Plan & Decisions

**Event-Driven Orchestration (LangGraph)**

**Product:** PULSE | **Phase:** 4 of 7 | **Version:** 0.1.0 (Draft — Pending Approval) | **Date:** 2026-08-07
**Status:** 🟡 Planning — no code written
**Authority:** `technical_roadmap.md` (Phase 4), `system_design.md` (ADR-001, ADR-003, ADR-005, ADR-005 Amendment 1), Non-Negotiable Invariants, workflow rules, `prd.md`
**Approval required from:** Sebastian, before any implementation begins — per project workflow rules: _"Plan before non-trivial work. Propose a plan, present comparative options where a real design choice exists, and wait for explicit approval before implementing."_

---

## 0. How to Read This Document

Structured like `system_design.md`'s ADR log, scoped to one phase and kept separate until finalized — the same pattern implied by the `phase3_implementation_plan_and_decisions.md` precedent referenced throughout `test_suite_report.md` and `phase3_ml_layer_architecture.md`.

- **Section 1** is the mandatory current-state audit. It drives Section 2.
- **Section 2** holds one entry per decision, each tagged:
  - 🔴 **Decision required** — a real fork exists; your input is needed.
  - 🟢 **No input required** — recorded for completeness and traceability, but the project's own constraints (a latency NFR, a Non-Negotiable Invariant, or an already-accepted ADR) leave exactly one defensible option.
- Sub-decisions are nested under the primary decision they branch from.

**Audit scope caveat, stated up front:** this conversation has PULSE's planning and architecture documentation, not the actual Phase 2/3 source files under `src/`. The audit below is therefore **spec-level** — audited against documented contracts, not a live `src/` tree. Findings that depend on something only visible in real source are marked **VERIFY**, and should be the literal first thing checked when implementation starts.

---

## 1. Current State Audit

### 1.1 Phase 4 Deliverable Files

| File                                          | Status                                                                                                                                                                            | Known interface (from docs)                                                                                                                                                          | Audit finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/graph/state_monitor.py`                  | Does not exist. Phase 4 scope per `technical_roadmap.md` and the `system_design.md` Component Inventory.                                                                          | Calls `resolve_point_win_probability()` → `p_hat`, `sample_size`, `fallback_tier`; then `compute_leverage()` and `propagate_leverage_uncertainty()` → `ΔL`, `[ΔL_low, ΔL_high]`.     | **Gap:** no document defines the node's own _output_ schema. `LeverageBandResult` is referenced by name in `test_suite_report.md` but its field list is never published. → **D-2**.                                                                                                                                                                                                                                                                                                  |
| `src/graph/pressure_diagnostic.py`            | Does not exist. Phase 4 scope.                                                                                                                                                    | Must query `PressureModelArtifact.results`, keyed `"server_id\|bucket_idx"` in `phase3_ml_layer_architecture.md`.                                                               | **Gap:** the only documented pressure function is `compute_player_pressure_deviation()`, described as part of the training pipeline. No serving-time single-lookup accessor is documented as existing. → **D-6**. Also depends on `assign_leverage_bucket()`, whose module location is never stated — only that it's used inside `scripts/train_pressure.py`'s pipeline. **VERIFY** it actually lives in `src/models/pressure_deviation.py` and not only in the training script. |
| `src/graph/strategy_exploit.py`               | Does not exist. **Scheduling is internally contradictory** (see 1.3, Finding A).                                                                                                  | Depends entirely on `core/game_theory.py`, which is Phase 5 scope and doesn't exist.                                                                                                 | → **D-1**, the central decision of this document.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `src/graph/tactical_output.py`                | Does not exist. Phase 4 scope.                                                                                                                                                    | Per system design guidelines: "a single small/cheap model," LLM call happens here only, on escalation only; no second-vendor fallback — on provider failure, return the raw structured payload. | **Gap:** no LLM provider, SDK, or model name is specified anywhere. `params.yaml` has no LLM keys yet. → **D-7**. Its DeepEval groundedness test is scheduled inconsistently across two other documents. → **D-8** (Finding B).                                                                                                                                                                                                                                                           |
| `src/graph/pulse_graph.py`                    | Does not exist. Phase 4 scope.                                                                                                                                                    | Owns conditional-edge wiring (ADR-001), and by extension artifact loading and `params.yaml` injection for every node.                                                                | Architectural center of gravity for the phase — D-2, D-3, D-5, D-9, D-10 all resolve into choices made here.                                                                                                                                                                                                                                                                                                                                                                              |
| `tests/integration/test_conditional_graph.py` | Does not exist; only the parent stub `tests/integration/__init__.py` is confirmed present, annotated "(Phase 4)" in `test_suite_report.md`, and marked "Scheduled Next". | Must prove variable node execution across ≥3 fixtures (routine / high-leverage-low-data / high-leverage-high-data), per `technical_roadmap.md` exit criteria.                        | The third fixture exercises `StrategyExploitNode` — directly downstream of D-1.                                                                                                                                                                                                                                                                                                                                                                                                           |

### 1.2 Upstream Dependencies (Already Built — Not In Scope, Treated as Stable Contracts)

All ✅ Complete per `phase3_ml_layer_architecture.md`: `core/markov_solver.py::compute_leverage`, `core/leverage_uncertainty.py::propagate_leverage_uncertainty`, `models/point_win_classifier.py::{load_stratum_table, resolve_point_win_probability}`, `models/pressure_deviation.py::{load_pressure_artifact, compute_player_pressure_deviation}`, `config/loader.py::Params`, `schemas/point_record.py::{PointRecord, MatchState}`, `utils/exceptions.py`, `utils/logger.py`. Not re-opened here.

### 1.3 Cross-Document Findings — Latent Bugs in the Plan, Not Yet in Code

**Finding A — `StrategyExploitNode` is claimed by two phases, and the mis-numbering is systematic, not a one-off typo.**
`system_design.md`'s Component Inventory lists it as `Phase 5 (module), Phase 4 (node)`. `technical_roadmap.md`'s Phase 4 conditional-edge task says "escalate to `StrategyExploitNode`... (**Phase 4 dependency**)," and Phase 4's exit criteria requires a high-leverage/high-data fixture that exercises it. But Phase 4's own **Deliverables** list omits `graph/strategy_exploit.py` entirely. Then, in Phase 5, **both** its exit criteria ("`StrategyExploitNode` from **Phase 3** wired to this module") **and** its Dependencies line ("Phase 1 (historical data), **Phase 3** (node to wire into)") point to Phase 3 for a node Phase 3 never builds — Phase 3 is the ML layer, not orchestration. Two independent occurrences of the same off-by-one strongly suggest "Phase 3" was meant to read "Phase 4" throughout. → **D-1**.

**Finding B — the `TacticalOutputNode` groundedness eval has no single home.**
`phase3_ml_layer_architecture.md` lists "DeepEval groundedness check" under "What Phase 3 does not cover... **Phase 4/5** scope." `test_suite_report.md`'s own roadmap table places it under "**Phase 6**: API, Simulation & DeepEval Quality Suite." `technical_roadmap.md` mentions it in neither Phase 4's nor Phase 6's key tasks. → **D-8**.

### 1.4 Configuration State

`params.yaml` (reviewed in full): `thresholds.leverage_escalation` (0.10) and `thresholds.exploit_min_sample_size` (30) already exist and are directly usable for Phase 4 gating — no new keys needed there. No LLM-related keys exist yet (provider, model, temperature, timeout) — pending D-7. No band-width-interaction coefficient exists — needed only if D-4 Option A is chosen.

`dvc.yaml` (reviewed in full): only `ingest`, `train_classifier`, `train_pressure`, and a placeholder `evaluate` stage exist. **No new DVC stage is needed for Phase 4** — orchestration is runtime request-handling code, not a trainable artifact-producing stage. 🟢 No input required.

---

## 2. Decisions

### D-1 🔴 `StrategyExploitNode` Scope for Phase 4

**Context:** Finding A. The graph's conditional-edge structure (ADR-001) and Phase 4's own exit criteria require a fixture that reaches a working `StrategyExploitNode`, but the game-theory math it needs (`core/game_theory.py`) is Phase 5 scope.

| Option                               | Description                                                                                                                                                                                                                                                                                                    | Trade-off                                                                                                                                                             |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Stub node in Phase 4**         | Build `graph/strategy_exploit.py` now. Runs the real sample-size sufficiency gate (ADR-003, `exploit_min_sample_size`) against real opponent data; if the gate passes, returns a structurally valid, explicitly-flagged placeholder (`status: "module_not_yet_implemented"`) instead of a real recommendation. | Fully exercisable conditional graph in Phase 4, as the roadmap's exit criteria implies. Phase 5 replaces one function body, not a node, an edge, or a test.           |
| **B — Defer entirely to Phase 5**    | Conditional edges only ever route to `PressureDiagnosticNode` this phase.                                                                                                                                                                                                                                      | Nothing gets thrown away, but Phase 4's own stated exit criteria can't be literally met — would need a formal, dated roadmap amendment, not a silent cut.             |
| **C — Pull Phase 5 forward in full** | Build the actual minimax solver now.                                                                                                                                                                                                                                                                           | Violates the roadmap's own dependency order and mixes an unrelated, higher-novelty component into this phase's review. Not a serious option; listed for completeness. |

**Proposal: Option A.** Only option that satisfies the stated exit criteria, keeps ADR-003's actually load-bearing sufficiency-gate logic real and tested now, and confines Phase 5 to a contained swap. Recommend logging this resolution back into `system_design.md` against the Component Inventory so Finding A doesn't resurface as a live ambiguity when Phase 5 starts.

---

### D-2 🔴 Graph State Schema & Node I/O Contract

**Context:** No document defines the object flowing through `pulse_graph.py`. Proposed shape (fields, not code — a Pydantic model at implementation time):

```
PulseGraphState
------------------------------------------------------------
point_context   : server_id, surface, serve_number, match_id, point_index   (input, from PointRecord)
leverage_result : ΔL, ΔL_low, ΔL_high, p_hat, sample_size, fallback_tier    (StateMonitorNode — always present)
pressure_result : PressureDeviationResult | None                            (PressureDiagnosticNode — only if fired)
exploit_result  : ExploitResult | None                                      (StrategyExploitNode — only if fired)
tactical_output : narrative text + assembled signal payload                 (TacticalOutputNode)
decision_log    : list of {node, fired: bool, reason}                       (appended by routing — see D-5)
```

**D-2a 🔴 — Pydantic `BaseModel` vs. LangGraph-idiomatic `TypedDict`.**

| Option                          | Trade-off                                                                                                                                                                                                                                                                                       |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TypedDict` (LangGraph default) | Idiomatic, frictionless with built-in reducers/checkpointing. Violates coding conventions: _"Every module boundary MUST validate input/output via Pydantic `BaseModel`. No raw `dict` parameters."_ — no validation at exactly the boundary where a malformed upstream payload is costliest to miss. |
| Pydantic `BaseModel`            | Consistent with every other module boundary in the project (`PointRecord`, `MatchState`, `StratumTable`, `PressureModelArtifact`). LangGraph supports it, but partial-update/reducer semantics need explicit handling.                                                                          |

**Proposal:** Pydantic — this is an already-stated project convention, not a fresh style preference. The reducer friction is a one-time, contained cost.

**D-2b 🔴 — representing "did this node fire."** `Optional` fields, defaulting to `None`, populated only on actual execution — never a placeholder "empty" object. Makes "did it fire" a presence check, which both `TacticalOutputNode`'s assembly (FR-7) and the groundedness check (D-8) need: nothing invented when a field is `None`.

---

### D-3 🟢 Conditional Edge Mechanics — Skip, Not No-Op

Non-Negotiable Invariants already settle this: _"Do not restructure this into a fixed pipeline where every node always executes 'for consistency.'"_ The only defensible option is `add_conditional_edges` with a routing function returning the next node name (or `END`) — an unfired node is never invoked, not invoked-and-returning-null. A no-op-but-invoked pattern would silently defeat the Sufficiency Gate. Recorded for completeness only.

---

### D-4 🔴 Confidence-Band-Aware Escalation Threshold

**Context:** `prd.md` requirements (still open): _"provisionally: wide bands should raise the effective threshold, not just wide sample-size gates."_ This phase is where the roadmap requires finalizing it.

| Option                                                | Mechanism                                                                                          | Trade-off                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Linear inflation coefficient**                  | `effective_threshold = leverage_escalation + k × (ΔL_high − ΔL_low)`, new `params.yaml` value `k`. | Literal reading of the PRD wording. `k` has no historical escalation-outcome data to calibrate against yet (Phase 7 is the first precision measurement) — arbitrary, even with a config home.                                                                                                                                                                                      |
| **B — Gate on the lower bound**                       | Escalate only if `ΔL_low ≥ leverage_escalation`.                                                   | No new parameter. A wide band pulls `ΔL_low` down, mechanically raising the bar — the PRD's rule falls out for free from infrastructure ADR-005 Amendment 1 already built. Directly operationalizes the Sufficiency Gate's own language for a one-sided decision. Marginally more conservative — acceptable given the PRD names false-escalation rate (<0.15) as a tracked metric. |
| **C — Point estimate only, band as display metadata** | Escalate on `ΔL` alone.                                                                            | Simplest, but doesn't close the open question at all.                                                                                                                                                                                                                                                                                                                              |

**Proposal: Option B.** Closes the question with zero new tunable parameters, reuses already-validated infrastructure, and is the more structural reading of the Sufficiency Gate rather than an approximation of it.

**D-4a 🔴 — apply uniformly to `PressureDiagnosticNode` and `StrategyExploitNode`'s leverage gate, or only one?** FR-4 and FR-5 both key off the same `thresholds.leverage_escalation`. **Proposal:** apply the same rule to both — two escalation semantics for one conceptual trigger, reused by two consumers, is a harder-to-audit inconsistency than any real design need justifies.

---

### D-5 🟢 Fire/Suppress Decision Logging — Routing Function, Not Node Body

FR-10 requires every escalation decision, fire _or_ suppress, logged with its triggering condition. Given D-3, a suppressed node is never invoked and structurally cannot log its own suppression. The only defensible option: logging lives in `pulse_graph.py`'s routing function(s) — the one choke point every point passes through regardless of outcome. Recommend the same routing functions open the OTel span per branch, per testing & telemetry conventions: _"Every graph run emits OTel spans for each node, including suppressed/non-fired nodes and the reason they didn't fire."_ Recorded for completeness.

---

### D-6 🔴 `PressureDiagnosticNode` Runtime Lookup — Module Ownership

| Option                                                       | Description                                                                                                                                                                               | Trade-off                                                                                                                                                                                      |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Extend `src/models/pressure_deviation.py`**            | Add `get_pressure_deviation(artifact, server_id, bucket) -> PressureDeviationResult \| None` next to `load_pressure_artifact()`, mirroring `resolve_point_win_probability()`'s precedent. | Matches an already-accepted pattern; key-construction logic (`"server_id\|bucket_idx"`) lives once, reused by both training and serving.                                                       |
| **B — Inline dict lookup in `graph/pressure_diagnostic.py`** | Node reaches into `artifact.results` directly.                                                                                                                                            | Duplicates the key-format string in two files — exactly the drift training-serving parity rules exist to prevent (stated for the classifier, but the same logic applies here). |

**Proposal: Option A.**

**Coupled VERIFY:** `assign_leverage_bucket()` is documented only as a step inside `scripts/train_pressure.py`'s pipeline — never confirmed as living in `src/`. If script-only today, `pressure_diagnostic.py` can't cleanly import it without a `src/` → `scripts/` dependency, which runs backward relative to the project's own layering. First action of implementation: confirm its location; if script-only, relocate it into `src/models/pressure_deviation.py` alongside the new accessor, and have `scripts/train_pressure.py` import it from there. 🟢 Not really a decision — only one direction respects the existing boundary — but gated on a VERIFY, so recorded here rather than in the unequivocal list.

---

### D-7 🔴 `TacticalOutputNode` LLM Provider & Invocation Pattern

**Context:** System architectural guidelines mandate "a single small/cheap model," no second-vendor fallback, deterministic raw-payload passthrough on failure — but never names a provider. No LLM keys exist in `params.yaml` yet.

| Option                                   | Trade-off                                                                                                                                                                                                                                                      |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Anthropic (Claude Haiku class)**   | Cheapest tier from the vendor already central to the certificate's own toolset and your workflow; strong instruction-following for a narrowly-scoped "phrase these numbers faithfully, invent nothing" prompt — exactly what D-8's groundedness check polices. |
| **B — OpenAI (GPT-4o-mini class)**       | Comparable cost/latency. No particular alignment with the rest of the toolchain.                                                                                                                                                                               |
| **C — Local/open-weight model (Ollama)** | Zero marginal inference cost, no external dependency. Solves a cost problem `project_charter.md` notes doesn't exist yet ("cents per escalation... negligible") at the price of new operational infrastructure.                                              |

**Proposal: Option A**, mainly for toolchain consistency and because the job here is deliberately thin — _"the LLM's role is thin enough that a deterministic passthrough is a complete, honest fallback"_ — a large model isn't needed, a cheap, reliable, instruction-following one is. This is a genuine judgment call, flagged 🔴, not a conclusion dressed up as inevitable.

**D-7a 🟢 — sync vs. async node functions, project-wide.** Not just a `tactical_output.py` question — whatever's decided sets the calling convention for all four Phase 4 nodes. Phase 6 wires this graph into FastAPI's async-native SSE/WebSocket streaming, and `TacticalOutputNode` makes the one real network call inside a <5s triggered-node budget, where blocking the event loop is a real cost. Building sync now and retrofitting in Phase 6 is avoidable rework against an already-fixed target. **Proposal:** all four nodes as `async def` from the start. Recorded for completeness — there's no real case for sync given the fixed downstream target.

---

### D-8 🔴 DeepEval Groundedness Test — Scheduling

**Context:** Finding B.

| Option                                                               | Trade-off                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Minimal version now, in Phase 4**                              | Matches the pattern already set twice: Phase 2 shipped the solver with its test alongside it; Phase 3 shipped both models with theirs. `tactical_output.py` is the only Phase 4 file calling an external LLM — shipping it with zero eval coverage leaves the phase's highest-risk file the least governed. |
| **B — Defer to Phase 6, as `test_suite_report.md` literally states** | No extra work this phase, but leaves the node ungoverned by its designated safety check for two full phases — longer exposure than the project's "fail loud, don't defer safety checks" posture elsewhere (e.g., ADR-002's zero-tolerance solver gate) suggests is comfortable.                             |

**Proposal: Option A**, scoped exactly as evaluation guidelines already scope it — one check: does the narrative introduce any number, confidence claim, or exploit recommendation absent from its input payload. Closes Finding B by amendment, not by silently picking whichever conflicting document is convenient.

---

### D-9 🟢 Artifact & Params Loading Strategy — Once, at Graph Construction

`StateMonitorNode` runs on every point under a <1s budget; the stratum table's O(1) resolution is documented as depending on being held in memory (`tier1_ml_layer_report.md`). Reloading `stratum_table.json`, `pressure_deviation.json`, and `params.yaml` from disk per point would silently violate both the latency budget and the "zero-latency inference" design intent already established in Phase 3. The only defensible option: load `StratumTable`, `PressureModelArtifact`, and `Params` once, at graph-construction time in `pulse_graph.py`, and make them available to every node from there. Recorded for completeness.

---

### D-10 🔴 Node Implementation Style — Functions + Closures, or Callable Classes

| Option                                                                        | Trade-off                                                                                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A — Plain functions + closures / `functools.partial`**                      | Matches the codebase's established style — `point_win_classifier.py` and `pressure_deviation.py` are function-based throughout (`build_stratum_table`, `resolve_point_win_probability`, `fit_bucket_prior`), no class-based wrappers anywhere in Phase 2/3. Direct fit with LangGraph's native registration. |
| **B — Callable classes** (`__init__` takes artifacts, `__call__` takes state) | More conventionally mockable in isolated unit tests. Introduces the first class-based pattern in an otherwise function-based codebase — a style inconsistency, not a technical blocker.                                                                                                                      |

**Proposal: Option A**, for consistency with established convention. Not unequivocal — B is a legitimate alternative on testability grounds — so this stays 🔴 rather than folding into D-9.

---

### D-11 🟢 Integration Test Fixtures — Static, Not Replayed

`technical_roadmap.md`'s Phase 4 exit criteria calls for "fixture match states"; `simulator/replay.py` is explicitly Phase 6 scope and doesn't exist. The only defensible option: the three required fixtures (routine / high-leverage-low-data / high-leverage-high-data) are constructed directly as `MatchState` + stratum/pressure lookup fixtures, not sourced from a replay. Recorded for completeness.

---

## 3. Decision Summary

| ID                | Title                                                      | Status                                                    |
| ----------------- | ---------------------------------------------------------- | --------------------------------------------------------- |
| D-1               | `StrategyExploitNode` scope — stub in Phase 4              | 🔴 Pending                                                |
| D-2 / D-2a / D-2b | Graph state schema — Pydantic, `Optional` fields           | 🔴 Pending                                                |
| D-3               | Conditional edges skip, don't no-op                        | 🟢 Recorded                                               |
| D-4 / D-4a        | Escalation gate on lower band bound, applied uniformly     | 🔴 Pending                                                |
| D-5               | Fire/suppress logging in routing functions                 | 🟢 Recorded                                               |
| D-6               | Pressure lookup accessor in `models/pressure_deviation.py` | 🔴 Pending (+ VERIFY `assign_leverage_bucket()` location) |
| D-7 / D-7a        | LLM provider (proposing Anthropic) + async nodes           | 🔴 Pending                                                |
| D-8               | Minimal DeepEval groundedness test, built in Phase 4       | 🔴 Pending                                                |
| D-9               | Load artifacts once, at graph construction                 | 🟢 Recorded                                               |
| D-10              | Functions + closures over callable classes                 | 🔴 Pending                                                |
| D-11              | Static fixtures, not replayed                              | 🟢 Recorded                                               |

**Proposed build order once resolved:** (1) confirm both VERIFY items against the actual `src/` tree, (2) `pulse_graph.py` state schema + artifact loading, (3) `state_monitor.py`, (4) `pressure_diagnostic.py` + its new accessor, (5) `strategy_exploit.py` stub, (6) conditional edges + routing-level logging, (7) `tactical_output.py` + minimal groundedness eval, (8) the three-fixture integration suite.

No implementation begins until the 🔴 items above are resolved.
