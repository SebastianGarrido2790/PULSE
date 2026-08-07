# Machine Learning Canvas — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.2.0 | **Date:** 2026-08-03 | **Status:** Phase 2 — Complete (Data Layer & Deterministic Core)

---

## 1. Background

### Customer Goals

Coaches, performance analysts, and broadcast teams need to know, **as a match unfolds**, which points are mathematically decisive and what a data-grounded tactical adjustment looks like, not a post-match PDF of aggregate stats. A coach watching from the box has seconds to decide whether to signal a change; a broadcaster has seconds to decide whether to cut to a graphic. Both currently rely on experience and intuition to separate a genuinely pivotal point from routine play.

### Customer Pains

| Pain                                                                                   | Severity | Root Cause                                                                                                   |
| -------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| "Big point" calls are subjective and inconsistent across analysts                      | Critical | No quantified, point-level measure of match-win impact exists in mainstream tooling                          |
| Serve/return tactics are treated as static, opponent-agnostic habits                   | Critical | No system models the server–returner interaction as the simultaneous-move game it actually is                |
| A player's poor performance under pressure is indistinguishable from ordinary variance | High     | No baseline-deviation model separates skill-consistent play from leverage-induced pressure effects           |
| Existing analytics platforms are descriptive and retrospective                         | High     | Stats are computed and published after the match; nothing reasons conditionally on live state                |
| Tactical tools either fire constantly (alert fatigue) or never (missed moments)        | Medium   | No principled escalation threshold, alerting is heuristic, not derived from the underlying probability model |

### Initial Validation

The closed-form Markov solver was validated against the standard game/set win-probability equations (win-by-two at every level: point → game → set → match). At a 55% single-point win rate, the model reproduces the well-known amplification effect where a modest point-level edge compounds into a dominant match-level edge, confirming the mathematical core before any ML or agentic layer is added.

---

## 2. Value Proposition

**Product:** A production-grade, event-driven tactical intelligence system that watches a match point-by-point, computes exact leverage in real time, detects when a player's performance is deviating from their own statistical baseline under pressure, and, only when the situation warrants it, surfaces an opponent-specific, game-theoretically grounded tactical exploit.

**Value created:**

- **Coach / Performance Analyst:** a continuously running, mathematically justified signal for _when_ a point matters and _why_, plus a concrete serve/return adjustment grounded in this specific opponent's tendencies, not generic advice.
- **Broadcast / Content Producer:** automatic, defensible identification of true turning points for commentary and highlight curation, replacing manual post-hoc review.
- **Player Development Analyst:** a data-backed way to separate genuine technical/tactical weakness from ordinary point-to-point variance, focusing training time correctly.

**Anti-patterns eliminated:**

| Anti-Pattern                                                                              | Production Fix                                                                                                                              |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Fixed-persona system fires the same analysis regardless of match state                    | Conditional, event-driven graph, nodes fire only when their trigger condition is met                                                        |
| "Big point" alerts based on heuristic score patterns (e.g., "it's break point, so alert") | Alerts driven by a continuously computed, closed-form leverage value with a configurable threshold                                          |
| Serve strategy treated as opponent-agnostic                                               | Game-theoretic exploit module explicitly conditions on the specific returner's historical positioning bias                                  |
| Single IID probability model applied uniformly                                            | Separate pressure-deviation model explicitly tests and quantifies where the IID assumption breaks down                                      |
| Batch-only, post-match analytics                                                          | Streaming state monitor reasons on live point-by-point state                                                                                |
| Alerts issued regardless of statistical confidence                                        | Data-sufficiency gate: exploit computation suppressed and gracefully degrades to leverage-only alert when opponent sample size is too small |

---

## 3. Objectives

| #   | Objective                                                              | Success Metric                                                                                                     | Priority |
| --- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- |
| O1  | Real-time leverage computation via a formally verified Markov solver   | Solver output matches closed-form combinatorial probability theory to within 1e-9                                  | Critical |
| O2  | Detect pressure-induced deviation from a player's IID baseline         | Deviation model beats a no-deviation (pure IID) baseline on held-out high-leverage points                          | Critical |
| O3  | Opponent-specific game-theoretic exploit, computed only when justified | Exploit EV gain over equilibrium mix is positive and statistically supported by sample size                        | Critical |
| O4  | Event-driven orchestration, conditional escalation, not fixed fan-out  | Graph executes variable node sets depending on match state; verified via integration tests                         | Critical |
| O5  | Full reproducibility of the mathematical core                          | Two runs on identical input state produce bit-identical leverage values                                            | High     |
| O6  | Zero hardcoded thresholds                                              | All leverage/escalation/sample-size thresholds live in `params.yaml`                                               | High     |
| O7  | Production observability                                               | OTel spans per node; structured logs for every escalation decision                                                 | High     |
| O8  | Advisory governance                                                    | System never issues autonomous commands; every output is a recommendation with a confidence/sample-size disclosure | Medium   |

---

## 4. Solution

**Core components:**

1. **Data Layer:** Pydantic-typed `PointRecord` schema (server, score state, surface, serve direction, serve number, rally length, point winner); `pandera` validation; sourced from public point-by-point charted match data; DVC-versioned.
2. **Tier 1 — ML Models:** Calibrated point-win probability classifier (`LogisticRegression` / `CalibratedClassifierCV`, surface- and player-conditioned); Pressure Deviation model, an empirical-Bayes shrinkage estimate of how far a player's realized performance departs from their own IID baseline as a function of point leverage, trained per player with shrinkage toward the population mean to handle sparse high-leverage samples.
3. **Tier 2 — Deterministic Core:** Closed-form nested Markov chain solver (point → game → set → match), unit-tested against textbook combinatorial formulas as the system's ground truth; a vectorized Monte Carlo layer relaxes the IID assumption using the Tier 1 deviation model for "what-if" distributions.
4. **Tier 2 — Game Theory Module:** Minimax/linear-programming solver computing the Nash-equilibrium serve-direction mix; compares it against a specific opponent's empirically observed return-positioning bias (from historical charted data) to compute the best-response deviation and its expected-value gain. Pure numerical optimization, no LLM involved.
5. **Tier 3 — LangGraph Event-Driven Agent:** `StateMonitorNode` runs continuously per point, computing leverage; conditional edges trigger `StrategyExploitNode` and/or `PressureDiagnosticNode` only when thresholds are crossed; `TacticalOutputNode` assembles whichever signals actually fired into a single recommendation; the output shape varies with match state, unlike a fixed-topology synthesis pattern.
6. **API:** FastAPI + SSE/WebSocket streaming, leverage values and escalation events pushed per point, not polled.
7. **Observability:** MLflow lineage for model training; OpenTelemetry spans per node; `structlog` JSON logs for every escalation decision (including _why_ a node did or didn't fire).
8. **CI/CD:** GitHub Actions; the Markov-solver-vs-closed-form equality test is a hard, non-negotiable gate, a build breaks if the simulation diverges from probability theory.

**Out of scope (v1):** live official data-feed integration (cost-prohibitive at portfolio stage, see Project Charter §6), doubles matches, video/vision-based state extraction, betting-market integration, autonomous coaching actions (advisory only).

---

## 5. Feasibility

| Dimension          | Assessment                                                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Data               | Public point-by-point charted match data (e.g., community charting projects) covers thousands of professional matches; sufficient for offline development and backtesting            |
| Deterministic core | Pure combinatorial probability; fully testable in isolation with no external dependency                                                                                              |
| ML                 | Logistic regression + shrinkage estimator well within standard scikit-learn scope                                                                                                    |
| Game theory        | Minimax via linear programming (`scipy.optimize.linprog`) is a solved, well-documented technique                                                                                     |
| LangGraph          | Conditional/event-driven graphs are a documented pattern distinct from parallel fan-out                                                                                              |
| Live data          | **Not feasible at portfolio scale** – official real-time feeds are enterprise-priced (see Charter §6); v1 uses point-by-point replay of historical matches to simulate a live stream |

**Key risks:**

| Risk                                                                                   | Mitigation                                                                                                      |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Sparse historical data for lower-tier players/opponents                                | Sample-size gate suppresses exploit computation below a configured threshold; falls back to leverage-only alert |
| Markov solver and simulation diverge under floating-point drift                        | Regression test asserts equality within fixed tolerance; CI-blocking                                            |
| Pressure Deviation model overfits to a small number of high-leverage points per player | Empirical-Bayes shrinkage toward population baseline; regularization tracked in MLflow                          |
| No access to live official feed for true real-time validation                          | Historical match replay at real-time point cadence used as a shadow-mode substitute                             |

---

## 6. Data

### Schema (Key Fields)

```
match_id: str
point_id: str (unique PK within match)
server: str (player_id)
returner: str (player_id)
surface: Literal["hard","clay","grass"]
set_score: str
game_score: str
point_score: str
serve_number: Literal[1,2]
serve_direction: Literal["wide","body","T"]
serve_speed_kmh: float | null
rally_length: int >= 0
point_winner: Literal["server","returner"]   <- classification TARGET
break_point: bool
set_point: bool
match_point: bool
leverage: float                              <- computed, not ingested (Tier 2 output)
```

### Validation Gates

- **Tier 1 (ingestion):** column presence, score-state consistency (game/set scores must be valid tennis states), no orphaned points, chronological ordering within a match.
- **Tier 2 (pandera):** `point_winner` ∈ {server, returner}, `serve_direction` ∈ {wide, body, T}, `point_id` uniqueness within `match_id`, score progression validity.

---

## 7. Metrics

### ML / Mathematical Metrics (Diagnostic)

| Metric                              | Component                | Threshold                                                                         |
| ----------------------------------- | ------------------------ | --------------------------------------------------------------------------------- |
| Solver-vs-closed-form deviation     | Markov solver            | < 1e-9 (CI-blocking)                                                              |
| AUC-ROC, calibration (Brier score)  | Point-win classifier     | AUC ≥ 0.65 (point-level prediction is inherently noisier than aggregate outcomes) |
| Shrinkage interval coverage         | Pressure Deviation model | ≥ 90% nominal coverage on held-out high-leverage points                           |
| Exploit EV-gain confidence interval | Game theory module       | Lower bound > 0 before an exploit is surfaced                                     |

### Business / Product Metrics (Production Gate)

| Metric                                                                                                      | Target                                                          |
| ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Alert precision (leverage escalation coincides with a real win-probability swing, retrospectively verified) | ≥ 0.75                                                          |
| State Monitor latency (per point)                                                                           | < 1 second                                                      |
| Triggered-node latency (Strategy/Pressure)                                                                  | < 5 seconds                                                     |
| False-escalation rate                                                                                       | < 0.15                                                          |
| Exploit-eligible coverage (fraction of high-leverage points with sufficient opponent data)                  | Tracked, not gated, expected to be low early and grow with data |

---

## 8. Evaluation

### Offline

| Component                       | Method                                                                                                                                                                                                                   | Criterion                                       |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| Markov solver                   | Unit tests against textbook combinatorial formulas                                                                                                                                                                       | Exact numeric equality within tolerance         |
| Point-win classifier            | AUC, calibration curve on 25% hold-out                                                                                                                                                                                   | AUC ≥ 0.65; calibration on-diagonal             |
| Pressure Deviation model        | Interval coverage on held-out high-leverage points                                                                                                                                                                       | ≥ 90% coverage                                  |
| Game theory module              | Unit tests: equilibrium mix sums to 1, is indifference-inducing for the returner                                                                                                                                         | Pass                                            |
| Escalation logic (novel method) | Retrospective ground truth: recompute leverage _after_ the match using the realized outcome via the same closed-form solver, then check whether the live (pre-outcome) escalation correctly flagged the point in advance | Precision/recall ≥ target                       |
| Full pipeline reproducibility   | Two point-by-point replays of the same match                                                                                                                                                                             | Bit-identical leverage and escalation sequences |

### Online (Shadow Mode)

- Historical matches replayed point-by-point at real-time cadence to simulate a live feed, since no production access to an official real-time provider exists at this stage
- Track alert precision and false-escalation rate across replayed matches
- Monitor Pressure Deviation calibration drift per player as more matches accumulate

---

## 9. Modeling

### Iteration Plan

1. **Baseline:** Empirical average point-win rate per player/surface establishes the floor
2. **v1:** Calibrated logistic regression conditioned on surface, serve number, and player serve statistics
3. **v2 (if v1 underperforms):** Gradient-boosted trees (LightGBM) for the point-win classifier
4. **Pressure Deviation v1:** Empirical-Bayes shrinkage estimator, no covariates beyond leverage bucket
5. **Pressure Deviation v2 (optional):** Hierarchical model with player-level and leverage-level random effects, if sample sizes support it

### Feature Engineering

- Categorical: `OneHotEncoding(handle_unknown='ignore')` for surface, serve direction
- Score-state features engineered from raw score strings (games/sets remaining, distance from deuce, break-point flags)
- Leverage itself is never used as an _input_ to the point-win classifier, it is a downstream, independently derived quantity, and using it upstream would leak the outcome it's meant to explain

---

## 10. Inference

| Stage                                        | Mode                              | Latency Target    |
| -------------------------------------------- | --------------------------------- | ----------------- |
| Data ingestion + validation                  | Batch (DVC stage)                 | Seconds           |
| Model training (both Tier 1 models)          | Batch (DVC stage, on data change) | < 5 min           |
| StateMonitorNode (leverage computation)      | Streaming, per point              | < 1 second        |
| StrategyExploitNode / PressureDiagnosticNode | On-demand, triggered              | < 5 seconds       |
| Full match replay (shadow mode)              | Streaming simulation              | Real-time cadence |

Models loaded once at API startup; the Markov solver and game-theory optimizer are pure computation, not model artifacts.

---

## 11. Feedback

| Source                                | Signal                                                                                 | Use                                             |
| ------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Retrospective leverage-swing labeling | Auto-generated ground truth from realized match outcomes (no manual labeling required) | Escalation-logic precision/recall evaluation    |
| Coach/analyst flags on live alerts    | False positive/negative marking                                                        | Threshold and model refinement                  |
| Pressure Deviation calibration drift  | Rolling per-player calibration error                                                   | Retrain trigger                                 |
| Exploit-eligible coverage growth      | Tracked over time as data accumulates                                                  | Signals when the cold-start gate can be relaxed |

---

## 12. Project

### Deliverables by Phase

| Phase | Deliverable                                                                    | Status         |
| ----- | ------------------------------------------------------------------------------ | -------------- |
| 0     | Planning docs (Canvas, Charter, PRD, User Story, Roadmap, ADR)                 | ✅ Complete    |
| 1     | Project Scaffolding (repo structure, dependencies, CI/CD, line-ceiling gate)   | ✅ Complete    |
| 2     | Data schema, validation, closed-form Markov solver + ground-truth unit tests   | ✅ Complete    |
| 3     | Tier 1 ML models (point-win classifier, pressure deviation estimator) + MLflow | ✅ Complete    |
| 4     | Event-driven LangGraph orchestration (StateMonitor + conditional nodes)        | 🛠️ In Progress |
| 5     | Game-theoretic exploit module (Nash equilibrium + best-response deviation)     | ⬜ Pending     |
| 6     | FastAPI + SSE/WebSocket streaming interface, match-replay simulator            | ⬜ Pending     |

### Timeline Estimate

| Phase                          | Duration        |
| ------------------------------ | --------------- |
| 0 — Planning                   | 1 day           |
| 1 — Solver + Scaffolding       | 2 days          |
| 2 — Tier 1 ML                  | 2–3 days        |
| 3 — Event-Driven Orchestration | 2–3 days        |
| 4 — Game Theory Module         | 2 days          |
| 5 — API + Streaming            | 2 days          |
| 6 — Infra + CI                 | 1–2 days        |
| **Total**                      | **~13–15 days** |
