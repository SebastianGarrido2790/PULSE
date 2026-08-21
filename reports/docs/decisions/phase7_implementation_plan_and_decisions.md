# Phase 7 — Implementation Plan & Decisions
**Observability, CI/CD, Shadow-Mode Acceptance**

**Product:** PULSE | **Phase:** 7 of 7 (final) | **Version:** 1.0.0 (Approved) | **Date:** 2026-08-20  
**Status:** 🟢 Approved — Ready for Implementation  
**Authority:** `technical_roadmap.md` (Phase 7), `prd.md` (FR-8, FR-9, FR-10, FR-12, NFR table, §7 Success Metrics)  
**Approved by:** Sebastian (2026-08-20)

---

## 0. How to Read This Document

Same conventions as every prior phase's decisions document:

- **Section 1** is the mandatory current-state audit. It drives Section 2.
- **Section 2** holds one entry per decision. All originally proposed options, trade-offs, and recommendations are preserved in full for the historical record, alongside the approved resolution.
- Sub-decisions are nested under the primary decision they branch from.
- **Section 3** provides the reconciled decision summary matrix.

---

## 1. Current State Audit

### 1.1 Phase 7 Deliverable Files

| File | Status | Notes |
|---|---|---|
| `.github/workflows/ci.yml` | **Exists**, but predates almost everything it needs to gate. Phase 1's own task list already built a baseline `ci.yml` covering lint, type-check, file-size enforcement, and the solver-correctness gate — before integration tests, the eval suite, the game-theory suite, or the API/streaming suite existed. | Phase 7's roadmap entry re-lists "solver-correctness gate" as if it's new — it isn't; what's actually new is everything built since Phase 1 that the pipeline doesn't run yet: integration tests, eval suite, coverage gate, Trivy scan, and a build stage. This is a bring-up-to-date task, not a from-scratch build. |
| `Dockerfile` | Does not exist. Phase 7 scope. | No prior phase touched containerization. |
| `docker-compose.yml` | Does not exist anywhere in the project, and **isn't in Phase 7's own Deliverables list either** — but the project's own established one-click command, `docker compose up --build`, depends on it existing. → **Finding A**. |
| Final evaluation report | Does not exist. Name/location TBD (this document proposes one in D-13). | — |
| Retrospective escalation-precision evaluation script/report | Does not exist. Governing methodology is `pulse_ml_canvas.md` §8 — not available in this conversation. → **VERIFY, blocking D-9**. |
| OTel spans in `core/markov_solver.py`, `models/point_win_classifier.py`, `models/pressure_deviation.py`, `core/game_theory.py` | **Not present**, on all evidence reviewed across every prior phase's code. | Graph-node-level spans exist (`pulse_graph.py`'s routing functions, since Phase 4) — the solver and model layers underneath them do not have their own spans yet. The roadmap's wording ("spans across solver, models, and graph nodes") is accurate: two of the three are still missing. |
| `src/utils/logger.py` | Exists and is used everywhere via `get_logger(__name__)` — but its actual backing implementation (`structlog`-based JSON output, or stdlib `logging` dressed up to look similar) has never been directly reviewed in this conversation. → **VERIFY**. |

### 1.2 Findings

**Finding A — `docker-compose.yml` isn't a listed deliverable, but the project's own one-click command depends on it.** The established "one-click full-stack orchestration" convention (`docker compose up --build`) has no compose file behind it anywhere in the project. Phase 7's Deliverables list (`ci.yml`, `Dockerfile`, final evaluation report) never mentions one either. Building a `Dockerfile` without a `docker-compose.yml` leaves that documented command broken. → folded into **D-4**.

**Finding B — two different evaluations are bundled under one task list, and conflating them would be a mistake.** "Run the retrospective escalation-precision evaluation" and "shadow-mode acceptance run" read as adjacent bullets in the same task list, but they're not the same kind of check. The precision evaluation is a **statistical** measurement against `prd.md` §7's headline target (alert precision ≥ 0.75), and its validity depends on being run against data that wasn't used to fit the artifacts being evaluated. The shadow-mode run is an **operational/integration** confirmation — does the full, containerized, end-to-end system run correctly at match scale, not just on 3-point test fixtures. Treating "held-out" as meaning the same thing for both would either weaken the precision evaluation's statistical validity or over-constrain the shadow-mode run for no reason. → **D-1, D-2**.

**Finding C — a genuine coverage gap already exists in the numbers, not hypothetically.** Phase 6's own literal `pytest-cov` output (already seen, already trusted in this conversation) shows `src/graph/llm_client.py` at **31%** coverage — the untested lines are almost certainly its exception-handling paths, which is to say the exact code that implements the project's own fail-loud/deterministic-passthrough resilience principle for LLM failures. The project-wide aggregate easily clears the 70% NFR target regardless, so an aggregate-only CI gate would never catch this. → **D-8**.

### 1.3 VERIFY Items (Blocking, Before Implementation)

1. **`pulse_ml_canvas.md` §8** — the escalation-precision evaluation's actual methodology. Not available in this conversation; D-9 can only scaffold *where* this evaluation lives, not *how* it's computed, until this is read directly.
2. **`project_charter.md` §5 (Definition of Done)** — this is Phase 7's literal, stated exit criteria ("all items in `project_charter.md` §5 are checked off"). Not available in this conversation. Every decision in this document is written against `prd.md` and the roadmap instead; the actual DoD checklist needs to be read and reconciled against this document before Phase 7 is considered plannable in full, not just before it's considered complete.
3. **`src/utils/logger.py`'s actual implementation** — confirm whether `structlog` JSON output already exists or needs to be introduced for the first time, before scoping D-11's "finalize logging" task.

---

## 2. Decisions

### D-1 🟢 Approved — What "Shadow-Mode Acceptance" Means for a System With No Live Feed to Shadow

> [!IMPORTANT]
> **Approved Resolution: Option A (Held-out-match replay through the full API/Docker stack).**  
> Start the containerized service, drive a set of historical matches through the real `GET /v1/matches/{id}/stream` endpoint (not internal function calls), and confirm the full deployed system behaves correctly end-to-end. This validates the Docker build and API layer in the same pass as the graph/solver logic.

#### Originally Proposed (v0.1.0)

**Context:** "Shadow mode" conventionally means running a new system alongside a live production one, observing without acting. `prd.md`'s own Non-Goals explicitly rule out live data-feed integration for this project — there's nothing to run alongside. The term needs a concrete, honest definition for what this project actually has.

| Option | Description | Trade-off |
|---|---|---|
| **A — Held-out-match replay through the full API/Docker stack** | Start the containerized service, drive a set of historical matches through the real `GET /v1/matches/{id}/stream` endpoint (not internal function calls), and confirm the whole deployed system behaves correctly end to end. | Validates the Docker build and the API layer in the same pass as the graph/solver logic — one run confirms more of the Definition of Done than a narrower check would. Closer to "shadow" in spirit: external, at-arm's-length invocation, not a live feed, but not a unit test either. |
| **B — Held-out-match replay via direct internal function calls** | Call `generate_point_events()` in-process, skip the HTTP/Docker layer entirely. | Faster, simpler to write. Doesn't touch the Dockerfile or the API layer at all, leaving those largely unvalidated by this specific exit criterion. |

**Recommendation: Option A.** Given Docker and the CI build stage are both new this phase, running the acceptance check through the actual deployed artifact — not around it — is what makes this a real acceptance test rather than another integration test with a different name.

---

### D-2 🟢 Approved — "Held-Out" Means Different Things for the Two Bundled Evaluations (Finding B)

> [!IMPORTANT]
> **Approved Resolution: Option A (Treat "held-out" as a genuine statistical holdout for the precision evaluation only).**  
> The escalation-precision evaluation (`ml_canvas.md` §8) evaluates matches not specifically used for manual calibration/debugging, with the limitation stated plainly in the evaluation report. The shadow-mode acceptance run operates as an operational/integration confirmation across full matches.

#### Originally Proposed (v0.1.0)

**Context:** neither the roadmap nor `prd.md` distinguishes these two evaluations' data requirements explicitly.

| Option | Description | Trade-off |
|---|---|---|
| **A — Treat "held-out" as a genuine statistical holdout for the precision evaluation only** | The escalation-precision evaluation (`ml_canvas.md` §8, pending VERIFY) needs matches that weren't used to fit the artifacts it's evaluating — though given the stratum table, pressure priors, and payoff matrices are all fit **per player**, aggregated across every match a player appears in, holding out one match doesn't cleanly remove that player's influence the way a classical ML train/test split would. The honest framing is that this evaluation measures precision on matches not specifically used for manual calibration/debugging, not a leakage-free statistical holdout in the strict sense — and that limitation should be stated in the evaluation report, not implied away. | Precise about what the number actually means, rather than overclaiming statistical rigor the per-player-aggregated artifact design can't fully support. |
| **B — Treat "held-out" identically for both evaluations** | Use the same match set for both the precision evaluation and the shadow-mode run. | Conflates a statistical validity concern with an operational one; simpler to set up, but risks the precision number being read as more rigorous than it is, and unnecessarily constrains which matches can exercise the operational/shadow-mode check. |

**Recommendation: Option A**, with the limitation stated plainly in whatever report cites the precision number — consistent with this project's own standing principle of not presenting a number with more confidence than its basis actually supports.

---

### D-3 🟢 Approved — CI Pipeline Update Scope & Trivy Scan Target

> [!IMPORTANT]
> **Approved Resolution: Option A (Scan the final built Docker image).**  
> Trivy runs against the built container in the pipeline's build stage. This validates both OS-layer base-image CVEs and Python dependency CVEs baked into the deployable artifact, enforcing the "no CRITICAL CVEs" NFR.

#### Originally Proposed (v0.1.0)

**Context:** per 1.1, the existing `ci.yml` needs to catch up to the already-stated target pipeline order (Lint → type-check → file-size check → unit tests → integration tests → eval suite → build) and add a coverage gate and a Trivy scan. The one open question the roadmap's wording doesn't settle: what does Trivy actually scan.

| Option | Description | Trade-off |
|---|---|---|
| **A — Scan the final built Docker image** | Trivy runs against the built container in the pipeline's build stage. | Catches both OS-layer base-image CVEs and the Python dependency CVEs baked into what's actually deployed — the more complete check, and the one that matches "no CRITICAL CVEs" as stated (an NFR about the deployed artifact, not just the source tree). |
| **B — Scan the Python dependency lockfile only** | Trivy (or an equivalent SCA tool) checks `pyproject.toml`/lockfile without a container build. | Faster, runs earlier in the pipeline (no build dependency), but misses base-image OS-layer CVEs entirely — a real gap given the Dockerfile itself is new and unaudited this phase. |

**Recommendation: Option A.** The NFR is about what ships, and only a built-image scan actually checks that.

---

### D-4 🟢 Approved — Docker Build Shape — Single Image, Runtime Entrypoint Override (Resolves Finding A)

> [!IMPORTANT]
> **Approved Resolution: Option A (One image, API as default `CMD`, CLI reachable via runtime override; add `docker-compose.yml`).**  
> A single Dockerfile and image with `api.main` as the default `CMD`. CLI commands (e.g. `uv run simulator.replay --match-id <id>`) are executed via runtime entrypoint override. `docker-compose.yml` is added as an explicit deliverable to support the project's standard `docker compose up --build` one-click orchestration.

#### Originally Proposed (v0.1.0)

**Context:** two runnable entry points exist (`api.main`, `simulator.replay`), sharing one dependency closure, and `docker-compose.yml` needs to exist for the established one-click command to actually work.

| Option | Description | Trade-off |
|---|---|---|
| **A — One image, API as default `CMD`, CLI reachable via runtime override** | `docker run <image>` starts the API by default; `docker run <image> uv run simulator.replay --match-id <id>` runs the CLI in the same image. `docker-compose.yml` defines one service (the API), matching what actually needs to run continuously. | Simplest to build and maintain — one Dockerfile, one image, one dependency closure to keep in sync. Matches the reality that only the API is a long-running service; the CLI is a one-off debug/demo tool, not something that needs its own persistent container. |
| **B — Two build targets in one multi-stage Dockerfile** | Shared builder stage, separate `api` and `simulator` final-stage targets, `docker-compose.yml` could define both as distinct services if ever needed to run simultaneously. | More "correct" separation, but there's no current requirement for the CLI to run as its own persistent container — this is complexity built for a need that doesn't exist yet. |

**Recommendation: Option A.** Add `docker-compose.yml` as an explicit deliverable of this phase, defining the API service — closing Finding A rather than leaving the documented one-click command broken.

---

### D-5 🟢 Recorded — Non-Root, Digest-Pinned Base Image

> [!NOTE]
> **Recorded Resolution: Non-Root, Digest-Pinned Base Image.**  
> Already dictated as an unequivocal requirement by the project's established Docker convention — multi-stage build with non-root user execution and SHA256 digest-pinned Python base image.

#### Originally Proposed (v0.1.0)

Already dictated as an unequivocal requirement by the project's established Docker convention — not a fresh choice, an implementation requirement to satisfy. Recorded for completeness.

---

### D-6 🟢 Approved — SQLite Persistence Across Container Restarts

> [!IMPORTANT]
> **Approved Resolution: Option A (Volume-mount `artifacts/` / SQLite path in `docker-compose.yml`).**  
> Volume-mount the SQLite database path in `docker-compose.yml` so that session-level escalation logs and audit trails survive container restarts, satisfying FR-12 (Critical) under containerized deployment.

#### Originally Proposed (v0.1.0)

**Context:** `artifacts/pulse_session.db` is written by the Phase 6 persistence layer to satisfy FR-12 (Critical). If the container's filesystem is ephemeral, every `docker compose down`/restart silently wipes the audit trail — undermining FR-12's "persisted" guarantee specifically in the containerized deployment path, even though it already works correctly for bare-metal `uv run api.main`.

| Option | Description | Trade-off |
|---|---|---|
| **A — Volume-mount `artifacts/` (or specifically the SQLite path) in `docker-compose.yml`** | The audit database survives container restarts, matching what FR-12 actually requires regardless of deployment method. | One more line in the compose file; requires deciding a host-side mount path. |
| **B — Leave it ephemeral** | Simpler compose file. | FR-12 is Critical priority and explicitly about persistence — silently not persisting across restarts in the one deployment method this phase introduces is a real, avoidable gap, not a neutral simplification. |

**Recommendation: Option A.**

---

### D-7 🟢 Approved — Model/Data Artifacts — Baked Into the Image or Mounted at Runtime

> [!IMPORTANT]
> **Approved Resolution: Option A (Bake artifacts into the image at build time).**  
> `COPY artifacts/ ...` during the Docker build so that the container image is a fully self-contained, reproducible, versioned deployable unit conforming to the project's bit-identical replay and reproducibility standards.

#### Originally Proposed (v0.1.0)

**Context:** `build_pulse_graph()` needs `stratum_table.json`, the pressure artifact, and `payoff_matrices.json` at startup; the replay simulator needs `points.parquet`. These are DVC-tracked, versioned artifacts already sitting in the repo's `artifacts/` directory.

| Option | Description | Trade-off |
|---|---|---|
| **A — Bake artifacts into the image at build time** | `COPY artifacts/ ...` during the Docker build; the image is a fully self-contained, versioned unit — one specific artifact state per image tag. | Matches this project's own reproducibility emphasis (bit-identical replay under a fixed seed) extended to the deployable unit itself: the image tag *is* a specific, traceable artifact version. Larger image, rebuild required on artifact updates — an acceptable cost at this project's current single-node, non-frequent-redeploy scale. |
| **B — Mount artifacts as a volume at runtime, kept out of the image** | Smaller, more generic image; artifacts versioned separately from the image. | The image alone isn't a reproducible, self-contained unit anymore — two things need to be versioned and kept in sync (image tag + mounted artifact state) instead of one. |

**Recommendation: Option A**, for consistency with the reproducibility principle already governing every other artifact in this project.

---

### D-8 🟢 Approved — Coverage Gate Scope, and the `llm_client.py` Gap It Would Currently Miss (Finding C)

> [!IMPORTANT]
> **Approved Resolution: Option C (Aggregate gate unchanged, plus close the specific `llm_client.py` gap now).**  
> Keep the aggregate CI coverage gate (`ci.min_coverage_pct: 70`), while specifically targeting and closing the 31% coverage gap in `src/graph/llm_client.py` with dedicated mock tests (network errors, missing API keys, fail-loud / deterministic passthrough) prior to shadow-mode acceptance sign-off.

#### Originally Proposed (v0.1.0)

**Context:** the project-wide aggregate (consistently 90–91% across every phase report reviewed) comfortably clears the 70% NFR target — while `llm_client.py` sits at 31%, per Phase 6's own literal coverage output.

| Option | Description | Trade-off |
|---|---|---|
| **A — Aggregate-only gate** | Matches the single existing `ci.min_coverage_pct: 70` value in `params.yaml` exactly; minimal CI complexity. | Structurally cannot catch a case like `llm_client.py` — a well-tested majority of the codebase will always absorb one genuinely undertested file into a passing aggregate number, indefinitely. |
| **B — Aggregate gate + a per-module floor** | Every module must individually clear some minimum, not just the total. | More rigorous, but a blunt, repo-wide policy change motivated by one specific known gap — likely more CI complexity than this specific problem warrants. |
| **C — Aggregate gate, plus close the specific known gap now** | Keep the aggregate-only gate (matches existing config, minimal change), but treat `llm_client.py`'s 31% as a named, tracked item to close with a couple of targeted tests (mocked network exception, mocked missing API key) before shadow-mode acceptance is considered complete — not a CI policy change, a specific fix. | Directly addresses the actual, evidenced problem rather than the general category; doesn't add gate complexity for every other module that doesn't have this issue. |

**Recommendation: Option C.** This file governs the fail-loud/deterministic-passthrough resilience path directly — the exact class of thing this project has been strictest about elsewhere. 31% on exactly that file, discovered rather than assumed, is worth fixing specifically rather than either ignoring it (Option A alone) or solving a broader problem than the evidence supports (Option B).

---

### D-9 🟢 Approved — Retrospective Escalation-Precision Evaluation Scaffolding

> [!IMPORTANT]
> **Approved Resolution: Scaffolding via `scripts/evaluate_escalation_precision.py` & Report.**  
> Create `scripts/evaluate_escalation_precision.py` (mirroring the established `scripts/build_payoff_matrices.py`-style offline pipeline pattern) and a corresponding `reports/docs/evaluations/escalation_precision_report.md` (matching the format every other phase's evaluation report has already used). The precision/recall computation logic is governed by `pulse_ml_canvas.md` §8 (resolved in VERIFY-1).

#### Originally Proposed (v0.1.0)

**Context:** per VERIFY item 1, `pulse_ml_canvas.md` §8's actual methodology isn't available in this conversation. This decision can only settle *where* this evaluation lives, not *how* it computes precision.

**Recommendation:** create `scripts/evaluate_escalation_precision.py` (mirroring the established `scripts/build_payoff_matrices.py`-style offline pipeline pattern) and a corresponding `reports/docs/evaluations/escalation_precision_report.md` (matching the format every other phase's evaluation report has already used). **The actual precision/recall computation logic must not be designed from this document alone** — `pulse_ml_canvas.md` §8 needs to be read first, and this decision revisited if its methodology implies a different shape than a straightforward offline script (e.g., if it requires infrastructure this document hasn't scoped, that's a reason to pause, not to improvise past the gap).

---

### D-10 🟢 Approved — OTel Span Granularity for Solver & Model Calls

> [!IMPORTANT]
> **Approved Resolution: Option A (Per-call child spans, nested under existing node spans).**  
> Each solver/model function (`compute_leverage()`, `resolve_point_win_probability()`, `compute_exploit()`, etc.) opens its own span at entry; OTel's context propagation automatically nests it under whatever node-level span is already open. Produces a full per-point call tree for precise latency profiling against the <1s budget.

#### Originally Proposed (v0.1.0)

**Context:** graph-node-level spans already exist (Phase 4). The roadmap asks for solver- and model-level spans too.

| Option | Description | Trade-off |
|---|---|---|
| **A — Per-call child spans, nested under the existing node-level span** | Each solver/model function (`compute_leverage()`, `resolve_point_win_probability()`, `compute_exploit()`, etc.) opens its own span at entry; OTel's context propagation automatically nests it under whatever node-level span is already open. | Produces a full per-point call tree (node → its solver/model sub-calls), useful for latency profiling — e.g., seeing exactly how much of `StateMonitorNode`'s <1s budget is solver time vs. stratum lookup. Matches the granularity the graph layer already uses; additive, low-risk. At this project's current scale (single-point-at-a-time or batch replay, not high-throughput production traffic) span volume isn't an operational concern — worth revisiting if that ever changes. |
| **B — Coarser: one span per node, solver/model calls uninstrumented underneath it** | No new spans below the node level. | Simpler, but leaves exactly the gap the roadmap's wording calls out — "spans across solver, models, and graph nodes" implies the first two need their own instrumentation, not just being covered indirectly by an enclosing node span. |

**Recommendation: Option A.**

---

### D-11 🟢 Approved — Structured Logging Finalization & Audit Scope

> [!IMPORTANT]
> **Approved Resolution: Audit & Verification Pass.**  
> Perform a codebase-wide audit pass confirming all logger calls route through `src/utils/logger.py`'s structured JSON output without stray `print()` statements or unformatted stdlib `logging` calls bypassing the shared logger.

#### Originally Proposed (v0.1.0)

**Context:** per VERIFY item 3, whether `src/utils/logger.py` is already `structlog`-backed with JSON output is unconfirmed.

**Recommendation:** if VERIFY confirms `structlog` JSON output already exists project-wide, "finalize" means an audit pass confirming every module's logger calls actually go through it consistently (no stray `print()` statements, no bare stdlib `logging` calls bypassing the shared logger) — a verification task, not a migration. If VERIFY finds the opposite, this becomes a real migration and needs its own, larger decision pass before Stage-level execution planning — flagged now so it isn't discovered mid-implementation.

---

### D-12 🟢 Recorded — Dockerfile `HEALTHCHECK` via the Existing `/health` Endpoint

> [!NOTE]
> **Recorded Resolution: Dockerfile `HEALTHCHECK` via `/health`.**  
> The Phase 6 `/health` endpoint already exists specifically for this purpose. A `HEALTHCHECK` instruction pointing at it is a natural, low-controversy addition, not a fresh design choice. Recorded for completeness.

#### Originally Proposed (v0.1.0)

The Phase 6 `/health` endpoint already exists specifically for this purpose. A `HEALTHCHECK` instruction pointing at it is a natural, low-controversy addition, not a fresh design choice. Recorded for completeness.

---

### D-13 🟢 Recorded — Final Evaluation Report Format

> [!NOTE]
> **Recorded Resolution: Standard Exit-Criteria Sign-off Format.**  
> Mirror the exit-criteria sign-off table format every prior phase's evaluation report has already used (`langgraph_orchestration_report.md`, `game_theory_report.md`, `streaming_api_evaluation_report.md`), checked directly against `project_charter.md` §5 Definition of Done items.

#### Originally Proposed (v0.1.0)

Recommendation: mirror the exit-criteria sign-off table format every prior phase's evaluation report has already used (`langgraph_orchestration_report.md`, `game_theory_report.md`, `streaming_api_evaluation_report.md`), checked directly against `project_charter.md` §5's Definition of Done items once VERIFY item 2 is resolved — not a new format invented for this phase. Recorded for completeness.

---

## 3. Reconciled Decision Summary

| ID | Title | Status | Approved Choice |
|---|---|:---:|---|
| **D-1** | Shadow-Mode Acceptance Definition | ✅ Approved | **Option A** — Held-out replay through real API/Docker stack (`/v1/matches/{id}/stream`) |
| **D-2** | "Held-Out" Evaluation Semantics | ✅ Approved | **Option A** — Statistical holdout for precision eval; operational check for shadow mode |
| **D-3** | CI Pipeline & Security Scan Target | ✅ Approved | **Option A** — Trivy scans final built Docker container image |
| **D-4** | Docker Build Shape & Compose | ✅ Approved | **Option A** — Single image (API CMD, CLI override) + `docker-compose.yml` service |
| **D-5** | Base Image Hardening | 🟢 Recorded | Multi-stage build, non-root user, SHA256 digest-pinned Python base |
| **D-6** | SQLite Persistence in Docker | ✅ Approved | **Option A** — Volume-mount `artifacts/` DB in `docker-compose.yml` (FR-12) |
| **D-7** | Model & Data Artifact Packaging | ✅ Approved | **Option A** — Bake artifacts into Docker image for self-contained reproducibility |
| **D-8** | Coverage Gate & Coverage Gap Fix | ✅ Approved | **Option C** — Aggregate gate unchanged; close `llm_client.py` 31% gap directly |
| **D-9** | Escalation-Precision Evaluation Scaffolding | ✅ Approved | **Recommendation** — `scripts/evaluate_escalation_precision.py` & evaluation report |
| **D-10** | OTel Span Granularity | ✅ Approved | **Option A** — Per-call child spans for solver/model calls nested under node spans |
| **D-11** | Structured Logging Finalization Scope | ✅ Approved | **Recommendation** — Codebase-wide audit pass confirming consistent JSON logging |
| **D-12** | Container Health Checking | 🟢 Recorded | `HEALTHCHECK` instruction probing `GET /health` |
| **D-13** | Final Evaluation Report Format | 🟢 Recorded | Standard exit-criteria sign-off table vs. `project_charter.md` §5 DoD |

---

All 13 decisions are fully reconciled and approved. Phase 7 is ready for VERIFY resolution and execution workflow planning.

