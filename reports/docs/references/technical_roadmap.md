# Technical Roadmap — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.6.5 | **Date:** 2026-08-22

This roadmap sequences implementation so that the deterministic ground truth (Phase 1) exists and is verified before any ML or agentic layer is built on top of it, consistent with the principle that PULSE's mathematical core, not its models, is the system's source of truth.

---

## Phase 0 — Planning ✅ Complete

**Deliverables:** `pulse_ml_canvas.md`, `pulse_project_charter.md`, `prd.md`, `user_story.md`, `technical_roadmap.md` (this document), `system_design.md`.

---

## Phase 1 — Project Scaffolding ✅ Complete

**Goal:** Establish the production repository structure, dependency environment (`uv`, `pyproject.toml`), code-quality tooling (`ruff`, `pyright`, `pre-commit`), CI/CD baseline (GitHub Actions), and line-ceiling enforcement (`scripts/check_file_size.py`) to serve as the foundation for the deterministic mathematical core.

**Key Tasks:**

- Instantiate production directory layout per project constitution (§4): `src/api`, `src/schemas`, `src/core`, `src/models`, `src/graph`, `src/simulator`, `src/utils`, `src/config`.
- Configure `pyproject.toml` dependencies with `uv` package management (`pydantic>=2.0`, `langgraph`, `scikit-learn`, `scipy`, `pandera`, `dvc`, `mlflow`, `deepeval`, `fastapi`, `pytest`, `ruff`, `pyright`).
- Setup `params.yaml` baseline with quantitative threshold parameters (`leverage_escalation_threshold`, `exploit_min_sample_size`, `latency_budget_ms`).
- Establish `scripts/check_file_size.py` with 1,000-line hard ceiling check and `ALLOWLIST` enforcement.
- Setup `.pre-commit-config.yaml` and `.github/workflows/ci.yml` CI pipeline (linting, type-checking, file-size enforcement, solver correctness test gate).

**Deliverables:** Updated `technical_roadmap.md`, production directory structure specification, `pyproject.toml`, `params.yaml` base configuration.

**Exit Criteria:** `technical_roadmap.md` Phase 1 fully defined and validated; workspace architecture established without code implementation.

**Dependencies:** Phase 0 Complete.

**Est. Duration:** 1 day

---

## Phase 2 — Data Layer & Deterministic Core ✅ Complete

**Goal:** Establish the `PointRecord` schema, ingestion/validation pipeline, and the closed-form Markov solver the system's ground truth, before any model is trained against it.

**Key Tasks:**

- Define `PointRecord` (Pydantic v2) and `pandera` validation gates per `ml_canvas.md` §6
- Write component specifications (`reports/specs/markov_solver_spec.md` and `reports/specs/game_theory_spec.md`) for the highest-novelty deterministic components
- Implement the closed-form Markov solver (point → game → set → match)
- Write golden-value unit tests comparing solver output to textbook combinatorial formulas (win-4-0, win-4-1, win-4-2, win-via-deuce paths)
- Implement observation-count tracking per player/surface/serve-number stratum, needed for the Wilson-interval uncertainty layer in Phase 2 (ADR-005)
- Set up `params.yaml` with initial threshold placeholders (leverage, sample size) values TBD pending Phase 2/3 calibration
- DVC-track the raw and validated data stages

**Deliverables:** `schemas/point_record.py`, `core/markov_solver.py`, `tests/test_markov_solver.py` (CI-blocking gate), `specs/markov_solver_spec.md`, `specs/game_theory_spec.md`, `params.yaml` v0.1

**Exit Criteria:** Solver matches closed-form theory within 1e-9 tolerance on all tested paths; `pandera` gates reject malformed records; `dvc repro` runs the ingestion stage end-to-end.

**Dependencies:** None (foundational phase).

**Est. Duration:** 2 days

---

## Phase 3 — Tier 1 ML Layer ✅ Complete

**Goal:** Build the calibrated point-win probability model and the pressure-deviation estimator, both with explicit uncertainty handling per ADR-005 and ADR-006.

**Key Tasks:**

- Train v1 point-win classifier: `LogisticRegression` + `CalibratedClassifierCV(method='sigmoid')`, explicit in `params.yaml`
- Implement Wilson (or Jeffreys) confidence interval on `p`, keyed to the observation count from Phase 1
- Implement the Pressure Deviation model as an empirical-Bayes shrinkage estimator, per-player, shrinking toward the population baseline as a function of leverage bucket
- Extend the Tier 2 Monte Carlo layer to propagate the `p` confidence interval through the Markov solver, producing a leverage confidence band rather than a point value
- Log both models and their calibration curves to MLflow
- Add the calibration-method decision (Platt now, isotonic if/when LightGBM v2 is adopted) as an explicit, tested config path, not a default fallen into silently

**Deliverables:** `models/point_win_classifier.py`, `models/pressure_deviation.py`, `core/leverage_uncertainty.py`, MLflow experiment log

**Exit Criteria:** Classifier AUC ≥ 0.65 on hold-out; Pressure Deviation shrinkage intervals achieve ≥90% nominal coverage; leverage confidence bands are produced end-to-end for a sample match.

**Dependencies:** Phase 1 (schema, observation counts, solver).

**Est. Duration:** 2–3 days

---

## Phase 4 — Event-Driven Orchestration (LangGraph) ✅ Complete

**Goal:** Implement the conditional graph: `StateMonitorNode` always-on, `PressureDiagnosticNode` and `StrategyExploitNode` triggered, `TacticalOutputNode` assembling whichever fired.

**Key Tasks:**

- Implement `StateMonitorNode`: per-point leverage + confidence band computation, threshold check against `params.yaml`
- Implement conditional edges: escalate to `PressureDiagnosticNode` on leverage threshold; escalate to `StrategyExploitNode` on leverage threshold **and** sample-size gate (Phase 4 dependency)
- Finalize how confidence-band width interacts with the escalation threshold (open question from `prd.md` §10), provisional rule: wide bands raise the effective threshold required to trigger
- Implement `TacticalOutputNode` with variable output shape depending on which upstream nodes fired, calling ultra-fast free-tier Groq Cloud (`llama-3.1-8b-instant`) or Anthropic with deterministic raw-signal passthrough fallback
- Structured logging of every fire/suppress decision with its triggering condition (FR-10)
- Integration tests verifying the graph produces different node sets for different match-state fixtures

**Deliverables:** `graph/state_monitor.py`, `graph/pressure_diagnostic.py`, `graph/strategy_exploit.py`, `graph/tactical_output.py`, `graph/pulse_graph.py`, `graph/llm_client.py`, integration test suite

**Exit Criteria:** Graph correctly varies its execution path across a set of fixture match states (routine point, high-leverage/low-data point, high-leverage/high-data point); all decisions logged.

**Dependencies:** Phase 2 (leverage + confidence bands).

**Est. Duration:** 2–3 days

---

## Phase 5 — Game-Theoretic Exploit Module ✅ Complete

**Goal:** Implement the Nash-equilibrium serve-direction solver and the opponent-specific best-response deviation calculation, with the sample-size gate as a hard, tested requirement.

**Key Tasks:**

- Implement hybrid minimax equilibrium solver via $2\times 2$ analytical formulas and `scipy.optimize.linprog(method='highs')`
- Build DVC data pipeline stage (`scripts/build_payoff_matrices.py`) extracting returner-positioning payoff matrices with Empirical-Bayes Beta shrinkage ($\alpha_0=29.314, \beta_0=15.145$)
- Implement pure best-response deviation and expected-value gain calculation ($\delta \ge 0$)
- Implement two-level sample-size sufficiency gate ($N_{\text{opp}} \ge 30$, cell counts $\ge 5$) with hierarchical stratum fallback
- Unit tests & golden-value properties: simplex sums, indifference induction, non-negative $\delta$, closed-form vs LP agreement, symmetric uniform equilibrium
- Wire `StrategyExploitNode` into LangGraph orchestration graph with zero-overhead in-process solving

**Deliverables:** `src/core/game_theory.py`, `scripts/build_payoff_matrices.py`, `tests/unit/test_game_theory.py`, `artifacts/models/game_theory/payoff_matrices.json`, `reports/docs/evaluations/game_theory_report.md`

**Exit Criteria:** Solver passes all 9 specification unit tests; sample-size gate verified via integration tests (FR-6); `StrategyExploitNode` wired and passing 102/102 test suite gates.

**Dependencies:** Phase 2 (historical data), Phase 4 (node to wire into).

**Est. Duration:** 2 days

---

## Phase 6 — API & Streaming Interface ✅ Complete

**Goal:** Expose PULSE via FastAPI with SSE/WebSocket streaming, and build the historical-match replay simulator that stands in for a live feed (Charter §6).

**Key Tasks:**

- FastAPI app with `/v1/matches/{match_id}/stream` (SSE) and WebSocket fallback
- Replay simulator: reads a historical match's `PointRecord` sequence and emits it at real-time cadence (configurable speed multiplier for testing)
- Wire the LangGraph pipeline to the streaming endpoint via process-startup lifespan compilation
- Request/response Pydantic schemas for all endpoints (`src/api/schemas.py`)
- SQLite audit persistence layer (`src/utils/persistence.py`) for decision logs and tactical outputs (FR-12)
- Unit and integration tests covering SSE/WebSocket parity, SQLite persistence, and fail-loud error handling

**Deliverables:** `src/api/main.py`, `src/api/streaming.py`, `src/api/schemas.py`, `src/simulator/replay.py`, `src/utils/persistence.py`, `tests/integration/test_api_streaming.py`, `reports/docs/architecture/phase6_api_and_streaming_architecture.md`, `reports/docs/evaluations/streaming_api_evaluation_report.md`

**Exit Criteria:** A full historical match can be streamed end-to-end through the API and produces the expected sequence of leverage/escalation events; SSE and WebSocket both verified.

**Dependencies:** Phase 3, Phase 4, Phase 5.

**Est. Duration:** 2 days

---

## Phase 6.5 — Interactive Presentation Layer (Tactical Cockpit) ✅ Complete

**Goal:** Build and integrate an embedded, zero-dependency real-time web dashboard (`src/api/static/`) directly within FastAPI to visually showcase the streaming leverage engine, Wilson confidence intervals, conditional LangGraph node executions, and game-theoretic payoff matrices for technical evaluators, recruitment managers, and coaches (ADR-013).

**Key Tasks:**

- Develop single-page tactical cockpit (`src/api/static/index.html`, `src/api/static/app.js`, `src/api/static/style.css`) using Vanilla HTML5/ES6/CSS with dark-mode glassmorphism styling and Canvas 2D timeline plotting.
- Connect UI to native `GET /v1/matches/{match_id}/stream` (SSE) with dynamic DOM updates, real-time match controls (play, pause, speed multiplier), and match selector dropdown.
- Mount static assets in `src/api/main.py` via FastAPI `StaticFiles` at `/` and `/ui`.
- Implement automated integration and smoke tests verifying static asset delivery, MIME types, and SSE browser client compatibility.
- Create standardized one-click system launcher script (`launch_app.bat`) to automate environment synchronization, artifact verification, FastAPI startup, and browser launch.

**Deliverables:** `src/api/static/index.html`, `src/api/static/app.js`, `src/api/static/style.css`, static file mount in `src/api/main.py`, unit/integration tests in `tests/integration/test_static_ui.py`, one-click ecosystem launcher `launch_app.bat`.


**Exit Criteria:** Navigating to `http://localhost:8000/` loads the tactical cockpit in <100ms with 0 npm/Node dependencies; match replay streams and animates live leverage curves and LangGraph node states in real time.

**Dependencies:** Phase 6 complete.

**Est. Duration:** 1 day

---

## Phase 6.6 — Post-Match Tactical Intelligence & Reporting ✅ Complete

**Goal:** Provide an end-to-end post-match tactical intelligence and performance debriefing engine that aggregates point-by-point leverage, extracts top pivotal inflection moments, evaluates leverage-tiered pressure resilience, audits serve-return game theory distributions, and renders coach-ready reports in JSON, Markdown, and interactive UI modal formats.

**Key Tasks:**

- Implement deterministic analytics engine in `src/analytics/match_report.py` (Markov leverage aggregation, Wilson 95% confidence intervals, pivotal point ranking, pressure tier partitioning, and minimax serve-return audit).
- Add Pydantic v2 schemas (`MatchReportResponse`, `PivotalPointEntry`, `PlayerPressureMetrics`, `GameTheoryExploitAudit`, `MatchSummaryStats`) in `src/api/schemas.py`.
- Integrate grounded executive debrief synthesis with free-tier Groq Cloud (`llama-3.1-8b-instant`) / Anthropic LLM async clients and deterministic zero-hallucination fallback.
- Register `GET /v1/matches/{match_id}/report` endpoint in `src/api/streaming.py` supporting `json` and `markdown` output formats and automatic `bo3`/`bo5` scoring detection.
- Add glassmorphic Post-Match Report interactive modal, tabular KPI displays, and clipboard/JSON/print PDF export tools to Tactical Cockpit UI (`src/api/static/`).
- Build comprehensive unit and integration test suites (`tests/unit/test_match_report.py`, `tests/integration/test_match_report_api.py`, `tests/integration/test_static_ui.py`) passing 100%.

**Deliverables:** `src/analytics/match_report.py`, `src/analytics/formatting.py`, `src/api/schemas.py`, `src/api/streaming.py`, `src/api/static/index.html`, `src/api/static/app.js`, `src/api/static/style.css`, `tests/unit/test_match_report.py`, `tests/integration/test_match_report_api.py`, `reports/docs/workflows/post_match_reporting_execution_workflow.md`, `reports/docs/decisions/free_tier_llm.md`.

**Exit Criteria:** Full post-match intelligence reports generated in <200ms; executive debrief grounded with 0 hallucinated figures; interactive modal accessible via browser with instant markdown copy and JSON export; 176/176 test suite passing.

**Dependencies:** Phases 1–6.5 complete.

**Est. Duration:** 1 day

---

## Phase 7 — Observability, CI/CD, Shadow-Mode Acceptance

**Goal:** Production-harden the system, bake the unified API, UI, and reporting engine into a production container, and run the full shadow-mode acceptance evaluation.

**Key Tasks:**

- OpenTelemetry spans across solver, models, and graph nodes
- `structlog` JSON logging finalized across all components
- GitHub Actions: coverage gate (≥70%), solver-correctness gate, Trivy scan
- Multi-stage Docker build, non-root, digest-pinned base, packaging `src/api/static/` and `docker-compose.yml`
- Run the retrospective escalation-precision evaluation (`pulse_ml_canvas.md` §8) across the full historical match set
- Shadow-mode acceptance run: replay a held-out set of matches end-to-end through the deployed container and confirm all Definition of Done criteria (`pulse_project_charter.md` §5)

**Deliverables:** `.github/workflows/ci.yml`, `Dockerfile`, `docker-compose.yml`, final evaluation report

**Exit Criteria:** All items in `pulse_project_charter.md` §5 Definition of Done are checked off.

**Dependencies:** Phases 1–6.6 complete.

**Est. Duration:** 1–2 days

---

## Sequential Action Plan (Immediate Next Steps)

1. Proceed to Phase 7: Observability, OpenTelemetry instrumentation, and distributed trace context propagation
2. Finalize multi-stage Docker build and Docker Compose packaging for full-stack deployment
3. Run shadow-mode retrospective evaluation and verify all Definition of Done merge criteria
