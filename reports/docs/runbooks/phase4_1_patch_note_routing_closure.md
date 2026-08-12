# Phase 4.1 — Patch Note: Routing Function Params Closure Fix

**Product:** PULSE | **Phase:** 4.1 (post-completion patch) | **Type:** Bug fix, no new features | **Date:** 2026-08-11
**Status:** 🟢 Applied & Verified
**Authority:** Phase 4 code review (this session), `phase4_implementation_plan_and_decisions.md` D-9 / D-10, `system_design.md` ADR-010
**Scope:** One bug, one fix. Option B selected and verified.

---

## 1. Summary

`route_after_state_monitor()` and `route_after_pressure_diagnostic()` in `src/graph/pulse_graph.py` reload `params.yaml` from disk on every point, via their `params: Params | None = None` fallback to `load_params()`. Every other artifact in the graph — `StratumTable`, `PressureModelArtifact`, and `Params` itself for all four node factories — is loaded exactly once at graph-construction time and closed over, per D-9. These two routing functions are the only place in the graph that doesn't follow that pattern, because `build_pulse_graph()` registers them with `add_conditional_edges` unbound:

```python
builder.add_conditional_edges("state_monitor", route_after_state_monitor, {...})
builder.add_conditional_edges("pressure_diagnostic", route_after_pressure_diagnostic, {...})
```

LangGraph calls a conditional-edge function as `route_fn(state)` — one positional argument. `params` never arrives, so it silently takes its `None` default on every call.

## 2. Root Cause

Not a logic error — the escalation math (`should_escalate`, the lower-bound comparison) is correct. It's a binding gap: the two routing functions were written with the same `params: Params | None = None` fallback signature used everywhere else in the codebase for standalone-callable convenience, but unlike the four node factories, they were never wrapped in a factory or `partial()` at registration time, so the fallback path — meant as a convenience for calling the function directly in a test or a script — is what actually runs in production, on every single point.

## 3. Proposed Fix

Two viable options. Recommending Option B for consistency with the rest of the codebase; Option A is the smaller diff if that's preferred instead.

### Option B (recommended) — convert both routing functions into factories, matching D-10's established pattern

Every other callable in `src/graph/` that needs bound configuration is a factory returning a closure (`make_state_monitor_node`, `make_pressure_diagnostic_node`, `make_strategy_exploit_node`, `make_tactical_output_node`). The two routing functions are currently the only exception. Bringing them in line removes the inconsistency, not just the bug.

**Before:**

```python
def route_after_state_monitor(state: PulseGraphState, params: Params | None = None) -> str:
    cfg = params if params is not None else load_params()
    threshold = cfg.thresholds.leverage_escalation
    ...
```

**After:**

```python
def make_route_after_state_monitor(params: Params) -> Callable[[PulseGraphState], str]:
    threshold = params.thresholds.leverage_escalation

    def route_after_state_monitor(state: PulseGraphState) -> str:
        lev_res = state.leverage_result
        lev_low = lev_res.delta_leverage_low if lev_res is not None else 0.0
        escalate = should_escalate(lev_res, threshold)
        ...  # unchanged fired/reason/destination + span logic
        return destination

    return route_after_state_monitor
```

Same transformation for `route_after_pressure_diagnostic` → `make_route_after_pressure_diagnostic(params)`.

**Registration changes to:**

```python
builder.add_conditional_edges("state_monitor", make_route_after_state_monitor(cfg), {...})
builder.add_conditional_edges(
    "pressure_diagnostic", make_route_after_pressure_diagnostic(cfg), {...}
)
```

`threshold` gets read from `params` once, at factory-construction time, instead of via `cfg.thresholds.leverage_escalation` on every call — a small, incidental cleanup, not the point of the fix.

### Option A (lighter touch) — bind with `functools.partial` at registration, leave function signatures untouched

```python
from functools import partial

...
builder.add_conditional_edges(
    "state_monitor",
    partial(route_after_state_monitor, params=cfg),
    {...},
)
builder.add_conditional_edges(
    "pressure_diagnostic",
    partial(route_after_pressure_diagnostic, params=cfg),
    {...},
)
```

Works identically — LangGraph still calls with `state` positionally, `params` is already bound as a keyword. Smaller diff, zero function-signature changes, but leaves the routing functions as the one place in `src/graph/` still using the optional-params-with-fallback pattern instead of the factory pattern everything else uses.

**Recommendation: Option B.** The fix is nearly the same size either way; B closes the actual inconsistency rather than papering over it, and keeps the file internally uniform for the next person reading it (or the next phase extending it, if the FR-5/ADR-003 question in §5 is ever revisited and the routing functions need to close over `stratum_table` too — B is more natural to extend for that).

## 4. Verification Plan

1. Update `tests/unit/test_routing.py`: monkeypatch `load_params` to raise if called, then invoke the routing function (built via the new factory) multiple times against synthetic states — assert `load_params` is never hit. This is the test that actually catches a regression back to the bug, not just a re-check of the escalation logic (which was already correct and already tested).
2. Re-run the existing routing unit tests unmodified — behavior doesn't change, only how `params` arrives, so all four leverage/sample-size combinations should still pass without edits.
3. Re-run `tests/integration/test_conditional_graph.py`'s three fixtures — no expected changes, this is a regression check.
4. Re-run the full Gate 10 sequence (`ruff`, `pyright`, file-size ceiling, `pytest --cov=src`) before merging.

## 5. Explicitly Out of Scope & Subsequent Resolution

- **The FR-5 / ADR-003 sample-size-gate placement question:** Reaffirmed in-node gate placement inside `StrategyExploitNode` per ADR-003/D-1, documented in `system_design.md` ADR-010.
- **The D-9 → D-8 citation mislabeling:** Resolved across `system_design.md`, `phase4_langgraph_architecture.md`, and `langgraph_orchestration_report.md`.
- **The stale routine-narrative example:** Synchronized in `langgraph_orchestration_report.md` §5.1 to match `tactical_output.py`.

## 6. Traceability

Logged back into `system_design.md` under **ADR-010 Amendment 1 (Phase 4.1 — 2026-08-11)** noting that routing functions were refactored into factory closures (`make_route_after_state_monitor`, `make_route_after_pressure_diagnostic`).

---

**Status: Approved, applied, verified (68/68 tests passing, 100% graph coverage), and committed.**
