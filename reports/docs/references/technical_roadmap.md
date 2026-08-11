# Technical Roadmap — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.1.0 | **Date:** 2026-07-20

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
- Implement `TacticalOutputNode` with variable output shape depending on which upstream nodes fired
- Structured logging of every fire/suppress decision with its triggering condition (FR-10)
- Integration tests verifying the graph produces different node sets for different match-state fixtures

**Deliverables:** `graph/state_monitor.py`, `graph/pressure_diagnostic.py`, `graph/strategy_exploit.py`, `graph/tactical_output.py`, `graph/pulse_graph.py`, integration test suite

**Exit Criteria:** Graph correctly varies its execution path across a set of fixture match states (routine point, high-leverage/low-data point, high-leverage/high-data point); all decisions logged.

**Dependencies:** Phase 2 (leverage + confidence bands).

**Est. Duration:** 2–3 days

---

## Phase 5 — Game-Theoretic Exploit Module

**Goal:** Implement the Nash-equilibrium serve-direction solver and the opponent-specific best-response deviation calculation, with the sample-size gate as a hard, tested requirement.

**Key Tasks:**

- Implement minimax equilibrium solver via `scipy.optimize.linprog`
- Implement opponent return-positioning bias estimation from historical charted data
- Implement best-response deviation and expected-value gain calculation
- Implement the sample-size gate: below threshold, the module returns an explicit "insufficient data" result, not a suppressed silent failure
- Unit tests: equilibrium mix sums to 1 and is indifference-inducing; gate correctly suppresses output on synthetic sparse-data fixtures

**Deliverables:** `core/game_theory.py`, `tests/test_game_theory.py`

**Exit Criteria:** Solver passes unit tests; sample-size gate verified via integration test (FR-6); `StrategyExploitNode` from Phase 4 wired to this module.

**Dependencies:** Phase 1 (historical data), Phase 4 (node to wire into).

**Est. Duration:** 2 days

---

## Phase 6 — API & Streaming Interface

**Goal:** Expose PULSE via FastAPI with SSE/WebSocket streaming, and build the historical-match replay simulator that stands in for a live feed (Charter §6).

**Key Tasks:**

- FastAPI app with `/v1/matches/{match_id}/stream` (SSE) and WebSocket fallback
- Replay simulator: reads a historical match's `PointRecord` sequence and emits it at real-time cadence (configurable speed multiplier for testing)
- Wire the LangGraph pipeline to the streaming endpoint
- Request/response Pydantic schemas for all endpoints

**Deliverables:** `api/main.py`, `api/streaming.py`, `simulator/replay.py`

**Exit Criteria:** A full historical match can be streamed end-to-end through the API and produces the expected sequence of leverage/escalation events; SSE and WebSocket both verified.

**Dependencies:** Phase 3, Phase 4.

**Est. Duration:** 2 days

---

## Phase 7 — Observability, CI/CD, Shadow-Mode Acceptance

**Goal:** Production-harden the system and run the full shadow-mode acceptance evaluation.

**Key Tasks:**

- OpenTelemetry spans across solver, models, and graph nodes
- `structlog` JSON logging finalized across all components
- GitHub Actions: coverage gate (≥70%), solver-correctness gate, Trivy scan
- Multi-stage Docker build, non-root, digest-pinned base
- Run the retrospective escalation-precision evaluation (`ml_canvas.md` §8) across the full historical match set
- Shadow-mode acceptance run: replay a held-out set of matches end-to-end and confirm all Definition of Done criteria (`project_charter.md` §5)

**Deliverables:** `.github/workflows/ci.yml`, `Dockerfile`, final evaluation report

**Exit Criteria:** All items in `project_charter.md` §5 Definition of Done are checked off.

**Dependencies:** Phases 1–5 complete.

**Est. Duration:** 1–2 days

---

## Sequential Action Plan (Immediate Next Steps)

1. Scaffold the repository structure and `pyproject.toml` with `uv`
2. Define `PointRecord` schema and `pandera` gates
3. Implement the closed-form Markov solver and its golden-value test suite, **this must be green before any other work begins**, since every downstream component depends on it as ground truth
4. Source and stage historical point-by-point match data; set up the DVC pipeline for ingestion
5. Proceed to Phase 2 only once Phase 1's exit criteria are met
