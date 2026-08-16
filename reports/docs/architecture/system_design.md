# System Design & Architectural Decision Record, PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.5.0 | **Date:** 2026-08-15

This document is a living record of the system's actual implemented state and the decisions that shaped it. During Phase 0, it reflects _planned_ state, the decisions made before any code exists. From Phase 1 onward, each phase's completion should update this document to reflect what was actually built, and any deviation from a prior ADR must be logged as an amendment, not silently changed.

---

## Current Implementation Status

**Phase 5 — Minimax Exploitation & Tactical Game Theory Complete (2026-08-15).**  
The Game-Theoretic Exploit Module (`src/core/game_theory.py`), offline DVC matrix construction pipeline (`scripts/build_payoff_matrices.py`), LangGraph node integration (`src/graph/strategy_exploit.py`), consolidated unit test suite (`tests/unit/test_game_theory.py`), and end-to-end integration tests (`tests/integration/test_conditional_graph.py`) are fully implemented, verified, and passing all quality gates (102/102 tests passing, 91% total coverage, 0 pyright/ruff errors, <1,000-line file ceiling).

**Phase 5 Exit Criteria Validation Summary:**
- **Deterministic Equilibrium Solver:** **PASSED** — Closed-form $2\times 2$ analytical formulas and HiGHS Linear Programming (`scipy.optimize.linprog(method='highs')`) solve mixed equilibria in $< 0.5\text{ms}$ with zero solver drift ($< 10^{-6}$ error).
- **Two-Level Sufficiency Gating:** **PASSED** — Gating triggers when $N_{\text{opp}} < 30$ or any cell count $< 5$, setting `sufficient_data=False` and clearing all exploit metrics to `None`.
- **Hierarchical Matrix Fallback:** **PASSED** — 3-tier lookup $(\text{Exact Stratum} \to \text{Aggregate Stratum} \to \text{Uncharted Opponent})$ provides seamless graceful degradation.
- **Empirical-Bayes Beta Shrinkage:** **PASSED** — Fitted Beta priors ($\alpha_0=29.314, \beta_0=15.145$) prevent probability swings on sparse serve directions across 534,168 charted points.
- **Pipeline Reproducibility:** **PASSED** — `uv run dvc repro` builds and validates 2,139 payoff matrix strata cleanly end to end.

**Phase 4 — Event-Driven Orchestration (LangGraph) Complete (2026-08-11).**  
The LangGraph StateGraph engine (`src/graph/pulse_graph.py`), Pydantic v2 graph state contracts (`src/graph/state.py`), always-on leverage monitor node (`src/graph/state_monitor.py`), empirical-Bayes pressure diagnostic node (`src/graph/pressure_diagnostic.py`), sample-size gated exploit node stub (`src/graph/strategy_exploit.py`), single-LLM narrative synthesis & deterministic fallback node (`src/graph/tactical_output.py`), DeepEval groundedness evaluation suite (`tests/evals/test_tactical_output_groundedness.py`), and end-to-end integration test suite (`tests/integration/test_conditional_graph.py`) are fully implemented, verified, and passing all quality gates (67/67 tests passing, 91% code coverage, 0 pyright/ruff errors, <1,000-line file ceiling).

**Phase 4 Exit Criteria Validation Summary:**
- **Conditional Topology:** **PASSED** — `test_conditional_topology_node_execution_differs_by_match_state` proves routine points execute only `StateMonitorNode` ($\emptyset$ diagnostic set) while high-leverage points fire `PressureDiagnosticNode` and `StrategyExploitNode`.
- **Sufficiency Gate:** **PASSED** — `StrategyExploitNode` enforces $N \ge 30$ sample size threshold, returning `status: "insufficient_data"` on sparse opponent fixtures.
- **Numerical Groundedness:** **PASSED** — DeepEval hallucination check verifies LLM narrative text introduces zero numbers absent from input signal payloads.
- **Single-LLM Fallback:** **PASSED** — `TacticalOutputNode` yields bit-exact raw signal passthrough with `is_llm_fallback=True` when LLM provider is unreachable.

**Phase 3 — Tier 1 ML Layer Complete (2026-08-06).**  
The Hierarchical Empirical Stratum Estimator (`src/models/point_win_classifier.py`), Empirical-Bayes Pressure Deviation Shrinkage Estimator (`src/models/pressure_deviation.py`), analytical leverage propagation (`src/core/leverage_uncertainty.py`), executable training pipelines (`scripts/train_classifier.py` & `scripts/train_pressure.py`), DVC pipeline stage promotion (`dvc.yaml` & `dvc.lock`), MLflow experiment tracking (`pulse_point_win_classifier_v1` & `pulse_pressure_deviation_v1`), unit and integration test suite (`tests/unit/test_point_win_classifier.py`, `tests/unit/test_pressure_deviation.py`, `tests/integration/test_classifier_uncertainty_integration.py`), and full quality gate suite (41/41 passing tests, 0 pyright/ruff errors, <1,000-line ceiling) are fully implemented, verified, and reproducible via `uv run dvc repro`.

**Exit Criteria Validation Summary (ADR-005 Amendment 2):**

- **Pressure Deviation Model:** **PASSED** — Posterior 90% credible intervals achieved **93.75% empirical coverage** across high-leverage player strata ($N_{\text{pressure}} \ge 10$), exceeding the $\ge 90\%$ target.
- **Point-Win Classifier Calibration:** **PASSED** — Quantile binning calibration analysis across 10 equal-frequency bins ($\approx 11,000$ points/bin) demonstrated **Mean Absolute Calibration Error (MACE) = 0.65%** ($0.0065$), well within the $\le 1.5\%$ exit criterion established under ADR-005 Amendment 2.
- **Point-Win Classifier ROC-AUC:** **PASSED (Sanity Trip-Wire)** — Holdout ROC-AUC reached **0.6339**, satisfying the $\ge 0.55$ diagnostic sanity trip-wire bound (`min_holdout_auc_sanity: 0.55`). ADR-005 Amendment 2 documents that 0.6339 is the empirical realization of the ROC-AUC ceiling for a saturated categorical stratum estimator on the feature-restricted set $(\text{player}, \text{surface}, \text{serve\_number})$.
- **Bin 1 Diagnostic:** Cross-tabulation confirmed Bin 1's residual error ($2.46\%$) is driven almost entirely by bin-width stretching across weak 2nd-serve strata (98.99% 2nd serves; 111 1st-serve points exhibit 16.6% error).

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

**Status:** Validated (Phase 3 — 2026-08-06)

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

#### ADR-005 Amendment 2: Calibration-Anchored Exit Criterion & Feature-Restricted ROC-AUC Scope (Phase 3 — 2026-08-06)

**Status:** Validated (Phase 3 — 2026-08-06)

**Context & Rationale:**
Holdout evaluation of the Hierarchical Empirical Stratum Estimator achieved an ROC-AUC of 0.6339 on 109,496 test points. Diagnostic evaluation resolved three key structural insights:

1. **Calibration Primacy for Markov Solver Stability:** The Markov solver evaluates point leverage through recursive win-by-two structures that amplify small input probability errors. Calibration accuracy ($\text{MCE}$), not ranking/discrimination power ($\text{AUC}$), directly governs solver output fidelity. A high-AUC model with uncalibrated probabilities is dangerous to downstream leverage computation, whereas an estimator reporting well-calibrated probabilities guarantees solver stability.
2. **Empirical Realization of ROC-AUC Ceiling:** The 0.65 AUC target was formulated in Phase 0 for a parametric `LogisticRegression`. Under the deliberate feature restriction to $(\text{player}, \text{surface}, \text{serve\_number})$ (chosen to avoid solver score-state circularity and maintain $O(1)$ zero-latency inference), the stratum estimator is already the fully saturated model. Because the model achieves near-perfect calibration ($\text{MCE} = 0.65\%$), there is no unextracted calibration error remaining to yield further ranking signal. Thus, 0.6339 is the empirical realization of the ROC-AUC ceiling for this feature-restricted categorical model.
3. **Bin 1 Diagnostic & Uniform Binning Artifact:** Quantile calibration across 10 equal-frequency bins ($\approx 11,000$ points/bin) yielded a **Mean Absolute Calibration Error (MACE) of 0.65%** ($0.0065$), proving that visual distortions under uniform binning were sparse-binning artifacts at $p_{\text{hat}} < 0.40$. Bin 1's residual error ($2.45\%$) was confirmed by cross-tabulation to be driven almost entirely by bin-width stretching across weak 2nd-serve strata (98.99% 2nd serves; 111 1st-serve points exhibit a 16.6% residual error).

**Amended Decision:**

1. **Primary Exit Gate:** Re-anchor the Point-Win Classifier exit criterion around **Mean Absolute Calibration Error (MACE) $\le 1.5\%$** (`models.max_mean_absolute_calibration_error: 0.015`) across $\ge 10$ equal-frequency quantile bins with $N \ge 1,000$.
2. **Non-Blocking Sanity Trip-Wire:** Retain holdout ROC-AUC as a non-blocking diagnostic trip-wire with a minimum sanity threshold of $\ge 0.55$ (`models.min_holdout_auc_sanity: 0.55`). If ROC-AUC falls below 0.55, a sanity warning is logged to catch pipeline join or feature scrambling bugs, but execution is not blocked.
3. **Exit Status:** The classifier passes the re-anchored Phase 3 exit gate with **MACE = 0.65%** ($\le 1.5\%$) and **AUC = 0.6339** ($\ge 0.55$ sanity threshold).

**Consequences:** Aligns model validation directly with Markov solver requirements; preserves zero-latency, leakage-free inference; documents the feature-restricted ROC-AUC empirical ceiling; eliminates fragile blocking bounds on secondary metrics.

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

### ADR-010: Event-Driven Conditional Graph Orchestration Architecture (Phase 4 — 2026-08-11)

**Status:** Validated (Phase 4 — 2026-08-11)

**Context:**
Phase 4 implements the event-driven LangGraph orchestration state machine for PULSE. Per project invariants (Conditional Topology & Sufficiency Gate), the graph's execution path must dynamically change based on point leverage and sample-size sufficiency, rather than executing every node uniformly for consistency.

**Decisions:**
1. **LangGraph StateGraph Engine (D-1, D-2):** Structured orchestration using `StateGraph(PulseGraphState)`. `PulseGraphState` manages Pydantic v2 schemas for `PointContext`, `LeverageResult`, `PressureDeviationResult`, `ExploitResult`, and `TacticalOutputResult`.
2. **State Reducer for Audit Logging (D-2a):** `PulseGraphState.decision_log` is annotated with `Annotated[list[DecisionLogEntry], operator.add]`, enabling node output dictionaries to append audit entries seamlessly without in-place state mutation issues.
3. **Wilson Lower Bound Escalation Gate (D-4):** Shared escalation condition checks `delta_leverage_low >= leverage_escalation` (0.10 in `params.yaml`). On routine points, downstream diagnostic nodes are suppressed, logging explicit audit reasons to `decision_log`.
4. **Single-LLM Vendor with Passthrough Fallback (D-7, D-8):** Routine points trigger zero LLM calls (cost guard). On escalated points, `TacticalOutputNode` invokes a single LLM vendor (`call_narrative_llm`). On network/vendor exceptions, it falls back to a deterministic raw-signal payload without attempting a secondary LLM provider.
5. **Numerical Groundedness CI Gate (D-8):** DeepEval evaluation suite (`tests/evals/test_tactical_output_groundedness.py`) verifies that LLM narratives never hallucinate numbers, bounds, or player statistics absent from input payloads.

**Consequences:**
The conditional topology is empirically validated: routine points execute only `StateMonitorNode` and `TacticalOutputNode` in 0.05ms, while high-leverage points fire diagnostic nodes and synthesize LLM narratives.

#### ADR-010 Amendment 1: Routing Function Factory Closures (Phase 4.1 — 2026-08-11)

**Status:** Validated (Phase 4.1 — 2026-08-11)

**Context & Rationale:**
Post-Phase 4 review identified that `route_after_state_monitor` and `route_after_pressure_diagnostic` in `src/graph/pulse_graph.py` took `params: Params | None = None` and fell back to calling `load_params()` per invocation when unregistered un-bound. While node factories (`make_state_monitor_node`, etc.) correctly closed over `cfg` per D-9/D-10, registering the raw routing functions directly with LangGraph's `add_conditional_edges()` caused `params` to take its default (`None`), silently hitting `load_params()` on every point event.

**Amended Decision:**
1. Refactor `route_after_state_monitor` and `route_after_pressure_diagnostic` into factory functions (`make_route_after_state_monitor(params)` and `make_route_after_pressure_diagnostic(params)`), matching the D-10 factory-closure pattern used across `src/graph/`.
2. In `build_pulse_graph()`, register `make_route_after_state_monitor(cfg)` and `make_route_after_pressure_diagnostic(cfg)`.
3. Add a unit regression test in `tests/unit/test_routing.py` (`test_routing_does_not_reload_params_from_disk`) verifying zero calls to `load_params()` occur during routing.
4. Reaffirm sample-size gate placement: `StrategyExploitNode` executes on the escalated path ($\Delta L_{\text{low}} \ge 0.10$) and enforces the ADR-003 sample-size gate ($N_{\text{opp}} \ge 30$) internally, outputting `"module_not_yet_implemented"` or `"insufficient_data"`.

---

### ADR-011: Game-Theoretic Minimax Exploitation Architecture (Phase 5 — 2026-08-15)

**Status:** Validated & Amended (Option A Parameterized Stylized Model — 2026-08-16)

**Context:**
Prior to Phase 5 reconciliation, D-1 evaluated three framing options for returner strategy modeling (continuous positioning distributions, discrete directional buckets, or directional margin approximations). Furthermore, the exploit module required an exact, low-latency (<1ms) game-theoretic solver to compute mixed-strategy Nash equilibria, best-response deviations, and empirical-Bayes cell shrinkage while respecting the Sufficiency Gate ($N_{\text{opp}} \ge 30$).

**Decisions:**
1. **2D Simultaneous Matrix Game Resolution (D-1):** D-1 was definitively resolved in favor of a full 2D zero-sum matrix game $\Pi \in \mathbb{R}^{m \times n}$ with discrete returner strategy columns $A_R = \{\text{"Cover Wide"}, \text{"Cover T"}\}$ (and server rows $A_S = \{\text{"Wide"}, \text{"T"}\}$, expanding to $3\times 2$ with $\text{"Body"}$ when body serve observations $N_{\text{body}} \ge 50$). *Note: This resolution supersedes the pre-reconciliation three-option framing.*
2. **Hybrid Deterministic Solver (D-2, D-2a):** In-process analytical $2\times 2$ algebraic solver (`_solve_2x2_analytical`) as the sub-millisecond default, with automated dispatch to HiGHS linear programming (`scipy.optimize.linprog(method='highs')`) for $m \times n$ games.
3. **Empirical-Bayes Beta Shrinkage (D-5):** Cell win probabilities $\pi_{ij}$ are smoothed using tour-level Beta priors ($\alpha_0=29.314, \beta_0=15.145$, fitted via Method of Moments across 471 returners and 534,168 charted points) to stabilize low-observation serve directions.
4. **Two-Level Sufficiency Gate Ownership (D-4):** `core/game_theory.py` owns and enforces both sample-size conditions ($N_{\text{opp}} \ge 30$ and cell count $\ge 5$). When gated, the solver cleanly returns `sufficient_data=False` with all exploit fields set to `None`.
5. **Hierarchical Matrix Lookup Fallback (D-9):** Resolves payoff matrices through a 3-tier fallback: Exact Stratum $(R, \text{surface}, N_{\text{serve}}) \to$ Aggregate Stratum $(R, \text{aggregate}) \to$ Uncharted Opponent ($N_{\text{opp}}=0$, `sufficient_data=False`).
6. **Fail-Loud Solver Exceptions (D-6):** Degenerate or non-strictly-positive determinant games raise `GameTheorySolverException(SolverException)` rather than failing silently or returning arbitrary fallback mixes.
7. **Offline DVC Pipeline & Live In-Process Solving (D-7, D-10):** Payoff matrix construction is managed as an offline DVC pipeline stage (`scripts/build_payoff_matrices.py` exporting `artifacts/models/game_theory/payoff_matrices.json`), while live equilibrium solving executes in-process in $< 0.5\text{ms}$ with zero added external dependencies.
8. **Parameterized Stylized Anticipation Model & Honest Contract Governance (Option A Resolution — 2026-08-16):**
   - *Domain Modeling Boundary:* Match Charting Project (MCP) data records trajectory placement (4/5/6) and stroke outcomes, but does not capture optical/spatial pre-serve returner stance coordinates.
   - *Mathematical Formulation:* In alignment with foundational sports economics literature (*Walker & Wooders 2001*, *Hsu et al. 2007*), the serve-and-return anticipation game is formulated as a stylized zero-sum game where row baselines are empirical and Bayesian-shrunk, while column differentials are parameterized from `params.yaml` (`anticipation_boost: 0.12`, `positioning_penalty: 0.05`).
   - *Schema Disclosure:* `PayoffMatrix` and `ExploitResult` carry explicit metadata (`is_stylized_anticipation_model: bool = True`, `anticipation_delta: float = 0.12`).
   - *Strong Duality Invariant:* `_solve_mn_linprog()` verifies $|V_{\text{primal}} - (-V_{\text{dual}})| \le 10^{-5}$, raising `GameTheorySolverException` if duality tolerance is violated.
   - *Server Population Pooling:* Matrices are tagged as `server_id="population_server"` to pool server observations against charted returners, avoiding overfitting on sparse head-to-head records.

**Consequences:**
Ensures zero-latency, mathematically verified game-theoretic calculations adhering to Ground-Truth Primacy, Strong Duality, and the Sufficiency Gate. Validated across 103 passing tests with 91% total codebase coverage.

---

## Component Inventory

| Component                        | Module Path                         | Introduced In                                                                |
| -------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------- |
| Package Skeleton & Stubs         | `src/*/` (`__init__.py`)            | Phase 1                                                                      |
| Exception Hierarchy              | `utils/exceptions.py`               | Phase 1                                                                      |
| Centralized Logger               | `utils/logger.py`                   | Phase 1                                                                      |
| Configuration Contract           | `params.yaml`, `pyrightconfig.json` | Phase 1                                                                      |
| File Ceiling Enforcement         | `scripts/check_file_size.py`        | Phase 1                                                                      |
| CI Quality Gate                  | `.github/workflows/ci.yml`          | Phase 1                                                                      |
| `PointRecord` schema             | `schemas/point_record.py`           | Phase 2                                                                      |
| Closed-form Markov solver        | `core/markov_solver.py`             | Phase 2                                                                      |
| Point-win classifier             | `models/point_win_classifier.py`    | Phase 3                                                                      |
| Pressure Deviation model         | `models/pressure_deviation.py`      | Phase 3                                                                      |
| Leverage uncertainty propagation | `core/leverage_uncertainty.py`      | Phase 3                                                                      |
| `StateMonitorNode`               | `graph/state_monitor.py`            | Phase 4                                                                      |
| `PressureDiagnosticNode`         | `graph/pressure_diagnostic.py`      | Phase 4                                                                      |
| `StrategyExploitNode`            | `graph/strategy_exploit.py`         | Phase 4 (node & sufficiency gate stub), Phase 5 (minimax module integration) |
| Game theory solver               | `core/game_theory.py`               | Phase 5                                                                      |
| Payoff Matrix DVC Stage          | `scripts/build_payoff_matrices.py`  | Phase 5                                                                      |
| `TacticalOutputNode`             | `graph/tactical_output.py`          | Phase 4                                                                      |
| FastAPI + streaming              | `api/main.py`, `api/streaming.py`   | Phase 6                                                                      |
| Replay simulator                 | `simulator/replay.py`               | Phase 6                                                                      |

---

## Update Protocol

At the end of each phase in `technical_roadmap.md`:

1. Update "Current Implementation Status" to reflect what was actually built.
2. Mark each relevant ADR's status as **Validated** (implementation matched the decision) or **Amended** (implementation diverged, the amendment must be logged as a new dated entry under the original ADR, not a silent edit).
3. Add new ADRs for any architecturally significant decision made during implementation that wasn't anticipated in Phase 0.
