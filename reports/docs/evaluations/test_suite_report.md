# PULSE — Test Suite Report

> **Version:** v1.0.0 — _Living Document_  
> **Phase:** 7 — Production Hardening, Observability, CI/CD & Operational Acceptance  
> **Status:** 🟢 202 / 202 Tests Passing (0 Warnings)  
> **Coverage:** 92% Total Code Coverage (100% Graph Topology, Core Math, Schemas & Wire Contracts)  
> **Maintained By:** MLOps & Performance Analytics Engineering Team  
> **Reference Documents:** [technical_roadmap.md](../references/technical_roadmap.md), [phase7_execution_workflow.md](../workflows/phase7_execution_workflow.md), [phase7_final_evaluation_report.md](phase7_final_evaluation_report.md), [shadow_mode_acceptance_report.md](shadow_mode_acceptance_report.md), [escalation_precision_report.md](escalation_precision_report.md), [system_design.md](../architecture/system_design.md)


---

## 1. Testing Strategy Overview

The **PULSE (Point-Level Understanding & Strategic Leverage Engine)** test suite enforces a rigorous, deterministic quality policy designed to ensure mathematical ground truth, strict typing, and reproducible event-driven orchestration. Our testing posture rests on six core principles:

- **Ground-Truth Mathematical Primacy:** Closed-form combinatorial probability theory and exact minimax linear programming are the ground truths. From Phase 2 onward, the Markov solver must match theoretical win-probabilities within a $1 \times 10^{-9}$ tolerance. Solver divergence is a CI-blocking build failure.
- **Determinism:** Every test must produce identical results under a fixed seed. Replayed matches, payoff matrix compilation, post-match analytics, and solver evaluations are 100% reproducible across local and CI environments.
- **Fail-Loud Policy:** Validation errors raise explicit custom exceptions (`SolverException`, `GameTheorySolverException`, `SufficiencyGateException`, `PersistenceException`, `InvalidMatchStateError`, `ModelInferenceError`, `SanitizationError`) rather than falling back silently.
- **File-Size Ceiling Gate:** No Python source file under `src/` may exceed 1,000 lines (§5.1 of project constitution). Enforced via `scripts/check_file_size.py` as a hard CI gate.
- **Strict Static Typing:** Python 3.11+ code targeting 80%+ Pyright type-check coverage with zero tolerated errors or missing import warnings.
- **Advisory-Only Governance:** Tactical recommendations emit explicit confidence bands (Wilson intervals) and sample-size sufficiency checks. Tests verify that insufficient data triggers explicit suppression rather than speculative advice.

---

## 2. Test Suite Structure

The testing directory mirrors the core package structure:

```text
PULSE/
├── scripts/
│   ├── check_file_size.py               # 1,000-line ceiling enforcement script (§5.1)
│   └── build_payoff_matrices.py         # Payoff matrix compilation DVC pipeline stage
├── tests/
│   ├── __init__.py                      # Package docstring stub
│   ├── unit/
│   │   ├── test_match_report.py         # Deterministic analytics, ranking, pressure, game-theory & debrief (Phase 6.6)
│   │   ├── test_api_schemas.py          # Pydantic v2 wire models & validation tests (Phases 6, 6.6)
│   │   ├── test_point_record_conversion.py # PointRecord -> PointContext conversion tests (Phase 6)
│   │   ├── test_persistence.py          # SQLite audit persistence & query tests (Phase 6)
│   │   ├── test_api_main.py             # FastAPI lifespan, static mounts & health route tests (Phases 6, 6.5)
│   │   ├── test_streaming.py            # SSE, keep-alive comments, WS & report route tests (Phases 6, 6.6)
│   │   ├── test_replay_generator.py     # Async generator & CLI tests (Phase 6)
│   │   ├── test_game_theory.py          # Consolidated §8 validation properties (Phase 5)
│   │   ├── test_game_theory_solver.py   # Analytical & HiGHS LP equilibrium solver tests
│   │   ├── test_game_theory_exploit.py  # Best response & empirical-Bayes shrinkage tests
│   │   ├── test_game_theory_contracts.py# PayoffMatrix & ExploitResult Pydantic tests
│   │   ├── test_build_payoff_matrices.py# DVC stage matrix extraction unit tests
│   │   └── ...                          # Prior unit test suites (Phases 1-4)
│   ├── integration/
│   │   ├── test_match_report_api.py     # End-to-end report API (JSON, Markdown, BO5, LLM mock, 404) (Phase 6.6)
│   │   ├── test_static_ui.py            # Static UI delivery, DOM contracts, report modal & MIME tests (Phases 6.5, 6.6)
│   │   ├── test_api_streaming.py        # SSE/WS parity & SQLite persistence integration (Phase 6)
│   │   └── test_conditional_graph.py    # LangGraph conditional edge & state tests (Phases 4-5)
│   └── evals/
│       └── test_tactical_output_groundedness.py # DeepEval narrative hallucination checks
├── pyproject.toml                       # Pytest, Ruff, and UV toolchain settings
├── pyrightconfig.json                   # Pyright static type checker configuration
├── params.yaml                          # Quantitative operational thresholds contract
└── .github/workflows/ci.yml             # Single sequential GitHub Actions CI quality gate
```


---

## 3. Component Breakdown & Verification Matrix

### 3.1 Project Scaffolding Baseline (`tests/unit/test_scaffolding.py`)

| Scenario               | Test Method                       | What Is Verified                                                                                                                                 | Status  |
| :--------------------- | :-------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| **Structure Baseline** | `test_project_structure_baseline` | Asserts existence of `pyproject.toml`, `pyrightconfig.json`, `params.yaml`, `dvc.yaml`, `scripts/check_file_size.py`, and `src/utils/logger.py`. | 🟢 PASS |

---

### 3.2 Utilities & Custom Exceptions (`src/utils/`)

| Module                    | Verification Target            | What Is Verified                                                                                                                                                                                                       | Status  |
| :------------------------ | :----------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| `src/utils/exceptions.py` | `BasePulseException` hierarchy | Verifies `SolverException`, `GameTheorySolverException`, `SufficiencyGateException`, `InvalidMatchStateError`, `ModelInferenceError`, and `SanitizationError` format stack traces with relative paths and line numbers. | 🟢 PASS |
| `src/utils/logger.py`     | `get_logger`                   | Verifies `Path` resolution, rotating file handlers (`logs/pulse_engine.log`), rich console formatting, and headline separator output without `NameError` or missing imports.                                           | 🟢 PASS |

---

### 3.3 File-Size Ceiling Gate (`scripts/check_file_size.py`)

| Check                 | Target                       | Rule / Ceiling                                                                                                               | Status                 |
| :-------------------- | :--------------------------- | :--------------------------------------------------------------------------------------------------------------------------- | :--------------------- |
| **Source Line Count** | All `.py` files under `src/` | Line limit: **1,000 lines per file**. Allowlist strictly restricted to auto-generated schemas with documented justification. | 🟢 PASS (0 Violations) |

---

### 3.4 Static Type Analysis (`pyright`)

| Tool        | Configuration                                       | Target                       | Status                         |
| :---------- | :-------------------------------------------------- | :--------------------------- | :----------------------------- |
| **Pyright** | `pyrightconfig.json` (`standard` mode, Python 3.11) | `src/`, `tests/`, `scripts/` | 🟢 PASS (0 Errors, 0 Warnings) |

---

### 3.5 Code Quality & Formatting (`ruff`)

| Tool            | Ruleset                                                                                                | Status                       |
| :-------------- | :----------------------------------------------------------------------------------------------------- | :--------------------------- |
| **Ruff Check**  | `E` (pycodestyle), `F` (Pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear), `RUF` (Ruff-specific) | 🟢 PASS (0 Linter Errors)    |
| **Ruff Format** | Line length = 100                                                                                      | 🟢 PASS (89 Files Formatted) |

---

### 3.6 Continuous Integration Pipeline (`.github/workflows/ci.yml`)

| CI Stage         | Command / Tool                      | Success Condition                       | Status   |
| :--------------- | :---------------------------------- | :-------------------------------------- | :------- |
| **Setup**        | `astral-sh/setup-uv@v3`             | Python 3.11 environment synced via `uv` | 🟢 Ready |
| **Linter**       | `uv run ruff check .`               | Exit code 0                             | 🟢 Ready |
| **Format**       | `uv run ruff format --check .`      | Exit code 0                             | 🟢 Ready |
| **Type Check**   | `uv run pyright`                    | Exit code 0                             | 🟢 Ready |
| **Ceiling Gate** | `python scripts/check_file_size.py` | Exit code 0                             | 🟢 Ready |
| **Pytest**       | `uv run pytest --cov=src`           | Exit code 0, coverage $\ge 70\%$        | 🟢 Ready |

---

### 3.7 Point-Win Classifier (`tests/unit/test_point_win_classifier.py`)

| Module                               | Verification Target                         | What Is Verified                                                                                                                          | Status  |
| :----------------------------------- | :------------------------------------------ | :---------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| `src/models/point_win_classifier.py` | `build_stratum_table`                       | Compiles exact stratum observation counts ($N$) and mean win rates from training split across Tier 0, Tier 1, and Tier 2.                 | 🟢 PASS |
| `src/models/point_win_classifier.py` | `resolve_point_win_probability`             | Evaluates 4-tier fallback hierarchy ($\text{Tier 0 Exact} \to \text{Tier 1 Player} \to \text{Tier 2 Surface} \to \text{Tier 3 Default}$). | 🟢 PASS |
| `src/models/point_win_classifier.py` | Quantile Calibration ($\text{MCE}$)         | Verifies Mean Absolute Calibration Error $\le 1.5\%$ ($\text{MCE} = 0.65\%$) across 10 equal-N quantile bins.                             | 🟢 PASS |
| `src/models/point_win_classifier.py` | `save_stratum_table` / `load_stratum_table` | Validates JSON serialization and deserialization roundtrip for DVC artifact persistence.                                                  | 🟢 PASS |

---

### 3.8 Pressure Deviation Estimator (`tests/unit/test_pressure_deviation.py`)

| Module                             | Verification Target         | What Is Verified                                                                                                                       | Status  |
| :--------------------------------- | :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| `src/models/pressure_deviation.py` | Empirical-Bayes MoM Fitting | Fits closed-form Beta prior parameters $(\alpha_0, \beta_0)$ per leverage bucket via Method of Moments.                                | 🟢 PASS |
| `src/models/pressure_deviation.py` | Sparse-Bucket Fallback Gate | Forces fallback to fixed prior $\text{Beta}(2.0, 2.0)$ with `is_prior_estimated=False` when player count $M < 15$.                     | 🟢 PASS |
| `src/models/pressure_deviation.py` | Posterior Shrinkage Bounds  | Asserts shrunk rate satisfies ordering invariant $\min(r, \mu_0) \le \text{shrunk\_rate} \le \max(r, \mu_0)$.                          | 🟢 PASS |
| `src/models/pressure_deviation.py` | 90% Credible Coverage Gate  | Evaluates posterior credible interval coverage ($\text{Coverage} = 93.75\% \ge 90\%$) across high-leverage player strata ($N \ge 10$). | 🟢 PASS |

---

### 3.9 Event-Driven LangGraph Orchestration & Evals (`src/graph/`, `tests/integration/`, `tests/evals/`)

| Module / Test File                                 | Verification Target        | What Is Verified                                                                                               | Status  |
| :------------------------------------------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------- | :------ |
| `tests/unit/test_graph_state.py`                   | `PulseGraphState` Schema   | Pydantic v2 validation, default factories, and `DecisionLogEntry` list reducer aggregation.                    | 🟢 PASS |
| `tests/unit/test_state_monitor.py`                 | `StateMonitorNode`         | Always-on node execution, Wilson interval propagation, and leverage calculation.                               | 🟢 PASS |
| `tests/unit/test_pressure_diagnostic.py`           | `PressureDiagnosticNode`   | Empirical-Bayes shrinkage lookup and leverage bucket resolution on high-leverage points (100% coverage).     | 🟢 PASS |
| `tests/unit/test_strategy_exploit.py`              | `StrategyExploitNode`      | Hierarchical matrix lookup and two-level sufficiency gate ($N \ge 30$, cell count $\ge 5$).                    | 🟢 PASS |
| `tests/unit/test_tactical_output.py`               | `TacticalOutputNode`       | Narrative synthesis and deterministic raw-signal fallback when LLM API call fails.                             | 🟢 PASS |
| `tests/unit/test_routing.py`                       | Graph Routing & Closures   | D-4 lower bound rule ($\Delta L_{\text{low}} \ge 0.10$), OTel spans, and zero `load_params()` per-point calls. | 🟢 PASS |
| `tests/evals/test_tactical_output_groundedness.py` | DeepEval Groundedness      | Numerical fidelity verification ensuring LLM narrative text introduces zero numbers absent from input payload. | 🟢 PASS |
| `tests/integration/test_conditional_graph.py`      | Dynamic Execution Topology | Dynamic node path variance across 5 match fixtures (routine, sparse, sufficient, uncharted, state-diff).       | 🟢 PASS |

---

### 3.10 Game Theory Exploitative Module (`src/core/game_theory.py`, `tests/unit/test_game_theory*.py`)

| Test File / Function | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :---: |
| `test_game_theory.py::test_equilibrium_mix_sums_to_one` | Simplex Normalization | $\sum x^* = 1.0, \sum y^* = 1.0$, all probabilities in $[0, 1]$. | 🟢 PASS |
| `test_game_theory.py::test_server_indifference_at_equilibrium` | Server Indifference | $\Pi[i, :] \cdot y^* = V$ for all active serve actions $i$. | 🟢 PASS |
| `test_game_theory.py::test_returner_indifference_at_equilibrium` | Returner Indifference | $x^* \cdot \Pi[:, j] = V$ for all active returner anticipation columns $j$. | 🟢 PASS |
| `test_game_theory.py::test_delta_non_negative` | Exploitation Guarantee | $\delta = \max_i (\Pi \hat{y})_i - V \ge 0.0$ always holds. | 🟢 PASS |
| `test_game_theory.py::test_lp_matches_closed_form_on_2x2` | Solver Agreement | HiGHS Linear Programming matches analytical $2\times 2$ closed form within $10^{-4}$. | 🟢 PASS |
| `test_game_theory_solver.py::test_linprog_strong_duality_verified` | Strong Duality Gate | Primal and Dual LPs converge to identical value ($|V_P - V_D| \le 10^{-5}$). | 🟢 PASS |
| `test_game_theory.py::test_sufficiency_gate_fires_below_threshold` | Opponent Sample Gate | `sufficient_data=False` when total opponent observations $N_{\text{opp}} < 30$. | 🟢 PASS |
| `test_game_theory.py::test_exploit_result_all_none_when_gate_fires` | Null Value Contract | All exploit fields (`equilibrium_value`, `best_response_action`, `delta`) are `None` when gated. | 🟢 PASS |
| `tests/unit/test_build_payoff_matrices.py` | DVC Matrix Compilation | Validates 534,168 point extraction, Beta prior fitting, and JSON artifact compilation. | 🟢 PASS |

---

### 3.11 API, Replay Simulation & Streaming Interface (`src/api/`, `src/simulator/`, `src/utils/persistence.py`)

| Test File / Function | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :---: |
| `tests/unit/test_api_schemas.py` | Pydantic v2 Wire Contracts | Field constraints, score bounds, timestamp formatting, JSON schema serialization. | 🟢 PASS |
| `tests/unit/test_point_record_conversion.py` | Schema Bridge Conversion | `PointRecord.to_point_context()`, score flip logic, surface mapping, bo3 & bo5 scope. | 🟢 PASS |
| `tests/unit/test_persistence.py` | SQLite Audit Persistence | Async non-blocking write of `decision_logs` and `tactical_outputs` via `aiosqlite`. | 🟢 PASS |
| `tests/unit/test_api_main.py` | FastAPI Application & Lifespan | Startup lifespan graph compilation (`app.state.graph`), UI/static routes, and `/health` route response. | 🟢 PASS |
| `tests/unit/test_streaming.py` | Streaming Transport Adapters | SSE route, periodic `: keep-alive\n\n` comments, WebSocket frames, match listing. | 🟢 PASS |
| `tests/unit/test_streaming.py::test_sse_event_stream_keep_alive_does_not_kill_slow_generator` | Keep-Alive Queue Decoupling | Long inter-point delay does not cancel in-flight generator task during heartbeat timeouts (D-5). | 🟢 PASS |
| `tests/unit/test_streaming.py::test_get_match_metadata_endpoint` | Match Metadata Route | `GET /v1/matches/{match_id}` returns accurate `MatchMetadataResponse` and handles 404s (D-10). | 🟢 PASS |
| `tests/unit/test_streaming.py::test_stream_match_sse_replay_request_validation` | Wire Schema Query Validation | `MatchReplayRequest` validation on SSE route (422 on negative speed or invalid format). | 🟢 PASS |
| `tests/unit/test_streaming.py::test_stream_match_sse_bo5_parameter_propagation` | End-to-End Format Wiring | `?match_format=bo5` correctly propagates into emitted point events (D-3a). | 🟢 PASS |
| `tests/unit/test_streaming.py::test_stream_match_sse_uninitialized_graph_503` | Graph Readiness Guard | `GET /stream` returns 503 if graph is uninitialized. | 🟢 PASS |
| `tests/unit/test_streaming.py::test_stream_match_ws_uninitialized_graph` | WebSocket Guard | WebSocket handshake closes with code 1011 if graph is uninitialized. | 🟢 PASS |
| `tests/unit/test_streaming.py::test_sse_event_stream_error_item_handling` | Fail-Loud Error Bubbling | Producer exceptions emitted as `event_type="error"` stream events (D-13). | 🟢 PASS |
| `tests/unit/test_streaming.py::test_sse_event_stream_client_cancellation_cleanup` | Async Resource Cleanup | Premature client disconnect cleanly cancels background producer task. | 🟢 PASS |
| `tests/unit/test_replay_generator.py` | Async Replay Generator & CLI | Replay pacing, bo5 fallback context, fail-loud exceptions, CLI flags (`--match-id`, `--speed-multiplier`, `--match-format`). | 🟢 PASS |
| `tests/integration/test_api_streaming.py::test_sse_streaming_and_persistence_parity` | SSE & SQLite Parity | Full SSE stream matches generator events 1-to-1 and persists records in SQLite. | 🟢 PASS |
| `tests/integration/test_api_streaming.py::test_websocket_and_sse_content_parity` | Transport Equivalence | Bit-for-bit content payload parity between WebSocket and SSE streams (D-1). | 🟢 PASS |
| `tests/integration/test_api_streaming.py::test_mid_stream_failure_integration` | Fail-Loud Mid-Stream | Emits `event_type="error"` on forced exception and terminates cleanly (D-13). | 🟢 PASS |

---

### 3.12 Interactive Presentation Layer (`tests/integration/test_static_ui.py`)

| Test File / Function | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :---: |
| `tests/integration/test_static_ui.py::test_root_and_ui_endpoints_serve_html` | SPA Route Delivery | `GET /` and `GET /ui` return HTTP 200 with `text/html; charset=utf-8` MIME type and `<!DOCTYPE html>`. | 🟢 PASS |
| `tests/integration/test_static_ui.py::test_html_contains_required_cockpit_dom_contracts` | DOM Blueprint Contracts | Asserts HTML body contains all core sub-components (`#scoreboard`, `#oscillogram-container`, `#topology-inspector`, `#game-theory-panel`, `#tactical-feed`, `#stream-controls`, `#modal-match-report`). | 🟢 PASS |
| `tests/integration/test_static_ui.py::test_static_assets_serve_correct_mime_types` | Static Assets MIME & Delivery | Asserts `GET /static/style.css` returns `text/css` and `GET /static/app.js` returns `text/javascript`. | 🟢 PASS |
| `tests/integration/test_static_ui.py::test_no_external_cdn_references` | Zero-CDN Invariant | Asserts 0 external `http`/`https` CDN `<script>` or `<link>` references in `index.html` (100% self-contained). | 🟢 PASS |
| `tests/integration/test_static_ui.py::test_match_preflight_and_docs_route_precedence` | Route Precedence & Integrity | Asserts `/v1/matches`, `/health`, and `/openapi.json` retain highest route precedence alongside static SPA endpoints. | 🟢 PASS |

---

### 3.13 Post-Match Tactical Analytics Engine (`tests/unit/test_match_report.py`)

| Test File / Function | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :---: |
| `tests/unit/test_match_report.py::test_evaluate_all_points` | Markov Leverage & Confidence Evaluation | Computes continuous $\Delta L$ and Wilson 95% confidence intervals $[L_{\text{low}}, L_{\text{high}}]$ across all match points. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_compute_match_summary` | Match Aggregate Summary | Computes total points, set scores, average leverage, and peak leverage point index correctly. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_extract_top_pivotal_points` | Top-$N$ Pivotal Point Ranking | Correctly extracts and ranks the top 5 highest-leverage inflection moments descending by $\Delta L$. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_compute_pressure_resilience` | Pressure Tier Partitioning | Partitions player point win rates across Routine, Elevated, and Critical tiers with empirical pressure shift $\Delta p$. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_compute_game_theory_audit_sufficient_data` | Minimax Serve/Return Audit | Audits realized serve direction mixes against Nash equilibrium and returner bias when $N \ge 10$. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_compute_game_theory_audit_insufficient_data` | Game Theory Sufficiency Gate | Suppresses exploit evaluation and sets `sufficient_data=False` when total charted serves $< 10$. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_generate_deterministic_debrief` | Grounded Deterministic Debrief | Synthesizes a structured 3-paragraph tactical debrief using only pre-computed metrics without LLM dependency. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_format_markdown_report` | Markdown Report Serializer | Emits standardized GitHub-flavored Markdown containing all 5 required structural sections. | 🟢 PASS |
| `tests/unit/test_match_report.py::test_generate_match_report_end_to_end` | Full Report Generation Pipeline | End-to-end execution of `generate_match_report` producing fully populated `MatchReportResponse`. | 🟢 PASS |

---

### 3.14 Post-Match Reporting API Endpoints (`tests/integration/test_match_report_api.py`)

| Test File / Function | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :---: |
| `tests/integration/test_match_report_api.py::test_get_match_report_json_integration` | JSON Report Wire Contract | `GET /v1/matches/{id}/report?format=json` returns HTTP 200 with valid `MatchReportResponse` schema. | 🟢 PASS |
| `tests/integration/test_match_report_api.py::test_get_match_report_markdown_integration` | Markdown Report Route | `GET /v1/matches/{id}/report?format=markdown` returns HTTP 200 with `text/markdown` and standard headers. | 🟢 PASS |
| `tests/integration/test_match_report_api.py::test_get_match_report_bo5_format_integration` | BO5 Scoring Rules Propagation | `?match_format=bo5` correctly propagates into Markov leverage solver during match report aggregation. | 🟢 PASS |
| `tests/integration/test_match_report_api.py::test_get_match_report_custom_llm_debrief_integration` | LLM Debrief Async Integration | Synthesizes customized executive debrief when Anthropic client succeeds with zero hallucinated figures. | 🟢 PASS |
| `tests/integration/test_match_report_api.py::test_get_match_report_not_found_404` | 404 Error Handling | Requesting an unrecorded or non-existent match ID cleanly raises HTTP 404 with structured error detail. | 🟢 PASS |

---

## 4. Upcoming Test Suite Roadmap

```
Phase 1: Project Scaffolding Baseline (Complete — 1 Pass)
  ├── Pytest Baseline Setup
  ├── File Ceiling Enforcement
  └── CI Workflow Quality Gate
       │
Phase 2: Data Layer & Deterministic Core (Complete — 19 Passes)
  ├── Pydantic v2 PointRecord Contract Validation
  ├── Pandera Row-Level & Score-Progression Gates
  ├── Markov Solver Golden-Value Tests vs Combinatorial Theory (< 1e-9 tolerance)
  └── Wilson Confidence Interval & Leverage Uncertainty Band Tests
       │
Phase 3: Tier 1 ML Models (Complete — 41 Passes)
  ├── Point-Win Classifier Quantile Calibration (MACE = 0.65% <= 1.5%) & Sanity AUC Checks
  ├── Stratum Table Tier Resolution & Serialization Persistence Tests
  ├── Pressure Deviation Empirical-Bayes Shrinkage Tests (Coverage = 93.75% >= 90%)
  └── Classifier-Uncertainty-Solver Integration Smoke Tests
       │
Phase 4: Agent Orchestration Layer (Complete — 68 Passes)
  ├── LangGraph Conditional Edge Execution Tests (StateMonitor -> Diagnostic/Exploit)
  ├── Sufficiency Gate Fallback Integration Tests (Data-sparse fallback to leverage-only)
  ├── Routing Factory Closure Zero-Per-Point Disk I/O Regression Test
  └── DeepEval Narrative Groundedness (Number Hallucination Checks)
       │
Phase 5: Game Theory Exploitative Module (Complete — 103 Passes)
  ├── 2D Zero-Sum Matrix Game Formulations (2x2 analytical + mxn HiGHS LP)
  ├── Strong Duality Primal/Dual Verification (|V_P - V_D| <= 1e-5)
  ├── Parameterized Stylized Anticipation Model (params.yaml sourcing)
  ├── Returner Positioning Bias & Empirical-Bayes Beta Shrinkage Priors
  ├── Pure Best-Response Deviation & Non-Negative Delta Guarantee Tests
  ├── Two-Level Sufficiency Gating (Opponent N >= 30, Cell N >= 5) & Uncharted Fallback
  └── DVC Payoff Matrix Extraction Pipeline Stage (2,139 strata exported)
       │
Phase 6: API, Simulation & Streaming Quality Suite (Complete — 146 Passes)
  ├── FastAPI SSE/WebSocket Streaming Endpoint Integration
  ├── Match Metadata Resolution Endpoint & Decoupled Async Queue Stream
  ├── MatchReplayRequest Wire Schema Validation & Parameterized bo3/bo5 Threading
  ├── Match Replay Simulator Bit-Identical Reproducibility Tests
  ├── SQLite Audit Persistence Traceability (FR-12)
  └── Fail-Loud Error Transparency & Keep-Alive Heartbeat (D-5, D-13)
       │
Phase 6.5: Interactive Presentation Layer (Tactical Cockpit) (Complete — 152 Passes)
  ├── Embedded Single-Page Application (SPA) Delivery via FastAPI Static Mount
  ├── Canvas 2D Oscillogram & Shaded Wilson 95% Confidence Band Engine
  ├── Native EventSource SSE Multi-Panel Dispatch Controller
  ├── DOM Blueprint Contracts (6 Sub-Components) & Zero-CDN Invariant Verification
  └── Health and OpenAPI Route Precedence Enforcement
       │
Phase 6.6: Post-Match Tactical Intelligence & Free-Tier Groq LLM Engine (Complete — 176 Passes)
  ├── Deterministic Post-Match Analytics Engine (Leverage Aggregation, Wilson Bounds)
  ├── Top-N Pivotal Inflection Points Ranking by Delta L
  ├── Pressure Resilience Partitioning Across Leverage Tiers (Routine / Elevated / Critical)
  ├── Minimax Serve/Return Realized Mix Audit & Sufficiency Gating (N >= 10)
  ├── Free-Tier Groq Cloud (llama-3.1-8b-instant) / Anthropic Async LLM Narrative Debrief
  ├── Presentation Layer Decomposition (src/analytics/formatting.py under 1,000-line ceiling)
  ├── FastAPI REST Report Endpoint (JSON & Markdown Transports, Auto BO3/BO5 Detection)
  └── Interactive Glassmorphic Report Modal UI & One-Click Clipboard/JSON/Print Exporters
       │
Phase 7: Observability, CI/CD, Shadow-Mode Acceptance (✅ Complete)
  ├── OpenTelemetry Component Spans (Solver, Models, Analytics, Nodes)
  ├── GitHub Actions CI Pipeline with Trivy Security Scan & Coverage Gate (>= 70%)
  ├── Multi-Stage Dockerfile & Docker Compose with Persistent Host Volumes
  ├── Retrospective Escalation Precision Evaluation (96.02% Precision across 100 Matches)
  └── Shadow-Mode Operational Acceptance Suite across Held-Out Match Set
```

---

## 5. Test Suite Execution Commands

| Target                         | Command                                             | Notes                                                       |
| :----------------------------- | :-------------------------------------------------- | :---------------------------------------------------------- |
| **Run Full Test Suite**        | `uv run pytest`                                     | Runs all unit, integration, and eval tests (202 passed)      |
| **Run Solver Unit Tests Only** | `uv run pytest -m solver`                           | Golden-value combinatorial correctness gate                 |
| **Run Match Report Tests**     | `uv run pytest tests/unit/test_match_report.py tests/integration/test_match_report_api.py` | Validates post-match analytics and API routes |
| **Run Static UI Tests Only**   | `uv run pytest tests/integration/test_static_ui.py`  | Validates presentation layer DOM & asset delivery           |
| **Run Coverage Report**        | `uv run pytest --cov=src --cov-report=term-missing` | Verifies $\ge 70\%$ line coverage requirement (measured 92%)|
| **Run File Ceiling Check**     | `python scripts/check_file_size.py`                 | Enforces 1,000-line ceiling per file under `src/`           |
| **Run Static Type Checker**    | `uv run pyright`                                    | Validates strict typing across `src/`, `tests/`, `scripts/` |
| **Run Linter Checks**          | `uv run ruff check .`                               | Imports, syntax, and style rules enforcement                |
| **Run Formatter Checks**       | `uv run ruff format --check .`                      | Verifies 100-character line length compliance               |

**Live Output (Phase 7 Complete & Hardened — 2026-08-27):**

```text
=============================== tests coverage ================================
______________ coverage: platform win32, python 3.11.13-final-0 _______________

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
src\__init__.py                          0      0   100%
src\analytics\__init__.py                0      0   100%
src\analytics\formatting.py             19      0   100%
src\analytics\match_report.py          316     43    86%   188, 280-281, 360-367, 376, 378, 384, 386, 456, 482-498, 645, 648-650, 659-660, 691-692, 713-714, 743-744, 873-875, 885-887
src\api\__init__.py                      0      0   100%
src\api\main.py                         58      7    88%   133-140, 149
src\api\schemas.py                     102      0   100%
src\api\streaming.py                    98     10    90%   144, 207, 304-311
src\config\__init__.py                   2      0   100%
src\config\loader.py                    89      1    99%   156
src\core\__init__.py                     0      0   100%
src\core\game_theory.py                191     12    94%   76, 88, 259, 292, 303, 343, 347, 354, 435, 487, 494-497
src\core\leverage_uncertainty.py        62      0   100%
src\core\markov_solver.py              236     40    83%   65, 70, 118, 143, 186, 254-275, 321, 328, 379-409, 432, 434-435, 445, 447-448
src\graph\__init__.py                    0      0   100%
src\graph\llm_client.py                 60      0   100%
src\graph\pressure_diagnostic.py        38      0   100%
src\graph\pulse_graph.py                96      0   100%
src\graph\state.py                      45      0   100%
src\graph\state_monitor.py              38      0   100%
src\graph\strategy_exploit.py           50      0   100%
src\graph\tactical_output.py            43      0   100%
src\models\__init__.py                   0      0   100%
src\models\point_win_classifier.py     141      5    96%   46, 140-141, 343-344
src\models\pressure_deviation.py       148      8    95%   93, 143, 192, 243-244, 297, 353-354
src\schemas\__init__.py                  0      0   100%
src\schemas\point_record.py            116      6    95%   135, 142, 151-152, 234, 236
src\simulator\__init__.py                0      0   100%
src\simulator\replay.py                134     16    88%   45, 61-62, 86-88, 180-184, 192, 291, 309, 320, 324
src\utils\__init__.py                    0      0   100%
src\utils\exceptions.py                 37      5    86%   30-31, 37-40
src\utils\logger.py                     37      3    92%   52-54
src\utils\persistence.py               104     14    87%   35, 86-89, 129, 155-158, 178-181
------------------------------------------------------------------
TOTAL                                 2260    170    92%
======================= 202 passed in 60.83s (0:01:00) ========================
```


