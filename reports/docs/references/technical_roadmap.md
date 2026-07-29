# Technical Roadmap — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.1.0 | **Date:** 2026-07-20

This roadmap sequences implementation so that the deterministic ground truth (Phase 1) exists and is verified before any ML or agentic layer is built on top of it, consistent with the principle that PULSE's mathematical core, not its models, is the system's source of truth.

---

## Phase 0 — Planning ✅ Complete

**Deliverables:** `ml_canvas.md`, `project_charter.md`, `prd.md`, `user_story.md`, `technical_roadmap.md` (this document), `system_design.md`.

---

## Phase 1 — Project Scaffolding ✅ Complete

**Goal:** Establish the production repository skeleton — dependency management, directory layout, foundational utilities, CI tooling configuration, and governance scripts — so that every subsequent phase builds on a consistent, lint-clean, type-checked, and CI-enforced base rather than retrofitting infrastructure around working code.

**Key Tasks:**

- Initialize `git` repository on `main` branch; configure `.gitignore` to exclude `.env`, `__pycache__`, DVC cache, and build artifacts
- Set up `uv` as the single dependency manager; define `pyproject.toml` with `[project]` table, `requires-python = ">=3.11"`, and initial dependencies (`pydantic>=2.0`, `fastapi`, `pyyaml`)
- Create the full `src/` module tree with `__init__.py` and `py.typed` marker files for each package: `schemas/`, `core/`, `models/`, `graph/`, `api/`, `simulator/`, `utils/`, `config/`, `constants/`
- Implement `src/constants/__init__.py`: single source of truth for `PROJECT_ROOT`, `CONFIG_DIR`, `PARAMS_FILE_PATH`, `DATA_DIR`, `ARTIFACTS_DIR`, `LOGS_DIR`, `REPORTS_DIR`; auto-creates missing directories on import
- Implement `src/utils/exceptions.py`: `BasePulseException` base class with relative-path traceback formatting via `error_message_detail`; domain sub-exceptions `SolverException`, `SufficiencyGateException`, `InvalidMatchStateError`, `ModelInferenceError`, `SanitizationError`
- Implement `src/utils/logger.py`: rotating file handler (`pulse_engine.log`, 5 MB × 5 backups) with optional `rich` console handler; `get_logger(name, headline)` factory; `log_spacer()` utility
- Implement `src/utils/sanitization.py`: stubbed prompt-injection defense — no free-text tool input exists yet, but the routing contract is established so any future coach-feedback field is forced through this module before any prompt
- Implement `src/config/__init__.py`: `load_params()` reads `params.yaml` via `pyyaml`; falls back to safe defaults if the file is absent (leverage threshold 0.70, sample-size gate 15, solver tolerance 1e-9)
- Populate typed stub modules for `schemas/`, `core/`, `models/`, `graph/`, `api/`, and `simulator/` — each with Google-style docstrings, Pydantic v2 I/O contracts, and placeholder logic that makes the module importable and type-checkable without yet being functional
- Create `tests/unit/test_markov_solver.py`, `tests/integration/test_conditional_graph.py`, and `tests/evals/test_tactical_output_groundedness.py` — structural stubs that establish the testing architecture before Phase 2 fills in the golden values
- Implement `scripts/check_file_size.py`: CI-ready line-count ceiling script (1,000 lines per `src/` file); explicit `ALLOWLIST` with mandatory per-entry justifications; exits non-zero and lists every violation
- Configure `params.yaml` with Phase 1 placeholder values for every threshold that downstream phases will calibrate
- Push repository to GitHub (`SebastianGarrido2790/PULSE`); confirm `git remote -v` and an initial commit on `main`
- Write `README.md`: project summary, architecture invariants, stack table, directory tree, getting-started commands, and reference link to `tennis_mathematical_elegance.md`

**Deliverables:**

- `src/` package tree (all `__init__.py` + `py.typed` markers, all stub modules)
- `src/constants/__init__.py`, `src/utils/exceptions.py`, `src/utils/logger.py`, `src/utils/sanitization.py`, `src/config/__init__.py`
- `scripts/check_file_size.py`
- `tests/unit/test_markov_solver.py`, `tests/integration/test_conditional_graph.py`, `tests/evals/test_tactical_output_groundedness.py` (structural stubs)
- `pyproject.toml` with `[project]` table and initial dependencies
- `params.yaml` v0.1 (placeholder thresholds)
- `README.md` and `tennis_mathematical_elegance.md` referenced from it
- GitHub remote `origin` tracking `main`

**Exit Criteria:**

- `python scripts/check_file_size.py` exits 0; all `src/` files are within the 1,000-line ceiling
- `git remote -v` confirms the remote is set and the initial commit is pushed
- Every module in `src/` is importable without error (`python -c "import src.<module>"`)
- `params.yaml` exists and contains keyed entries for `leverage_escalation_threshold`, `sample_size_gate`, and `solver_tolerance`

**Dependencies:** Phase 0 (planning documents complete).

**Est. Duration:** 1 day

---

## Phase 2 — Data Layer & Deterministic Core

**Goal:** Establish the `PointRecord` schema, ingestion/validation pipeline, and the closed-form Markov solver the system's ground truth, before any model is trained against it.

**Key Tasks:**

- Define `PointRecord` (Pydantic v2) and `pandera` validation gates per `ml_canvas.md` §6
- Implement the closed-form Markov solver (point → game → set → match)
- Write golden-value unit tests comparing solver output to textbook combinatorial formulas (win-4-0, win-4-1, win-4-2, win-via-deuce paths)
- Implement observation-count tracking per player/surface/serve-number stratum, needed for the Wilson-interval uncertainty layer in Phase 2 (ADR-005)
- Set up `params.yaml` with initial threshold placeholders (leverage, sample size) values TBD pending Phase 2/3 calibration
- DVC-track the raw and validated data stages

**Deliverables:** `schemas/point_record.py`, `core/markov_solver.py`, `tests/test_markov_solver.py` (CI-blocking gate), `params.yaml` v0.1

**Exit Criteria:** Solver matches closed-form theory within 1e-9 tolerance on all tested paths; `pandera` gates reject malformed records; `dvc repro` runs the ingestion stage end-to-end.

**Dependencies:** None (foundational phase).

**Est. Duration:** 2 days

---

## Phase 3 — Tier 1 ML Layer

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

## Phase 4 — Event-Driven Orchestration (LangGraph)

**Goal:** Implement the conditional graph: `StateMonitorNode` always-on, `PressureDiagnosticNode` and `StrategyExploitNode` triggered, `TacticalOutputNode` assembling whichever fired.

**Key Tasks:**

- Implement `StateMonitorNode`: per-point leverage + confidence band computation, threshold check against `params.yaml`
- Implement conditional edges: escalate to `PressureDiagnosticNode` on leverage threshold; escalate to `StrategyExploitNode` on leverage threshold **and** sample-size gate (Phase 4 dependency)
- Finalize how confidence-band width interacts with the escalation threshold (open question from `prd.md` §10), provisional rule: wide bands raise the effective threshold required to trigger
- Implement `TacticalOutputNode` with variable output shape depending on which upstream nodes fired
- Structured logging of every fire/suppress decision with its triggering condition (FR-10)
- Integration tests verifying the graph produces different node sets for different match-state fixtures

**Deliverables:** `graph/state_monitor.py`, `graph/pressure_diagnostic.py`, `graph/tactical_output.py`, `graph/pulse_graph.py`, integration test suite

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

**Exit Criteria:** Solver passes unit tests; sample-size gate verified via integration test (FR-6); `StrategyExploitNode` from Phase 3 wired to this module.

**Dependencies:** Phase 1 (historical data), Phase 3 (node to wire into).

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

1. ~~Scaffold the repository structure and `pyproject.toml` with `uv`~~ ✅ Done (Phase 1)
2. Define `PointRecord` schema and `pandera` validation gates (Phase 2)
3. Implement the closed-form Markov solver and its golden-value test suite — **this must be green before any other work continues**, since every downstream component depends on it as the system's ground truth (Phase 2)
4. Source and stage historical point-by-point match data; set up the DVC pipeline for ingestion (Phase 2)
5. Proceed to Phase 3 only once Phase 2's exit criteria are met (solver tolerance < 1e-9; `dvc repro` runs end-to-end)

