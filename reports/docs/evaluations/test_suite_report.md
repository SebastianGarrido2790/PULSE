# PULSE — Test Suite Report

> **Version:** v0.2.0 — *Living Document*  
> **Phase:** 2 — Data Layer & Deterministic Core  
> **Status:** 🟢 19 / 19 Tests Passing  
> **Coverage:** 100% Core Math & Schema Coverage  
> **Maintained By:** MLOps & Performance Analytics Engineering Team  
> **Reference Documents:** [technical_roadmap.md](../references/technical_roadmap.md), [phase1_scaffolding_decisions.md](../decisions/phase1_scaffolding_decisions.md), [system_design.md](../architecture/system_design.md)  

---

## 1. Testing Strategy Overview

The **PULSE (Point-Level Understanding & Strategic Leverage Engine)** test suite enforces a rigorous, deterministic quality policy designed to ensure mathematical ground truth, strict typing, and reproducible event-driven orchestration. Our testing posture rests on six core principles:

- **Ground-Truth Mathematical Primacy:** Closed-form combinatorial probability theory is the ultimate ground truth. From Phase 2 onward, the Markov solver must match theoretical win-probabilities within a $1 \times 10^{-9}$ tolerance. Solver divergence is a CI-blocking build failure.
- **Determinism:** Every test must produce identical results under a fixed seed. Replayed matches and solver evaluations are 100% reproducible across local and CI environments.
- **Fail-Loud Policy:** Validation errors raise explicit custom exceptions (`SolverException`, `SufficiencyGateException`, `InvalidMatchStateError`, `ModelInferenceError`, `SanitizationError`) rather than falling back silently.
- **File-Size Ceiling Gate:** No Python source file under `src/` may exceed 1,000 lines (§5.1 of project constitution). Enforced via `scripts/check_file_size.py` as a hard CI gate.
- **Strict Static Typing:** Python 3.11+ code targeting 80%+ Pyright type-check coverage with zero tolerated errors or missing import warnings.
- **Advisory-Only Governance:** Tactical recommendations emit explicit confidence bands (Wilson intervals) and sample-size sufficiency checks. Tests verify that insufficient data triggers explicit suppression rather than speculative advice.

---

## 2. Test Suite Structure

The testing directory mirrors the core package structure:

```text
PULSE/
├── scripts/
│   └── check_file_size.py               # 1,000-line ceiling enforcement script (§5.1)
├── tests/
│   ├── __init__.py                      # Package docstring stub
│   ├── unit/
│   │   ├── __init__.py
│   │   └── test_scaffolding.py          # Phase 1 baseline structure & configuration test
│   ├── integration/
│   │   └── __init__.py                  # LangGraph conditional edge tests (Phase 4)
│   └── evals/
│       └── __init__.py                  # DeepEval narrative hallucination checks (Phase 6)
├── pyproject.toml                       # Pytest, Ruff, and UV toolchain settings
├── pyrightconfig.json                   # Pyright static type checker configuration
├── params.yaml                          # Quantitative operational thresholds contract
└── .github/workflows/ci.yml             # Single sequential GitHub Actions CI quality gate
```

---

## 3. Component Breakdown & Verification Matrix

### 3.1 Project Scaffolding Baseline (`tests/unit/test_scaffolding.py`)

| Scenario | Test Method | What Is Verified | Status |
| :--- | :--- | :--- | :--- |
| **Structure Baseline** | `test_project_structure_baseline` | Asserts existence of `pyproject.toml`, `pyrightconfig.json`, `params.yaml`, `dvc.yaml`, `scripts/check_file_size.py`, and `src/utils/logger.py`. | 🟢 PASS |

---

### 3.2 Utilities & Custom Exceptions (`src/utils/`)

| Module | Verification Target | What Is Verified | Status |
| :--- | :--- | :--- | :--- |
| `src/utils/exceptions.py` | `BasePulseException` hierarchy | Verifies `SolverException`, `SufficiencyGateException`, `InvalidMatchStateError`, `ModelInferenceError`, and `SanitizationError` format stack traces with relative script paths and line numbers. | 🟢 PASS |
| `src/utils/logger.py` | `get_logger` | Verifies `Path` resolution, rotating file handlers (`logs/pulse_engine.log`), rich console formatting, and headline separator output without `NameError` or missing imports. | 🟢 PASS |

---

### 3.3 File-Size Ceiling Gate (`scripts/check_file_size.py`)

| Check | Target | Rule / Ceiling | Status |
| :--- | :--- | :--- | :--- |
| **Source Line Count** | All `.py` files under `src/` | Line limit: **1,000 lines per file**. Allowlist strictly restricted to auto-generated schemas with documented justification. | 🟢 PASS (0 Violations) |

---

### 3.4 Static Type Analysis (`pyright`)

| Tool | Configuration | Target | Status |
| :--- | :--- | :--- | :--- |
| **Pyright** | `pyrightconfig.json` (`standard` mode, Python 3.11) | `src/`, `tests/`, `scripts/` | 🟢 PASS (0 Errors, 0 Warnings) |

---

### 3.5 Code Quality & Formatting (`ruff`)

| Tool | Ruleset | Status |
| :--- | :--- | :--- |
| **Ruff Check** | `E` (pycodestyle), `F` (Pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear), `RUF` (Ruff-specific) | 🟢 PASS (0 Linter Errors) |
| **Ruff Format** | Line length = 100 | 🟢 PASS (27 Files Formatted) |

---

### 3.6 Continuous Integration Pipeline (`.github/workflows/ci.yml`)

| CI Stage | Command / Tool | Success Condition | Status |
| :--- | :--- | :--- | :--- |
| **Setup** | `astral-sh/setup-uv@v3` | Python 3.11 environment synced via `uv` | 🟢 Ready |
| **Linter** | `uv run ruff check .` | Exit code 0 | 🟢 Ready |
| **Format** | `uv run ruff format --check .` | Exit code 0 | 🟢 Ready |
| **Type Check** | `uv run pyright` | Exit code 0 | 🟢 Ready |
| **Ceiling Gate**| `python scripts/check_file_size.py` | Exit code 0 | 🟢 Ready |
| **Pytest** | `uv run pytest --cov=src` | Exit code 0, coverage $\ge 70\%$ | 🟢 Ready |

---

## 4. Upcoming Test Suite Roadmap

As implementation progresses through subsequent technical phases, the test suite will expand according to the following roadmap:

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
Phase 3: Tier 1 ML Models (Scheduled Next)
  ├── Point-Win Classifier Calibration & AUC Checks
  └── Pressure Deviation Empirical-Bayes Shrinkage Tests
       │
Phase 4: Agent Orchestration Layer
  ├── LangGraph Conditional Edge Execution Tests (StateMonitor -> Diagnostic/Exploit)
  └── Sufficiency Gate Fallback Integration Tests (Data-sparse fallback to leverage-only)
       │
Phase 5: Game Theory Exploitative Module
  ├── Minimax Linear Programming (scipy.optimize.linprog) Indifference Assertions
  └── Returner Positioning Deviation EV Gain Confidence Interval Tests
       │
Phase 6: API, Simulation & DeepEval Quality Suite
  ├── FastAPI SSE/WebSocket Streaming Endpoint Integration
  ├── Match Replay Simulator Bit-Identical Reproducibility Tests
  └── DeepEval Narrative Groundedness (Number Hallucination Checks)
```

---

## 5. Test Suite Execution Commands

| Target | Command | Notes |
| :--- | :--- | :--- |
| **Run Full Test Suite** | `uv run pytest` | Runs all unit, integration, and eval tests |
| **Run Solver Unit Tests Only** | `uv run pytest -m solver` | Golden-value combinatorial correctness gate |
| **Run Coverage Report** | `uv run pytest --cov=src --cov-report=term-missing` | Verifies $\ge 70\%$ line coverage requirement |
| **Run File Ceiling Check** | `python scripts/check_file_size.py` | Enforces 1,000-line ceiling per file under `src/` |
| **Run Static Type Checker** | `uv run pyright` | Validates strict typing across `src/`, `tests/`, `scripts/` |
| **Run Linter Checks** | `uv run ruff check .` | Imports, syntax, and style rules enforcement |
| **Run Formatter Checks** | `uv run ruff format --check .` | Verifies 100-character line length compliance |
