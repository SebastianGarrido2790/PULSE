# Phase 7 — Execution Workflow

**Observability, CI/CD, Shadow-Mode Acceptance — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 7 of 7 (final) | **Version:** 1.1.0 | **Date:** 2026-08-26  
**Status:** 🟡 Ready to execute — no code written yet  
**Authority:** `phase7_implementation_plan_and_decisions.md` v1.1.0 (D-1–D-13, all approved)  
**Scope of this document:** sequencing only, no code.

---

## How to Read This

11 stages (0–10), strictly ordered. Steps numbered continuously (1–31) so any step is unambiguously referenceable. Each step is tagged with the decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

---

## Stage 0 — Pre-Implementation Verification

1. Read `reports/docs/references/pulse_project_charter.md` §5 (Definition of Done) in full. Produce an explicit checklist mapping every DoD item to the Phase 7 deliverable or decision that satisfies it — this checklist is what Stage 9's final report gets reconciled against.
2. Read `reports/docs/references/pulse_ml_canvas.md` §8 (Evaluation) in full. Confirm the retrospective escalation-precision evaluation methodology (realized win-probability swing vs. pre-outcome escalation alerts) governing `scripts/evaluate_escalation_precision.py`. **[D-9]**
3. Read `src/utils/logger.py` directly. Audit log formatting and handlers (`RotatingFileHandler`, `RichHandler`), confirming logger conventions across all `src/` modules. **[D-11]**
4. Read `.github/workflows/ci.yml` directly to inventory existing steps and scope Stage 6 additions (integration test suites, coverage gate, Docker build, Trivy scan). **[D-3]**
5. Confirm current test baseline (176 tests passing) and verify test coverage over `src/graph/llm_client.py`, `src/analytics/match_report.py`, and `src/analytics/formatting.py`. **[D-8]**

**Gate 0:** all pre-implementation verification items resolved against literal source text; D-9 methodology confirmed; CI and logging baseline fully mapped.

---

## Stage 1 — Verify Multi-Provider LLM & Debrief Test Coverage

6. Confirm unit and integration test coverage for direct SDK wrappers (`groq.AsyncGroq`, `anthropic.AsyncAnthropic`): (a) network/timeout exceptions, (b) missing `GROQ_API_KEY` / `ANTHROPIC_API_KEY`, (c) malformed API responses, (d) unsupported provider configuration — each asserting deterministic raw-payload passthrough fallback without unhandled exceptions. **[D-8, ADR-015]**
7. Confirm test coverage across `src/analytics/match_report.py` and `src/analytics/formatting.py` (Markov leverage aggregation, pivotal points ranking, pressure breakdown, game-theory exploit audit, JSON/Markdown serialization, and async debrief synthesis).
8. Re-run coverage report (`pytest --cov=src`); verify aggregate coverage remains well above the 70% project threshold with all fallback branches explicitly exercised.

**Gate 1:** all LLM direct SDK paths and post-match report analytics have dedicated tests; aggregate coverage verified above 70%.

---

## Stage 2 — OpenTelemetry Spans for Solver, Model & Analytics Layers

9. Add per-call child spans to:
   - `core/markov_solver.py` (`compute_leverage()`)
   - `core/leverage_uncertainty.py` (`propagate_leverage_uncertainty()`)
   - `models/point_win_classifier.py` (`resolve_point_win_probability()`)
   - `models/pressure_deviation.py` (`get_pressure_deviation()`)
   - `core/game_theory.py` (`compute_exploit()`)
   - `analytics/match_report.py` (`generate_match_report_async()`, `evaluate_all_points()`) **[D-10]**
10. Confirm span attributes carry latency-profiling metadata (e.g. stratum keys, matrix dimensions, solver duration) while relying on OTel context propagation to nest under active graph node spans or API request spans.
11. Trace inspection: replay one escalated point and one post-match report request, verifying in logs/traces that child spans correctly nest under parent node/endpoint spans.

**Gate 2:** span tree correctly nested for both real-time graph node executions and post-match report generations.

---

## Stage 3 — Structured Logging Finalization & Audit Pass

12. Perform a repository-wide audit of `src/` to confirm all logging routes through `src.utils.logger.get_logger()`. **[D-11]**
13. Eliminate any stray `print()` calls or bare stdlib `logging` calls bypassing the centralized logger.

**Gate 3:** grep confirms zero stray `print()` calls in `src/`; all log output consistently formatted with timestamp, level, module name, and structured messages.

---

## Stage 4 — Multi-Stage Dockerfile Packaging

14. Write a multi-stage `Dockerfile`:
    - **Builder stage**: Install dependencies via `uv` into a clean virtual environment.
    - **Final stage**: Run as a non-root user on a SHA256 digest-pinned Python base image (`python:3.11-slim@sha256:...`).
    - **Asset packaging**: `COPY` application code (`src/`, including `src/api/static/` presentation layer and `src/analytics/`) and versioned `artifacts/` (stratum table, pressure artifact, payoff matrices, points parquet). **[D-4, D-5, D-7]**
15. Set default `CMD` to launch `api.main` (FastAPI serving SSE streams, REST endpoints, and the Tactical Cockpit UI at `http://localhost:8000`). Confirm CLI execution (`uv run simulator.replay ...`) is reachable via runtime entrypoint override.
16. Add a container `HEALTHCHECK` instruction probing `GET /health`. **[D-12]**

**Gate 4:** `docker build` succeeds; container starts non-root on digest-pinned base; `HEALTHCHECK` passes; static UI and API endpoints respond cleanly.

---

## Stage 5 — `docker-compose.yml` Full-Stack Orchestration

17. Define the primary API service in `docker-compose.yml`:
    - Maps host port `8000:8000` to serve the Tactical Cockpit UI and streaming API.
    - Mounts a named volume at `artifacts/` (or SQLite path `artifacts/pulse_session.db`) ensuring session audit trails survive container restarts (satisfying FR-12). **[D-4, D-6]**
    - Configures environment variables (`GROQ_API_KEY`, `ANTHROPIC_API_KEY`) via `.env` passthrough.
18. Validate one-click command: run `docker compose up --build`, confirm the application launches, serves the Tactical Cockpit at `http://localhost:8000`, streams live replay data, and persists SQLite logs across `docker compose down` and restart.

**Gate 5:** `docker compose up --build` works end-to-end; SQLite audit logs survive container restarts; Tactical Cockpit is accessible in browser.

---

## Stage 6 — CI Pipeline Completion (GitHub Actions)

19. Extend `.github/workflows/ci.yml` to the full target order:
    - **Lint & Format**: `ruff check .` and `ruff format --check .`
    - **Type Check**: `pyright` (strict typing gate)
    - **Modularity Ceiling**: `python scripts/check_file_size.py` (<1,000 lines per file)
    - **Unit Tests**: Full unit suite (Markov solver golden tests, game theory, ML models, match report analytics)
    - **Integration Tests**: `test_conditional_graph.py`, `test_api_streaming.py`, `test_static_ui.py`, `test_match_report_api.py`
    - **Eval Suite**: DeepEval groundedness numbers verification (`test_tactical_output_groundedness.py`)
    - **Coverage Gate**: `pytest --cov=src --cov-fail-under=70` (≥70% aggregate coverage) **[D-8]**
    - **Docker Build**: Build multi-stage container image
    - **Security Scan**: Run Trivy vulnerability scan against the built container image (asserting 0 CRITICAL CVEs) **[D-3]**
20. Verify pipeline execution and ensure all stages pass cleanly on GitHub Actions runner.

**Gate 6:** full CI pipeline green on clean run; coverage gate (≥70%) and Trivy scan (0 CRITICAL CVEs) both pass.

---

## Stage 7 — Retrospective Escalation-Precision Evaluation

21. Implement `scripts/evaluate_escalation_precision.py` per `pulse_ml_canvas.md` §8:
    - Recompute realized win-probability swings after match completion using the closed-form Markov solver.
    - Evaluate whether pre-outcome live escalation alerts correctly flagged high-impact points in advance. **[D-9]**
22. Execute evaluation script across historical match data and generate `reports/docs/evaluations/escalation_precision_report.md`. **[D-2]**
23. Document measured Alert Precision (target $\ge 0.75$) and False Escalation Rate (target $< 0.15$) against PRD §7 criteria, explicitly noting per-player aggregation boundaries.

**Gate 7:** evaluation script runs reproducibly; `escalation_precision_report.md` generated with explicit metric comparisons against PRD targets.

---

## Stage 8 — Shadow-Mode Acceptance Run

24. With the containerized stack running (`docker compose up`), execute end-to-end shadow-mode acceptance across held-out historical matches. **[D-1, D-2]**
25. For each match in the acceptance suite, verify:
    - Live replay streaming through `GET /v1/matches/{id}/stream` (SSE events sequence correctly).
    - Sub-second latency budget (`StateMonitorNode` $< 1\text{s}$, triggered nodes $< 5\text{s}$).
    - Correct SQLite session persistence of point records and escalation logs.
    - Post-match tactical intelligence retrieval via `GET /v1/matches/{id}/report` ($< 200\text{ms}$).
    - Tactical Cockpit browser UI renders live leverage curves, Wilson bounds, exploit badges, and post-match modal without errors.
26. Record acceptance run traces and log any anomalies.

**Gate 8:** full held-out match acceptance suite replays cleanly through containerized API with zero unhandled exceptions and sub-second latency.

---

## Stage 9 — Final Evaluation Report & Definition-of-Done Reconciliation

27. Compile `reports/docs/evaluations/phase7_final_evaluation_report.md` using the standard exit-criteria sign-off table format. **[D-13]**
28. Perform item-by-item reconciliation against `pulse_project_charter.md` §5 (Definition of Done), verifying every DoD criterion with concrete evidence from test outputs, MLflow logs, CI runs, and evaluation reports.

**Gate 9:** every item in `pulse_project_charter.md` §5 has an explicit ✅ sign-off with supporting evidence in the final evaluation report.

---

## Stage 10 — Full Verification & Project Close-Out

29. Run complete local quality suite:
    - `uv run ruff check .`
    - `uv run pyright`
    - `python scripts/check_file_size.py`
    - `uv run pytest --cov=src --cov-report=term-missing` (176+ tests passing, ≥70% coverage)
30. Log architectural decision records in `reports/docs/architecture/system_design.md` capturing containerization, security scanning, and acceptance methodology.
31. Update `reports/docs/references/technical_roadmap.md` marking Phase 7 and all milestones as ✅ Complete.

**Gate 10 (Project Complete):** all quality checks green; containerized stack verified; CI passing; final evaluation report approved; technical roadmap complete.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify DoD & methodology)
   │
   ▼
Stage 1 (verify LLM & analytics test coverage)
   │
   ▼
Stage 2 (OTel child spans for solver, models & analytics)
   │
   ▼
Stage 3 (structured logging audit)
   │
   ▼
Stage 4 (multi-stage Dockerfile packaging)
   │
   ▼
Stage 5 (docker-compose.yml full-stack orchestration)
   │
   ▼
Stage 6 (CI pipeline completion: coverage gate + Trivy scan)
   │
   ▼
Stage 7 (retrospective escalation-precision evaluation)
   │
   ▼
Stage 8 (shadow-mode acceptance run across held-out matches)
   │
   ▼
Stage 9 (final evaluation report & DoD reconciliation)
   │
   ▼
Stage 10 (full quality verification & project close-out)
```

31 steps, 11 gates. Every stage is bounded by an explicit gate, ensuring complete test coverage, container integrity, and mathematical ground-truth verification.
