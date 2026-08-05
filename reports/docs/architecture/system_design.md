# System Design & Architectural Decision Record, PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.2.0 | **Date:** 2026-08-03

This document is a living record of the system's actual implemented state and the decisions that shaped it. During Phase 0, it reflects _planned_ state, the decisions made before any code exists. From Phase 1 onward, each phase's completion should update this document to reflect what was actually built, and any deviation from a prior ADR must be logged as an amendment, not silently changed.

---

## Current Implementation Status

**Phase 2 — Data Layer & Deterministic Core Complete (2026-08-03).**  
The closed-form Markov solver (`src/core/markov_solver.py`), Wilson confidence interval propagation (`src/core/leverage_uncertainty.py`), Pydantic v2 domain model and Pandera bulk validation gate (`src/schemas/point_record.py`), parameters configuration (`params.yaml`), DVC raw data ingestion pipeline stage (`scripts/ingest.py` & `dvc.yaml`), and CI-blocking verification suite (`tests/unit/test_markov_solver.py` with `@pytest.mark.solver` $<10^{-9}$ tolerance) are fully implemented, verified, and pushed to `main`. 547,478 Match Charting Project (MCP) point records were ingested and validated into `artifacts/validated_data/points.parquet`.

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

#### ADR-005 Amendment 1: Model-Class Correction & Direct-Extreme Band Propagation (Phase 3 — 2026-08-05)

**Status:** Accepted (Amended in Phase 3 — 2026-08-05)

**Context & Rationale:**
Review of ADR-005 prior to Phase 3 model training identified two structural adjustments required for mathematical and architectural consistency:
1. **Uncertainty Band Propagation (D-0):** ADR-005 §3 originally specified propagating Wilson confidence intervals through a "Tier 2 Monte Carlo relaxation." In Phase 2 D-4, empirical review verified that the closed-form match-win probability function $M(p)$ is strictly monotonic in $p_{\text{serve}}$. Consequently, evaluating the Markov solver directly at $p_{\text{low}}$ and $p_{\text{high}}$ (direct-extreme evaluation) yields the exact analytical lower and upper leverage bounds without Monte Carlo sampling error or stochastic variance.
2. **Model Class & Stratum Estimator Correction (D-3):** ADR-005 §1 specified `LogisticRegression` + `CalibratedClassifierCV` for v1 point-win probability estimation. In practice, a logistic regression with full interaction terms ($\text{player} \times \text{surface} \times \text{serve\_number}$) behaves as a saturated categorical estimator where L2 regularization acts as an implicit, uniform prior. Replacing `LogisticRegression` with a direct **Hierarchical Empirical Stratum Estimator** is a deliberate correction, not a scope reduction:
   - It directly exposes the sample size $N$ for Wilson interval sizing per ADR-005 §2.
   - It eliminates the risk of feature leakage from score-context fields (`break_point`, `set_point`) that represent in-game states already conditioned on by the Markov solver.
   - It delegates cross-stratum smoothing to the Empirical-Bayes shrinkage estimator in the Pressure Deviation model (D-5), which performs principled Bayesian shrinkage rather than arbitrary linear blending.

**Amended Decision:**
1. **Model Class:** Replace `LogisticRegression` with a **Hierarchical Empirical Stratum Estimator**. For any point query, point-win probability $p_{\text{hat}}$ and sample size $N$ are resolved through a 4-tier fallback hierarchy:
   $$\text{Stratum } (P, S, N_{\text{serve}}) \longrightarrow \text{Player Overall } (P, N_{\text{serve}}) \longrightarrow \text{Population Surface } (S, N_{\text{serve}}) \longrightarrow \text{Global Default } p_{\text{default}}$$
2. **Band Propagation:** Reaffirm Phase 2 D-4: leverage confidence bands $[\Delta L_{\text{low}}, \Delta L_{\text{high}}]$ are computed via direct-extreme evaluation at $p_{\text{low}}$ and $p_{\text{high}}$ through `propagate_leverage_uncertainty()`. Monte Carlo sampling is formally retired for the in-process solver.

**Consequences:** Zero stochastic variance in leverage band computation; fully transparent, leakage-free prior generation for `StateMonitorNode`; explicit tier tracking (`fallback_tier`) on every inference payload.

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

### ADR-009: Input-Validation Hardening — MatchState Cross-Field Check, Config-Sourced Fallback Margin, Explicit Server-Role Field

**Status:** Accepted (Phase 2 — 2026-08-02)

> **Note:** Referenced below as "Phase 2 Decision D-5." If D-5 is already assigned in `phase2_implementation_plan_and_decisions.md`, renumber this entry to the next available slot before merging — I don't have visibility into your full decision log, only what's been shared in this conversation.

**Context:** Review of the Phase 2 implementation (`markov_solver.py`, `leverage_uncertainty.py`, `point_record.py`) ahead of Step 6 (data ingestion) surfaced three related gaps, all in the general category of "correctness that depends on an assumption the code doesn't actually enforce":

1. `MatchState` validated each point-score field independently (`0 <= x <= 4`) but not their joint validity. States like `(point_score_server=4, point_score_returner=4)` — both players simultaneously at "AD," which cannot occur in real tennis — passed construction, bypassed the explicit deuce/advantage handling in `game_prob_from_state`, and fell into the general recursive fallback in a region structurally similar to the tiebreak bug fixed in ADR-008 (margin can stay near zero while `i, j` grow before the `i>=4`-gated terminal condition fires).
2. `leverage_uncertainty.py`'s insufficient-sample fallback used a hardcoded `0.15` margin, violating the project's own "no hardcoded thresholds — source from `params.yaml`" rule.
3. `point_record.py` determined whether `server` was "player 1" via a string-pattern heuristic (`server.endswith("1")`) rather than an explicit field — a latent data-integrity risk for the ingestion pipeline about to be built in Step 6, since a player ID that happens to end in "1" without being p1 would silently swap server/returner scores with no error raised.

**Decision:**

1. Added a `model_validator(mode="after")` to `MatchState` rejecting any joint point score where one side is 4 ("AD") and the other is not exactly 3 ("40"). Verified: all valid states still construct successfully; all invalid combinations (`(4,4)`, `(4,0)`, `(4,1)`, `(4,2)`, `(0,4)`, `(1,4)`, `(2,4)`) now raise `ValidationError`; `compute_leverage` unaffected on valid input. Documented in `markov_solver_spec.md` v1.0.2 (§5.1, §6).
2. Added `uncertainty.default_fallback_margin: 0.15` to `params.yaml`. `compute_wilson_interval` and `propagate_leverage_uncertainty` now accept `fallback_margin` as an explicit parameter (default preserved for backward compatibility) instead of a hardcoded literal.
3. Added an explicit `server_is_p1: bool` field to `PointRecord`, populated at ingestion time from unambiguous source-data match metadata, not inferred from player-ID string content. `get_server_score_int()` / `get_returner_score_int()` now read this field directly. `PointRecordSchema` (pandera) updated to match.

**Consequences:** `scripts/ingest.py` (Step 6) is responsible for populating `server_is_p1` correctly at the source-data extraction boundary; it does not attempt to infer it downstream. Any raw CSV lacking this column will fail ingestion loudly (`IngestionException`) rather than falling back to a guess. This is consistent with the project's sufficiency-gate philosophy (ADR-003, ADR-005): the system does not silently proceed on an assumption it cannot verify.

**Alternatives Considered:**

- **For #1:** Raising `SolverException` from within `game_prob_from_state` on an unreachable `(i,j)` pair, rather than rejecting it earlier at `MatchState` construction — rejected because it pushes the check downstream of where the actual invariant is defined (the score state itself), and would need to be duplicated in every function that consumes raw point-count pairs rather than enforced once at the boundary.
- **For #3:** A secondary heuristic combining string matching with a length or format check — rejected as still fundamentally guessing; an explicit field set from known match metadata has no failure mode the heuristic doesn't.

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
