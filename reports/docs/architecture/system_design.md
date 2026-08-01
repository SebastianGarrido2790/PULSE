# System Design & Architectural Decision Record, PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.1.0 | **Date:** 2026-07-20

This document is a living record of the system's actual implemented state and the decisions that shaped it. During Phase 0, it reflects _planned_ state, the decisions made before any code exists. From Phase 1 onward, each phase's completion should update this document to reflect what was actually built, and any deviation from a prior ADR must be logged as an amendment, not silently changed.

---

## Current Implementation Status

**Phase 1 — Project Scaffolding Complete (2026-07-29).**  
The repository architecture, dependency environment (`pyproject.toml`, `uv`), static type configuration (`pyrightconfig.json`), operational threshold parameters (`params.yaml`), DVC pipeline skeleton (`dvc.yaml`), file-size ceiling checker (`scripts/check_file_size.py`), local pre-commit hooks (`.pre-commit-config.yaml`), GitHub Actions CI workflow (`.github/workflows/ci.yml`), and package subdirectories (`src/api`, `src/schemas`, `src/core`, `src/models`, `src/graph`, `src/simulator`, `src/utils`, `src/config`, `tests/unit`, `tests/integration`, `tests/evals`) are fully established, verified, and pushed to `main`.

---

## ADR Log

### ADR-001: Event-Driven Conditional Graph over Parallel Fan-Out Synthesis

**Status:** Accepted (Phase 0)

**Context:** A tennis match is a live, sequential process with a single evolving state, not a static decision compared across fixed stakeholder perspectives. A graph architecture where every node always runs and a synthesis node reconciles them would misrepresent the domain, most points require no deep analysis at all.

**Decision:** `StateMonitorNode` runs on every point. `PressureDiagnosticNode` and `StrategyExploitNode` run only when their respective trigger conditions are met. `TacticalOutputNode` assembles whichever signals actually fired, producing a variable-shape output.

**Consequences:** Requires conditional-edge support in LangGraph and integration tests that verify different node sets fire under different fixtures, not just that the graph runs. Logging must capture _why_ a node did or didn't fire (see FR-10).

**Alternatives Considered:** Fixed parallel fan-out with a synthesis node, rejected as architecturally dishonest to a single-timeline, single-agent monitoring problem.

---

### ADR-002: Closed-Form Markov Solver as Ground Truth and Hard CI Gate

**Status:** Accepted (Phase 0)

**Context:** Unlike most business decision-support systems, this domain has an exact, textbook-derivable mathematical answer for win probability at any score state. That is a rare opportunity to validate the system against verifiable truth rather than internal consistency alone.

**Decision:** The closed-form Markov solver, not any ML model, is the system's ground truth. Its output must match combinatorial probability theory within 1e-9 tolerance, enforced as a CI-blocking test, a build breaks if this drifts, with no exceptions.

**Consequences:** Leverage is computed deterministically from `p`, not learned end-to-end. All ML uncertainty enters _upstream_, in the estimation of `p` itself (see ADR-005), never in the solver logic.

**Alternatives Considered:** Learning leverage directly via a trained model, rejected; it would discard a verifiable mathematical structure in favor of an opaque approximation of something already exactly solvable.

---

### ADR-003: Data-Sufficiency Gating for the Exploit Module

**Status:** Accepted (Phase 0)

**Context:** Opponent-specific historical data is sparse for lower-tier or infrequently charted players. A system that computes an exploit recommendation regardless of sample size would produce confident-sounding advice with no statistical basis.

**Decision:** `StrategyExploitNode` checks opponent sample size against a configured minimum before computing a recommendation. Below the threshold, it returns an explicit "insufficient data" result and the system falls back to a leverage-only alert.

**Consequences:** Requires an integration test proving this fallback path, not just documentation of intended behavior (PRD FR-6). Establishes a design invariant, see ADR-005, which extends the same principle to the leverage computation itself.

**Alternatives Considered:** Always producing a best-effort recommendation with a caveat, rejected; a caveat buried in text is weaker than a structurally enforced gate, and is more likely to be ignored under time pressure at a changeover.

---

### ADR-004: V1 Scope Excludes Live Official Data Feed

**Status:** Accepted (Phase 0)

**Context:** Licensed, real-time, tour-level point-by-point data feeds are enterprise-priced with opaque, individually negotiated contracts (see `project_charter.md` §6). This is not a modeling or engineering constraint, it is a data-access economics constraint outside this project's scope to solve.

**Decision:** V1 uses historical point-by-point charted match data, replayed at real-time cadence to simulate a live stream. Live official feed integration is explicitly deferred as a future, cost-gated phase.

**Consequences:** All "real-time" claims in this project refer to processing latency against a replayed stream, not a genuinely live match. This distinction is stated explicitly wherever performance is discussed, to avoid overclaiming.

**Alternatives Considered:** Using a lower-cost, lower-fidelity aggregator API, rejected for v1, because these feeds generally lack the granular serve-direction data the exploit module depends on; documented as a possible future trade-off, not a solution.

---

### ADR-005: Tier 1 Point-Win Probability - Retain Calibrated Logistic Regression as v1 Point Estimate, Add Wilson-Interval Uncertainty Propagation

**Status:** Accepted (Phase 0)

**Context:** Because leverage is computed through a nested, win-by-two Markov structure at every level (point → game → set → match), small calibration errors in `p` are actively amplified, not merely carried forward proportionally. At the same time, `p` itself is estimated from historical data with widely varying sample sizes across players, heavily charted top-tier players versus sparsely charted lower-tier players. As designed prior to this ADR, the system emitted a single point value for leverage regardless of how much data backed the underlying `p`, which is inconsistent with the sample-size honesty already required of the exploit module (ADR-003).

There is empirical precedent that a simple, low-parameter probability model tracks real point-win outcomes closely in this domain, e.g., first-serve win rate alone predicting hold rate within a fraction of a percentage point in known cases, supporting logistic regression as a legitimate v1 choice rather than a placeholder.

**Decision:**

1. Retain `LogisticRegression` + `CalibratedClassifierCV` as the v1 point-win probability model.
2. Attach a Wilson (or Jeffreys) confidence interval to `p`, sized by the observation count backing it (per player × surface × serve-number stratum).
3. Propagate that interval through the Tier 2 Monte Carlo relaxation to produce a **leverage confidence band**, not a point value, as the value surfaced to `StateMonitorNode`.
4. Escalation logic (Phase 3) must account for band width, not just the point estimate, provisionally, wide bands raise the effective threshold required to escalate.

**Consequences:** Couples this decision to ADR-003 as a shared design invariant: _the system does not emit a confident-sounding signal it cannot statistically support._ Adds a defined scope item to Phase 2 (`technical_roadmap.md`) rather than deferring it. Requires `StateMonitorNode`'s output schema to carry an uncertainty field from the outset, avoiding a breaking schema change later.

**Alternatives Considered:**

- **Full hierarchical Bayesian / Beta-Binomial pooled model** (partial pooling across player × surface × serve-number strata), architecturally more consistent, since the Pressure Deviation model already uses shrinkage, and would replace the point-estimate-plus-bolted-on-interval approach with a single coherent posterior. Deferred to v2 as a documented candidate: higher implementation and inference complexity, not justified before v1 validates the simpler approach end-to-end.
- **No uncertainty handling at all**, rejected as inconsistent with ADR-003 and with the amplification argument above.

---

### ADR-006: Calibration Method - Platt (v1) vs. Isotonic (v2 if LightGBM Is Adopted)

**Status:** Accepted (Phase 0)

**Context:** `CalibratedClassifierCV` defaults to sigmoid (Platt) calibration unless `method='isotonic'` is specified. Platt calibration assumes miscalibration is sigmoid-shaped, a reasonable assumption for logistic regression's typically near-calibrated raw outputs, but a poor fit for gradient-boosted trees, which are reliably overconfident in ways a single sigmoid correction does not capture well.

**Decision:** `calibration_method` is an explicit, required field in `params.yaml`, never left at the library default. Set to `sigmoid` for the v1 logistic regression model. If a v2 LightGBM model is adopted (per the iteration plan in `ml_canvas.md` §9), `calibration_method` must be set to `isotonic` as part of that change, not inherited silently.

**Consequences:** Any future model swap must include an explicit calibration-method review as part of the change, not just a model-class swap. This is enforced by making the field required rather than optional in the config schema.

**Alternatives Considered:** Temperature scaling, noted as a viable alternative primarily for neural network outputs; not applicable to the linear/tree-based models in this project's scope.

---

### ADR-007: Phase 1 Production Scaffolding Architecture & Quality Gate Strategy

**Status:** Validated (Phase 1 — 2026-07-29)

**Context:** The production system requires an unshakeable foundation before implementing the deterministic mathematical core. Standardizing dependency resolution (`uv`), static type enforcement (`pyright`), code formatting (`ruff`), operational threshold contracts (`params.yaml`), modular directory structure, file-size ceilings (`scripts/check_file_size.py`), and CI pipelines (`.github/workflows/ci.yml`) is necessary to prevent technical debt and ensure strict reproducibility.

**Decision:**

1. Enforce strict `uv` package management with Python 3.11+ target.
2. Maintain `pyrightconfig.json` in root with standard mode type enforcement across `src/` and `tests/`.
3. Centralize all threshold parameters, latency budgets, and model configuration names in namespaced `params.yaml`.
4. Implement `scripts/check_file_size.py` to enforce a CI-blocking 1,000-line limit per Python file under `src/` (§5.1 of project constitution).
5. Establish a single sequential GitHub Actions CI workflow (`quality-gate`) executing ruff, pyright, line ceiling checks, and pytest.
6. Adopt docstring-only `__init__.py` files across all package subdirectories to prevent circular imports.

**Consequences:** Any code addition must pass static typing, linting, formatting, and file-size ceiling checks before merging. Ensures zero circular imports and complete environment reproducibility across machines.

**Alternatives Considered:** Multi-job parallel CI workflow (rejected: higher cost and complex logs), including Pyright in pre-commit hooks (rejected: 10s delay on local commits; reserved for CI).

---

### ADR-008: Correction to Tiebreak Sudden-Death Handling — Closed-Form Deuce Tail Replaces Flawed Block Shortcut

**Status:** Accepted (Phase 2 — 2026-08-01)

**Context:** Spec review of `markov_solver_spec.md` v1.0.0 §3.2 found the "two-serve sub-game" shortcut for tiebreak states beyond 6-6 was incorrect: it assumed a fresh alternating 2-2 serve block restarts exactly at the tie, but the true point-numbering shows the first post-6-6 point is the _second_ point of an already-half-played block, not the start of a fresh one. The v1.0.0 draft also never defined terminal states beyond the initial race to 7 (e.g. 8-6, 9-7), relying entirely on the flawed shortcut to stand in for them.

The first candidate fix — extending the terminal condition to `max(i,j) >= 7 and abs(i-j) >= 2` and continuing plain point-by-point recursion past 6-6 — was mathematically valid but empirically found operationally unsound: a memoized top-down implementation raised `RecursionError` even with `sys.setrecursionlimit(100_000)`, because depth-first evaluation of near-tied oscillating paths requires resolving arbitrarily deep call chains before backtracking.

**Decision:** Replace both the flawed shortcut and the "extend recursion" candidate with a correctly-derived closed form for the tail beyond any tied state N-N (N >= 6):

```
t_tail(p_A, p_B) = (p_A * p_B) / (1 - p_A - p_B + 2 * p_A * p_B)
```

This value is provably identical regardless of which player serves the next point (a genuine symmetry of the alternation structure, not an approximation), and was cross-validated against an independent bottom-up dynamic-programming implementation to 10 decimal places across multiple asymmetric `(p_A, p_B)` pairs, at both possible next-server assignments, and for both the 7-point and 10-point (match) tiebreak formats. Point-by-point recursion is retained only for the bounded region 0-0 through 6-6 (at most 12 points), where it is trivially shallow and requires no recursion-depth mitigation.

**Consequences:** `markov_solver_spec.md` bumped to v1.0.1. The `next_server(n)` alternation rule, previously left as prose, is now given as an explicit formula to prevent the same class of error recurring. No other component is affected — this correction was caught during spec review, before `markov_solver.py` implementation began, so no downstream code required rework.

**Alternatives Considered:**

- **Extend the recursive terminal condition and rely on `sys.setrecursionlimit`** — rejected after empirical testing showed `RecursionError` persists even at a limit of 100,000, since the true worst-case depth for near-tied paths is effectively unbounded, not just large.
- **Bottom-up DP with a large finite cap, treating the residual tail as negligible** — rejected in favor of the exact closed form; a capped DP is not a true approximation-free solution and would sit awkwardly against this project's "not a simulation, all outputs are exact" invariant (ADR-002) even though the residual error would be practically negligible.

---

## Component Inventory

| Component                        | Module Path                         | Introduced In                    |
| -------------------------------- | ----------------------------------- | -------------------------------- |
| Package Skeleton & Stubs         | `src/*/` (`__init__.py`)            | Phase 1                          |
| Exception Hierarchy              | `utils/exceptions.py`               | Phase 1                          |
| Centralized Logger               | `utils/logger.py`                   | Phase 1                          |
| Configuration Contract           | `params.yaml`, `pyrightconfig.json` | Phase 1                          |
| File Ceiling Enforcement         | `scripts/check_file_size.py`        | Phase 1                          |
| CI Quality Gate                  | `.github/workflows/ci.yml`          | Phase 1                          |
| `PointRecord` schema             | `schemas/point_record.py`           | Phase 2                          |
| Closed-form Markov solver        | `core/markov_solver.py`             | Phase 2                          |
| Point-win classifier             | `models/point_win_classifier.py`    | Phase 3                          |
| Pressure Deviation model         | `models/pressure_deviation.py`      | Phase 3                          |
| Leverage uncertainty propagation | `core/leverage_uncertainty.py`      | Phase 3                          |
| `StateMonitorNode`               | `graph/state_monitor.py`            | Phase 4                          |
| `PressureDiagnosticNode`         | `graph/pressure_diagnostic.py`      | Phase 4                          |
| `StrategyExploitNode`            | `graph/strategy_exploit.py`         | Phase 5 (module), Phase 4 (node) |
| Game theory solver               | `core/game_theory.py`               | Phase 5                          |
| `TacticalOutputNode`             | `graph/tactical_output.py`          | Phase 4                          |
| FastAPI + streaming              | `api/main.py`, `api/streaming.py`   | Phase 6                          |
| Replay simulator                 | `simulator/replay.py`               | Phase 6                          |

---

## Update Protocol

At the end of each phase in `technical_roadmap.md`:

1. Update "Current Implementation Status" to reflect what was actually built.
2. Mark each relevant ADR's status as **Validated** (implementation matched the decision) or **Amended** (implementation diverged, the amendment must be logged as a new dated entry under the original ADR, not a silent edit).
3. Add new ADRs for any architecturally significant decision made during implementation that wasn't anticipated in Phase 0.
