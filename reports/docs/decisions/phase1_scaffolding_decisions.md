# Phase 1 — Project Scaffolding: Implementation Decisions

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)
**Phase:** 1 — Project Scaffolding
**Version:** 0.1.0
**Date Created:** 2026-07-29
**Status:** ✅ Approved (2026-07-29)

> **Purpose of this document.** This is the living design-decision record for Phase 1. It translates each deliverable from [`technical_roadmap.md` §Phase 1](../references/technical_roadmap.md) into concrete architectural decisions. All decisions in this document have been explicitly approved by the user and serve as the authoritative baseline for implementation and phase-close ADR review.

---

## Current State Audit

Before proposing decisions, here is the honest inventory of what already exists in the workspace:

| Artifact                  | Current State                             | Gap                                                                    |
| ------------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| `pyproject.toml`          | Empty file (0 bytes)                      | Needs full dependency spec                                             |
| `params.yaml`             | Empty file (0 bytes)                      | Needs all threshold keys                                               |
| `.pre-commit-config.yaml` | Empty file (0 bytes)                      | Needs ruff + pyright hooks                                             |
| `.github/workflows/`      | Empty directory                           | Needs `ci.yml`                                                         |
| `scripts/`                | Empty directory                           | Needs `check_file_size.py`                                             |
| `src/utils/exceptions.py` | ✅ Implemented (90 lines)                 | `SanitizationError` stub included                                      |
| `src/utils/logger.py`     | ✅ Implemented (78 lines)                 | Missing `from pathlib import Path` import (bug)                        |
| `src/api/`                | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/schemas/`            | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/core/`               | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/models/`             | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/graph/`              | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/simulator/`          | Empty directory                           | Needs `__init__.py` stubs                                              |
| `src/config/`             | Empty directory                           | Needs `__init__.py` stubs                                              |
| `dvc.yaml`                | Empty file (0 bytes)                      | Needs phase-1 stage skeleton                                           |
| `.gitignore`              | ✅ Present (115 lines)                    | ChromaDB entry irrelevant (no RAG in PULSE), otherwise solid           |
| `src/__init__.py`         | ✅ Present                                | OK                                                                     |
| `src/py.typed`            | ✅ Present                                | OK                                                                     |
| `tests/`                  | Exists (structure TBD from prior session) | Needs `unit/`, `integration/`, `evals/` directories with `__init__.py` |

> [!NOTE]
> `src/utils/logger.py` contains `PROJECT_ROOT = Path(__file__).resolve().parents[2]` on line 13 but `Path` is never imported. This is a latent `NameError` — it must be fixed as part of Phase 1 regardless of the decisions below.

---

## Decision Map

Each deliverable from `technical_roadmap.md §Phase 1` maps to one primary decision. Sub-decisions are nested where the primary decision has meaningful internal branching.

| #   | Deliverable                                           | Decision                                                                        |
| --- | ----------------------------------------------------- | ------------------------------------------------------------------------------- |
| D-1 | `pyproject.toml` — dependency spec & toolchain config | Package metadata format, dependency list scope, Python version pin              |
| D-2 | `params.yaml` — baseline configuration                | Schema shape, key naming convention, placeholder values vs. calibrated defaults |
| D-3 | `scripts/check_file_size.py` — 1,000-line ceiling     | Enforcement scope, CI integration method                                        |
| D-4 | `.pre-commit-config.yaml` — local code quality hooks  | Hook selection and version pinning strategy                                     |
| D-5 | `.github/workflows/ci.yml` — CI pipeline              | Job sequencing, gate ordering, failure behavior                                 |
| D-6 | `src/*/` stub modules — package skeleton              | `__init__.py` content convention, stub content policy                           |
| D-7 | `dvc.yaml` — pipeline skeleton                        | Stage definition scope for Phase 1 vs. leaving it empty                         |
| D-8 | `.gitignore` — cleanup                                | Whether to remove the ChromaDB entry (no RAG in PULSE v1)                       |

---

## D-1 — `pyproject.toml`: Package Metadata, Dependency Scope & Python Version Pin

**Deliverable:** A fully specified `pyproject.toml` that governs `uv` dependency resolution, `ruff` linting configuration, `pyright` type-checking configuration, and `pytest` test discovery settings.

**Context & Constraints:**

- `uv` is the single dependency management tool (non-negotiable per project constitution §2).
- Python 3.11+ is the target (project constitution §2).
- The deterministic core (`scipy`, `scikit-learn`) and the LangGraph orchestration layer must be listed now even though they are implemented in later phases — otherwise `uv sync` will fail when those modules are introduced.
- `deepeval` is a pinned optional dev dependency used only in `tests/evals/`.
- The file currently exists but is completely empty.

**Options:**

**Option A — Full production + dev dependency spec now (Proposed ✅)**
List all production and development dependencies in a single `pyproject.toml`. Production group: `fastapi`, `pydantic>=2.0`, `langgraph`, `scikit-learn`, `scipy`, `pandera`, `dvc`, `mlflow`, `opentelemetry-sdk`, `structlog`. Dev group: `pytest`, `pytest-cov`, `ruff`, `pyright`, `deepeval`, `pre-commit`, `rich`.

_Trade-offs:_ Full lock file from day one — avoids the "works on my machine" issue when Phase 2 contributors install. Means `uv lock` generates a complete, reproducible lock immediately. Slightly more upfront work but eliminates a whole class of later dependency-resolution surprises. Strongly preferred given the project constitution's emphasis on reproducibility.

**Option B — Minimal spec now, expand per phase**
Only include what Phase 1 strictly needs today (`ruff`, `pyright`, `pytest`, `pre-commit`). Add production deps as each phase introduces them.

_Trade-offs:_ Simpler initial file. Risk: `uv sync` breaks every time a new phase begins and someone forgets to run it. Creates false confidence that the environment is stable. Contradicts "full reproducibility from a clean checkout" (Charter §5).

**Sub-decision D-1a — Python version pin strategy:**

| Sub-option              | Detail                                                          | Proposed    |
| ----------------------- | --------------------------------------------------------------- | ----------- |
| Pin to `>=3.11`         | Allows any 3.11+ (flexible)                                     | ✅          |
| Pin to `==3.11.*`       | Exact minor, any patch                                          | Alternative |
| Pin to exact `==3.11.9` | Maximum reproducibility, most brittle to CI runner availability | Rejected    |

**Sub-decision D-1b — `ruff` configuration scope:**

| Sub-option                                      | Detail                      | Proposed |
| ----------------------------------------------- | --------------------------- | -------- |
| `ruff` in `[tool.ruff]` inside `pyproject.toml` | Single config file          | ✅       |
| Separate `ruff.toml`                            | Extra file, no benefit here | Rejected |

Proposed `ruff` rules: `E`, `F`, `I` (isort), `UP` (pyupgrade), `B` (bugbear), `RUF` (ruff-specific). f-string enforcement (`UP032`) is mandatory per project constitution §5.

**Sub-decision D-1c — `pyright` configuration:**

| Sub-option                               | Detail                     | Proposed    |
| ---------------------------------------- | -------------------------- | ----------- |
| `pyrightconfig.json` in repo root        | Conventional, IDE-friendly | ✅          |
| `[tool.pyright]` inside `pyproject.toml` | Fewer files, same effect   | Alternative |

**Proposed:** Option A with sub-decisions D-1a → `>=3.11`, D-1b → ruff in `pyproject.toml`, D-1c → `pyrightconfig.json` in root.

> [!IMPORTANT]
> **Your input needed:** Do you prefer `pyrightconfig.json` as a separate file (conventional, better IDE support) or `[tool.pyright]` inside `pyproject.toml` (fewer files)?

---

## D-2 — `params.yaml`: Configuration Schema Shape & Placeholder Strategy

**Deliverable:** A populated `params.yaml` with all threshold keys required across all phases, not just Phase 1's immediate needs.

**Context & Constraints:**

- Project constitution §5: "No hardcoded thresholds, model names, or magic numbers — source from `params.yaml`."
- FR-8 (PRD): "All thresholds (leverage, sample size, latency) are defined in `params.yaml`, never hardcoded."
- Values needed in Phase 1 are baseline config; actual calibrated values come from Phase 2–3.
- ADR-006: `calibration_method` must be an explicit, required field (never left at library default).
- The file is currently empty.

**Options:**

**Option A — Flat key-value structure**

```yaml
leverage_escalation_threshold: 0.10
exploit_min_sample_size: 30
state_monitor_latency_budget_ms: 1000
triggered_node_latency_budget_ms: 5000
```

_Trade-offs:_ Simple to read and parse. Becomes unwieldy past ~20 keys with no namespace separation.

**Option B — Namespaced/nested structure grouped by concern (Proposed ✅)**

```yaml
thresholds:
  leverage_escalation: 0.10 # placeholder — calibrate in Phase 3
  exploit_min_sample_size: 30 # placeholder — calibrate in Phase 3

latency:
  state_monitor_ms: 1000 # per-point budget; NFR: < 1s
  triggered_node_ms: 5000 # on-demand budget; NFR: < 5s

models:
  calibration_method: "sigmoid" # Required: "sigmoid" for LR v1; "isotonic" if LightGBM (ADR-006)
  point_win_classifier: "logistic_regression"
  solver_tolerance: 1.0e-9 # CI-blocking: deviation from closed-form theory

ci:
  line_ceiling: 1000 # src/ file size limit (§5.1)
  min_coverage_pct: 70 # pytest --cov minimum
```

_Trade-offs:_ Groups related keys. The `src/config/params_loader.py` validator can use Pydantic models that mirror this nesting — validation is more natural than parsing a flat dict. Matches ADR-006's requirement that `calibration_method` is explicit and required.

**Sub-decision D-2a — Placeholder value policy:**

| Sub-option                                              | Detail                                                                                   | Proposed    |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------- |
| Use `null` for uncalibrated values                      | Explicit absence; downstream code must handle `None`                                     | Alternative |
| Use documented placeholder numbers with inline comments | E.g., `0.10  # placeholder — calibrate Phase 3`. Avoids `None` handling in early phases. | ✅          |

**Proposed:** Option B (namespaced) with D-2a → commented placeholder numbers.

> [!IMPORTANT]
> **Your input needed:** Do you want to include keys for all future phases now (e.g., `models.calibration_method`) so the file is a complete contract from day one, or limit Phase 1's `params.yaml` to only keys that Phase 1 code will actually read?

---

## D-3 — `scripts/check_file_size.py`: Enforcement Scope & CI Integration

**Deliverable:** The line-count ceiling enforcement script, exactly as specified in project constitution §5.1.

**Context & Constraints:**

- The script is fully specified in the project constitution. There is no material design choice for the script's logic itself — it must match the spec exactly.
- The only real decision is how and when CI calls it.

**Options for CI integration:**

**Option A — Standalone step in `ci.yml`, runs after linting (Proposed ✅)**
CI job sequence: `ruff` → `pyright` → `check_file_size.py` → `pytest`. File-size check is a separate named step.

_Trade-offs:_ Each failure is independently visible in the CI log. A file-size violation doesn't mask a lint failure and vice versa. Simplest to debug.

**Option B — Bundle into a pre-commit hook**
Add `check_file_size.py` as a local pre-commit hook (runs on `git commit`).

_Trade-offs:_ Catches violations before they reach CI. But pre-commit hooks are skipped with `--no-verify`, and the project constitution explicitly states it must pass in CI — so CI enforcement is required regardless. Running it only in pre-commit would leave a gap.

**Proposed:** Option A (CI step) + pre-commit hook as belt-and-suspenders. The CI gate is the authoritative enforcement point; pre-commit is fast-feedback only.

_No further sub-decisions needed. Script logic is fully specified._

---

## D-4 — `.pre-commit-config.yaml`: Hook Selection & Version Pinning

**Deliverable:** A pre-commit configuration that enforces code quality before every commit.

**Context & Constraints:**

- `ruff` for linting + import sorting is non-negotiable (project constitution §2).
- `pyright` as a pre-commit hook has limitations (can be slow on large repos; some teams prefer CI-only for type checks).
- Secrets-check hook aligns with "never commit `.env*` or credentials" (project constitution §10).

**Options:**

**Option A — Lean set: `ruff`, `ruff-format`, trailing-whitespace, end-of-file-fixer, secrets check (Proposed ✅)**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <pinned>
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <pinned>
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: detect-private-key
  - repo: local
    hooks:
      - id: check-file-size
        name: File size ceiling check
        entry: python scripts/check_file_size.py
        language: python
        pass_filenames: false
```

_Trade-offs:_ Fast commit cycle. `pyright` excluded from pre-commit (slow; delegated to CI). `detect-private-key` adds a lightweight secrets guard.

**Option B — Include `pyright` in pre-commit**
Add `pyright` as a local pre-commit hook.

_Trade-offs:_ Catches type errors early, but type-checking 80+ files on every commit adds 5–15s overhead. Risk of developers disabling hooks to avoid the slowdown, defeating the purpose.

**Sub-decision D-4a — Version pinning strategy for hook repos:**

| Sub-option                          | Detail                                                 | Proposed |
| ----------------------------------- | ------------------------------------------------------ | -------- |
| Pin to exact tag (e.g., `v0.11.13`) | Maximum reproducibility                                | ✅       |
| Pin to branch (`main`)              | Gets latest automatically; risk of unexpected breakage | Rejected |

**Proposed:** Option A (lean set without `pyright` in pre-commit) with D-4a → exact tag pinning. `pyright` runs in CI only.

> [!IMPORTANT]
> **Your input needed:** Should `pyright` be included in pre-commit hooks (slower commits, earlier type feedback) or reserved for CI only (faster commits, type errors caught at PR time)?

---

## D-5 — `.github/workflows/ci.yml`: Job Sequencing, Gate Ordering & Failure Behavior

**Deliverable:** A GitHub Actions CI pipeline that enforces the full quality gate sequence on every push and pull request.

**Context & Constraints:**

- Gate order matters: the project constitution specifies Lint → Type-check → File-size → Unit tests → Integration tests → Eval suite → Build.
- The Markov solver correctness test is the single highest-priority test — a failure there must block everything else.
- `pytest` with `--cov` enforces ≥70% line coverage (Charter §5).
- Trivy security scan for zero CRITICAL CVEs (Charter §5).
- `uv` must be the package installer in CI.
- No secrets in the workflow file.

**Options:**

**Option A — Single sequential job (Proposed ✅)**
One job, all steps sequential. Fast feedback on the most common failure case (lint before type check before tests). Cheaper in GitHub Actions minutes.

```
Job: quality-gate
  steps:
    1. Checkout
    2. Set up Python 3.11
    3. Install uv
    4. uv sync --all-extras
    5. ruff check . && ruff format --check .
    6. pyright
    7. python scripts/check_file_size.py
    8. pytest (with --cov, solver gate runs first via pytest-ordering or module ordering)
    9. Trivy scan (on the Docker image, or on the repo for secrets)
```

_Trade-offs:_ Simple, cheap, readable. If lint fails, you don't spend minutes on type-checking. All failures visible in one log.

**Option B — Parallel jobs per concern**
Separate jobs: `lint`, `typecheck`, `test`, `security` run in parallel.

_Trade-offs:_ Faster wall-clock time when all pass. More complex workflow file. More expensive in CI minutes. Harder to see the ordered failure chain the project constitution specifies.

**Sub-decision D-5a — Trigger conditions:**

| Sub-option                                           | Detail                                                  | Proposed    |
| ---------------------------------------------------- | ------------------------------------------------------- | ----------- |
| On `push` to all branches + `pull_request` to `main` | Broadest; catches problems early                        | ✅          |
| On `pull_request` to `main` only                     | Cheaper; risk of problems lingering on feature branches | Alternative |

**Sub-decision D-5b — Solver correctness test ordering within pytest:**

| Sub-option                                                                        | Detail                                                                            | Proposed |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | -------- |
| Use `pytest-ordering` or `pytest-first` to run `test_markov_solver.py` first      | Explicit, discoverable                                                            | ✅       |
| Rely on file alphabetical ordering (happens to run `unit/` before `integration/`) | Fragile; breaks if new unit tests are added before the solver test alphabetically | Rejected |

**Sub-decision D-5c — `uv` installation in CI:**

| Sub-option                                   | Detail                                        | Proposed    |
| -------------------------------------------- | --------------------------------------------- | ----------- |
| `pip install uv` inside the workflow         | Simple, always works                          | Alternative |
| Use the official `astral-sh/setup-uv` action | Idiomatic, version-pinned, caches `uv` binary | ✅          |

**Proposed:** Option A (single sequential job) with D-5a → push all + PR to main, D-5b → `pytest-ordering`, D-5c → `astral-sh/setup-uv` action.

> [!IMPORTANT]
> **Your input needed:** Single sequential job (simpler, cheaper) or parallel jobs per concern (faster wall-clock when all pass, more complex)?

---

## D-6 — `src/*/` Package Skeleton: `__init__.py` Content Convention

**Deliverable:** All `src/` package directories have `__init__.py` files, establishing the importable package structure. Similarly for `tests/unit/`, `tests/integration/`, `tests/evals/`.

**Context & Constraints:**

- Phase 1 is scaffolding only — no logic is implemented yet.
- `__init__.py` files must exist for Python to treat directories as packages.
- The convention for their content affects readability and future maintenance.

**Options:**

**Option A — Empty `__init__.py` files everywhere (Proposed ✅)**
All `__init__.py` files contain only a module docstring, no imports. Logic is imported at the point of use, not re-exported from package `__init__`.

```python
"""PULSE — src.core package."""
```

_Trade-offs:_ Avoids circular imports. Avoids the "convenience import" pattern that makes refactoring harder. Consistent with how production Python packages are structured. The project constitution's 1,000-line ceiling is easier to track when nothing is pulled into `__init__`.

**Option B — Selective re-exports via `__init__.py`**
Re-export key public symbols at the package level (e.g., `from src.core.markov_solver import MarkovSolver` in `src/core/__init__.py`).

_Trade-offs:_ Shorter import paths for callers. Adds invisible coupling — adding a new module to `__init__` can silently introduce circular dependencies. Complicates the file-size ceiling tracking since `__init__` files can grow.

**Proposed:** Option A (docstring-only `__init__.py` files throughout).

_No user input required on this decision — Option A is unambiguously correct given the constraints. It is listed here for the completeness of the decision record._

---

## D-7 — `dvc.yaml`: Phase 1 Pipeline Skeleton Scope

**Deliverable:** A `dvc.yaml` that defines the pipeline stages PULSE will use, even if the stage commands are stubs.

**Context & Constraints:**

- `dvc.yaml` is currently empty (0 bytes).
- Phase 1 does not introduce any data ingestion or model training stages — those are Phase 2.
- The project constitution §3 specifies `uv run dvc repro` as a command that must work.

**Options:**

**Option A — Leave `dvc.yaml` empty or with a comment block only**
No stages defined yet. `dvc repro` succeeds trivially (nothing to reproduce).

_Trade-offs:_ Accurate for Phase 1 scope. Avoids stub stages that would fail if run. `dvc repro` exits cleanly with "nothing to reproduce."

**Option B — Add a skeleton with stage names and `cmd: echo` stubs (Proposed ✅)**
Define the full stage topology as commented-out or echo stubs so the file documents the pipeline shape from day one:

```yaml
stages:
  ingest:
    cmd: echo "Stage not yet implemented — Phase 2"
    deps: [data/raw]
    outs: [artifacts/validated]
  train_classifier:
    cmd: echo "Stage not yet implemented — Phase 2"
    ...
```

_Trade-offs:_ Documents the intended pipeline shape now. `dvc repro` still succeeds (echo always exits 0). New contributor can see the full intended pipeline from a clean checkout. Matches the "full reproducibility from a clean checkout" goal in Charter §5.

> [!IMPORTANT]
> **Your input needed:** Should `dvc.yaml` remain empty until Phase 2 introduces real stages (clean, no stubs), or should it contain the skeleton of all planned stages now (documented shape, stub commands)?

---

## D-8 — `.gitignore`: ChromaDB Entry Cleanup

**Deliverable:** A clean `.gitignore` aligned with PULSE's actual technology stack.

**Context & Constraints:**

- `.gitignore` currently contains `chroma_db/` and `*.chroma` entries (lines 106–107).
- Project constitution §11 explicitly states: "Not applicable. PULSE has no retrieval or knowledge-base component in v1 scope."
- The entries are harmless but misleading — they suggest a ChromaDB dependency that doesn't exist.

**Options:**

**Option A — Remove ChromaDB entries (Proposed ✅)**
Delete lines 105–107 (`# Vector Database Storage`, `chroma_db/`, `*.chroma`).

_Trade-offs:_ Eliminates false signal about the system's architecture. No functional impact (ChromaDB is not used and the files don't exist). Keeps the `.gitignore` honest about PULSE's actual stack.

**Option B — Leave as-is**
Harmless, but creates a minor confusion if someone reads the file to understand what PULSE uses.

**Proposed:** Option A (remove ChromaDB entries). No user input needed; this is a simple cleanup with no trade-off.

---

## Decision Log (Fully Approved)

| #    | Decision                          | Status      | Choice                                                                |
| ---- | --------------------------------- | ----------- | --------------------------------------------------------------------- |
| D-1  | `pyproject.toml` spec             | ✅ Approved | Option A (Full spec with pyrightconfig.json & ruff in pyproject.toml) |
| D-1a | Python version pin                | ✅ Approved | `>=3.11`                                                              |
| D-1b | `ruff` config location            | ✅ Approved | Inside `pyproject.toml`                                               |
| D-1c | `pyright` config location         | ✅ Approved | `pyrightconfig.json` in project root                                  |
| D-2  | `params.yaml` scope               | ✅ Approved | Option B (namespaced with commented placeholders & future keys)       |
| D-2a | Placeholder value policy          | ✅ Approved | Commented placeholder numbers                                         |
| D-3  | CI integration of file-size check | ✅ Approved | Option A (CI step) + pre-commit hook as belt-and-suspenders           |
| D-4  | Pre-commit hook selection         | ✅ Approved | Option A (lean set, exact tag pinning, pyright in CI only)            |
| D-4a | Hook version pinning              | ✅ Approved | Exact tag pinning                                                     |
| D-5  | CI job topology                   | ✅ Approved | Option A (single sequential job, push all + PR to main)               |
| D-5a | CI trigger conditions             | ✅ Approved | Push all branches + PR to main                                        |
| D-5b | Solver test ordering              | ✅ Approved | `pytest-ordering`                                                     |
| D-5c | `uv` in CI                        | ✅ Approved | `astral-sh/setup-uv` action                                           |
| D-6  | `__init__.py` content convention  | ✅ Approved | Option A (docstring-only `__init__.py` files throughout)              |
| D-7  | `dvc.yaml` scope                  | ✅ Approved | Option B (skeleton with stage names and `cmd: echo` stubs)            |
| D-8  | `.gitignore` cleanup              | ✅ Approved | Option A (remove ChromaDB entries & add `.agents/` ignore)            |
