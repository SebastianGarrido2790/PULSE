# Project Charter — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.6.5 | **Date:** 2026-08-22 | **Status:** Phase 6.5 — Interactive Presentation Layer (Tactical Cockpit)

---

## 1. End State

A production-grade, event-driven tactical intelligence system that ingests a tennis match point-by-point, computes exact leverage through a closed-form Markov chain solver validated bit-for-bit against combinatorial probability theory, and only when leverage and data-sufficiency thresholds are crossed triggers a game-theoretic exploit calculation identifying where a specific opponent's return tendencies deviate from Nash equilibrium.

The system is finished when a complete historical match can be replayed point-by-point through the live pipeline (accessible via both SSE/WebSocket streaming APIs and an embedded real-time browser cockpit), producing leverage alerts, pressure diagnostics, and tactical exploit recommendations that are each independently traceable to a persisted, versioned artifact, and when the Markov solver, the escalation logic, and the full replay are all bit-for-bit reproducible under a fixed seed from a clean checkout.

---

## 2. Audience

### Primary Users

| Persona                          | Role                             | How they interact                                                                                   |
| -------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Coach / Performance Analyst**  | In-match tactical decision-maker | Watches the live leverage stream or tactical cockpit; receives triggered pressure and exploit alerts |
| **Broadcast / Content Producer** | Editorial decision-maker         | Uses leverage spikes and visual cockpit to auto-flag turning points for commentary and highlight packages |

### Secondary Users & Evaluators

| Persona                        | Role                          | How they interact                                                                          |
| ------------------------------ | ----------------------------- | ------------------------------------------------------------------------------------------ |
| **Portfolio & Hiring Managers** | Technical/Product Evaluator   | Interacts with the real-time visual cockpit to assess product completeness, latency, and UX |
| **Technical Evaluator / MLOps** | Systems/Architecture Assessor | Audits SSE streaming performance, Wilson confidence bounds, OTel spans, and graph topology |
| **Player Development Analyst** | Training-focus decision-maker | Reviews post-match pressure-deviation reports to separate genuine weaknesses from variance |
| **Sports Data Engineer**       | Pipeline owner                | Maintains ingestion, DVC pipeline, and the historical-match replay simulator               |
| **MLOps Engineer**             | Production owner              | Maintains CI/CD, observability, container builds, and the Markov-solver correctness gate   |

---

## 3. Problem Framing

### Surface Problem

"We want to know which moments in a tennis match actually matter, and what to do about them."

### Real Engineering Problems

1. **Leverage invisibility:** "Big point" judgments are made by intuition; no mainstream tool exposes a continuously computed, mathematically exact measure of a point's impact on the match outcome.
2. **Adversary blindness:** Serve and return tactics are treated as fixed habits rather than as a simultaneous-move game against a specific, data-characterizable opponent, so tactical advice is generic rather than exploitative.
3. **Signal/noise conflation:** A player's underperformance in a high-pressure moment is indistinguishable, in most tools, from ordinary point-to-point variance, because nothing models the player's own IID baseline and measures deviation from it.
4. **Static-batch anti-pattern:** Existing analytics compute descriptive statistics after the match ends; nothing reasons conditionally, in real time, on an evolving state, which is the natural shape of a live match and the natural fit for an event-driven agentic graph rather than a one-shot report generator.

---

## 4. The ROI Situation

### Honest Assessment

This is a portfolio-stage system with no paying customer and no production data-feed access; the figures below are **illustrative, benchmark-derived estimates**, not validated savings, and are presented as such.

| Category                                           | Estimate                                                                                               | Basis                                                                                                                                               |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Manual "key moment" editorial curation (broadcast) | Hours of analyst time per match                                                                        | Illustrative, no direct measurement available at this stage                                                                                         |
| Coaching analytics subscription comparables        | Existing player-tracking/analytics products price access in the low hundreds of USD per month per team | Rough market comparable, not a validated willingness-to-pay figure for this specific system                                                         |
| LLM cost per triggered tactical output             | ~$0.01–0.05 per escalation event                                                                       | Only the `TacticalOutputNode` calls an LLM, and only on escalation, the always-on `StateMonitorNode` is pure numeric computation with zero LLM cost |
| System build cost                                  | ~13–15 developer-days                                                                                  | Full 6-phase build per the ML Canvas                                                                                                                |

### Honest Caveats

- There is no validated commercial ROI figure for this project, it is being built to demonstrate architecture and rigor, not to capture a quantified business case.
- The hardest real-world constraint is not modeling or engineering, it is **data access economics**, detailed in §6 below.
- Alert precision is an empirical target (≥0.75), not a guarantee; a coach acting on a false escalation incurs a real, if small, cost in attention and trust.
- The exploit module's value depends entirely on having enough historical data on a specific opponent, for lower-tier or infrequently charted players, the system will correctly and honestly say "insufficient data" rather than guess.

---

## 5. Definition of Done

The system is **done** when all of the following are simultaneously true:

- [ ] `dvc repro` from a clean checkout reproduces the full pipeline (data → models → solver validation → replay) without error
- [ ] The Markov solver matches closed-form combinatorial probability theory within 1e-9 tolerance, this is a CI-blocking gate, not a soft check
- [ ] `pytest` reports ≥70% line coverage with zero failures, enforced in CI
- [ ] Point-win classifier AUC ≥ configured threshold (default 0.65), calibration curve logged to MLflow
- [ ] Retrospective escalation-precision evaluation (§ML Canvas, Evaluation) meets or exceeds 0.75 on held-out historical matches
- [ ] A full historical match replayed point-by-point produces bit-identical leverage and escalation sequences across two runs with the same seed
- [ ] The exploit module correctly suppresses its output and falls back to a leverage-only alert when opponent sample size is below the configured threshold, verified by an integration test, not just documented behavior
- [ ] The embedded real-time web dashboard (`src/api/static/`) serves at `/` and `/ui`, connects to live SSE streams, and visualizes leverage curves, node firing states, and exploit matrices without external build tools
- [ ] GitHub Actions CI is green on `main` with the solver-correctness gate, coverage gate, and Trivy scan (zero CRITICAL CVEs) all passing
- [ ] A new escalation threshold can be changed in `params.yaml` and take effect via `dvc repro` without modifying Python code

---

## 6. Large-Scale Costs

Honest, order-of-magnitude figures for a company implementing this at real workload scale, not the marketing-tier pricing pages.

| Category                                                          | Real Cost                                                                                                                                                                                                         | Basis                                                                                                                                                                                                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Official live point-by-point data feed**                        | Enterprise contracts for licensed, real-time tour-level sports data are priced opaquely with no public rate card, and third-party pricing comparisons put them at roughly $10,000+/month, individually negotiated | This is the single largest real-world blocker to production deployment, not a modeling or engineering cost                                                                                                                                                 |
| **Lower-fidelity aggregator APIs**                                | Roughly $500–$1,000+/month                                                                                                                                                                                        | Materially cheaper, but these feeds generally lack the granular shot-direction data (serve wide/body/T) the exploit module depends on, cost and feature completeness trade off directly, and this project would need the official tier to work as designed |
| **LLM inference (tactical narrative synthesis)**                  | Cents per escalation event, since the LLM is called only on the minority of points that escalate, not per point                                                                                                   | Negligible at any realistic match volume                                                                                                                                                                                                                   |
| **Compute (ML training + Markov solver + game theory optimizer)** | CPU-only, no GPU required; training completes in minutes                                                                                                                                                          | Negligible                                                                                                                                                                                                                                                 |
| **Storage**                                                       | Point-level match data is small (thousands of rows per match); DVC-tracked storage is inexpensive at any realistic tour-season scale                                                                              | Negligible                                                                                                                                                                                                                                                 |

**Honest bottom line:** the engineering and ML components of this system are cheap to run at scale. The real, unresolved cost is **data access**, an official real-time feed is an enterprise sales conversation, not a self-service API key. This project deliberately scopes v1 around historical replay of public charted match data for exactly this reason, and treats live-feed integration as an explicitly out-of-scope, cost-gated future phase rather than pretending it away.

---

## 7. Technology Stack

| Layer                  | Technology                              | Rationale                                                                            |
| ---------------------- | --------------------------------------- | ------------------------------------------------------------------------------------ |
| Language               | Python 3.11+                            | `uv` for deterministic dependency management                                         |
| Package management     | `uv` + `pyproject.toml` + `uv.lock`     | Reproducible, fast                                                                   |
| ML                     | scikit-learn, LightGBM                  | Point-win classifier and shrinkage-based deviation estimator                         |
| Deterministic core     | Pure Python / NumPy                     | Closed-form Markov solver, no ML, fully unit-testable against textbook math          |
| Game theory            | `scipy.optimize.linprog`                | Minimax equilibrium via linear programming, exact, not learned                       |
| Experiment tracking    | MLflow                                  | Run lineage for the two Tier 1 models                                                |
| Pipeline orchestration | DVC                                     | Stage DAG, data versioning, `dvc repro` reproducibility                              |
| Agent framework        | LangGraph                               | Event-driven, conditional graph, nodes fire based on live state, not a fixed fan-out |
| API                    | FastAPI + Uvicorn                       | Async; SSE/WebSocket for per-point streaming                                         |
| Streaming              | Server-Sent Events + WebSocket fallback | Live leverage stream, not batch reports                                              |
| Validation             | Pydantic v2 + pandera                   | Point schema and agent output contracts                                              |
| Config                 | `params.yaml` + pydantic-settings       | Single source of truth for every threshold                                           |
| Logging                | `structlog`                             | Structured JSON logs, including _why_ a node did or didn't fire                      |
| Tracing                | OpenTelemetry                           | Component-level spans across solver, models, and graph nodes                         |
| Testing                | pytest + pytest-cov                     | Unit, integration, and the solver-correctness gate                                   |
| Containerization       | Docker (multi-stage)                    | Non-root, digest-pinned base                                                         |
| CI/CD                  | GitHub Actions                          | Coverage gate, Trivy scan, solver-correctness gate                                   |

---

## 8. Core Concepts

### Concept Map

```
Historical Point-by-Point Match Data (public charting sources)
    │
    ▼ [Pydantic + pandera validation]
PointRecord Schema
    │
    ├──────────────────────────────────────────┐
    ▼                                            ▼
Tier 1 — Point-Win Classifier          Tier 1 — Pressure Deviation Model
(calibrated, surface/player-aware)     (empirical-Bayes shrinkage vs. IID baseline)
    │                                            │
    └──────────────────┬─────────────────────────┘
                        ▼
        Tier 2 — Closed-Form Markov Solver
        (point → game → set → match, validated against combinatorial theory)
                        │
                        ▼
              Leverage(point) — exact, deterministic
                        │
                        ▼
        ┌───────────────────────────────────┐
        │   StateMonitorNode (always-on)     │
        │   runs per point, computes leverage │
        └───────────────┬────────────────────┘
                         │ leverage > threshold?
              ┌──────────┴──────────┐
              ▼                     ▼
    PressureDiagnosticNode   StrategyExploitNode
    (triggered)              (triggered, gated by
                              opponent sample size)
              │                     │
              │      Tier 2 — Game Theory Module
              │      (Nash equilibrium serve mix vs.
              │       opponent's empirical bias →
              │       best-response deviation + EV gain)
              └──────────┬──────────┘
                         ▼
              TacticalOutputNode
        (assembles whichever signals fired;
         output shape varies with match state)
                         │
                         ▼
        FastAPI SSE/WebSocket — Live Leverage & Tactical Stream
```

### Key Relationships

- **The Markov solver is the system's ground truth**, not the ML models, this is the inverse of a typical ML system, and it's what makes the correctness gate (§5) meaningful rather than cosmetic.
- **The graph topology is conditional, not fixed**, unlike a synthesis pattern where every node always runs, PULSE's downstream nodes fire only when their trigger condition is met, so the same graph produces different output shapes depending on match state.
- **The exploit module is honest about its own limits**, it does not produce a recommendation when the opponent sample size is too small, this is a design decision, not a missing feature.
- **`params.yaml`** is the single authority for every threshold, leverage escalation, sample-size gating, and latency targets are all configuration, not code.
