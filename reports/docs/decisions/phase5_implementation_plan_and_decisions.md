# Phase 5 — Implementation Plan & Decisions

**Game-Theoretic Exploit Module — Reconciled Against `game_theory_spec.md`**

**Product:** PULSE | **Phase:** 5 of 7 | **Version:** 2.1.0 (Reconciled — original proposals preserved for the record) | **Date:** 2026-08-12
**Status:** ✅ Decisions resolved — ready for an execution workflow
**Authority:** `reports/specs/game_theory_spec.md` (§1.1–§1.3, §2.1, §3.2–§3.3, §4.1–§4.2, §5.1, §5.3–§5.4, §6.1–§6.2, §7, §9), `technical_roadmap.md` Phase 5, `system_design.md` (ADR-002, ADR-003, ADR-005, ADR-010)

**Standing caveat:** the full text of `game_theory_spec.md` has not been directly reviewed in this conversation — this document is built from a detailed reconciliation summary plus one directly-confirmed line ("explicitly mandates a 2D simultaneous-move zero-sum matrix game"). The two concrete Pydantic contracts in D-8 are trusted as close to verbatim, since they're specific enough that paraphrase error is unlikely. Stage 0 of the execution workflow still opens with reading the literal file.

---

## 0. Revision Note

v2.1.0 restores every option/trade-off table from the original v0.1.0 draft, at request — nothing proposed during the initial planning pass is removed from the record, even where the spec settled the question differently. Each decision below now carries two parts:

- **Originally Proposed (v0.1.0)** — the options considered, their trade-offs, and what was recommended before `game_theory_spec.md` was available.
- **Resolution (reconciled)** — what the spec actually settles, and how it compares to the original proposal.

v2.0.0 reconciles the initial planning proposals against `reports/specs/game_theory_spec.md`. The initial three-option tables for D-1 and D-2 have been compressed into single-line summary notes under each decision — since the governing specification settles those structural questions outright rather than leaving them as design forks. All historical context and rationale are preserved in compressed form.

Where the resolution matches the original proposal, that's stated plainly. Where it doesn't (D-1, and D-2's mechanism), the divergence is called out explicitly rather than smoothed over.

---

## 1. Current State Audit

Unchanged in substance from the original audit — nothing in the codebase has moved since it was taken.

| File                                   | Status                                       | Notes                                                                                                                                                                                                                                                   |
| -------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/core/game_theory.py`              | Does not exist. Phase 5 scope.               | Now: pure `PayoffMatrix` consumer — 2x2 closed-form + `linprog` dispatch, sufficiency gate, best-response/EV computation.                                                                                                                               |
| `tests/unit/test_game_theory.py`       | Does not exist.                              | Golden-value + gate-verification suite, per spec §8 (exact list still to be read directly — Stage 0 of the execution workflow).                                                                                                                         |
| `src/graph/strategy_exploit.py`        | Exists — Phase 4 stub, verified through 4.1. | `count_opponent_observations()` is retired by the D-4 resolution — superseded by `PayoffMatrix.n_opp_total`/`observation_counts`, which carry real return-relevant data instead of a serve-count proxy.                                                 |
| `src/graph/state.py` — `ExploitResult` | Exists — Phase 4 schema.                     | **Replaced, not extended** — see D-8. Old fields (`status`, `opponent_id`, `sample_size`, `is_sufficient_sample`, `recommendation`) are gone.                                                                                                           |
| `src/schemas/point_record.py`          | Exists — Phase 2, stable.                    | The original audit's central concern (no literal return-position field) is addressed by D-1's resolution: the returner axis is _constructed_ from charted return-coverage/outcome data during matrix building, not read off a field that doesn't exist. |
| `params.yaml`                          | No game-theory keys yet.                     | New keys needed per D-2 (dimension-inclusion threshold), D-4 (two-level sufficiency), D-5 (smoothing priors).                                                                                                                                           |
| `dvc.yaml`                             | No game-theory stage yet.                    | New `build_payoff_matrices` stage needed — D-7.                                                                                                                                                                                                         |

### 1.1 The Central Feasibility Question That Originally Drove D-1

_(Preserved verbatim from v0.1.0, since it's the reasoning the original three options were built to answer.)_

The roadmap and hand-off summary both described this phase's data work as "opponent **return-positioning** bias estimation from historical charted data" and a payoff matrix over serve direction (Wide/Tee, or Wide/Body/Tee) **vs.** return positioning (Deuce-guard/Ad-guard). Two pieces of evidence cast real doubt on whether literal return-position data exists to build that second axis from: (1) serve direction is confirmed present in the ingested data since Phase 2; (2) nothing reviewed showed a comparable field for the returner's court position, and `prd.md` §3 explicitly places video/vision-based state extraction out of scope, for exactly the reasons that would make it costly to add now. This gap — real, not resolved by the spec's existence alone — is what D-1 was written to address.

### 1.2 Feasibility Context (Why Option C Was Initially Considered for D-1)

_Historical note:_ The initial draft considered redefining the game into a 1D outcome profile (Option C) because `point_record.py` lacks a literal returner court-position field. `game_theory_spec.md` settles this by resolving the gap at the data layer (constructing discrete returner coverage categories during matrix building), while preserving the 2D matrix game structure.

---

## 2. Decisions

### D-1 🟢 Approved (2D Matrix Game) — Return-Positioning Data Availability & What the "Opponent's Strategy" Represents

> [!IMPORTANT]
> **Approved Resolution:** Mandated 2D Zero-Sum Matrix Game $\Pi \in \mathbb{R}^{m \times n}$. Returner strategy axis is constructed at the data layer during matrix building (§5.4) by mapping charted return coverage/outcomes to discrete categories (e.g., `{"Cover Wide", "Cover T"}`). Option C (1D outcome vector) is rejected by spec.

#### Originally Proposed (v0.1.0)

| Option                                                                                  | Description                                                                                                                                                                                                                                                                                                 | Trade-off                                                                                                                                                                                          |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Confirm return-position data exists, build as literally scoped**                  | If `point_record.py` (or a companion charting field) does expose returner positioning, build the 2x2/3x3 game exactly as described: serve direction vs. literal return positioning.                                                                                                                         | Best case, and the cleanest to explain to a coach ("stand wider against this server"). Contingent entirely on a VERIFY that, on current evidence, was unlikely to succeed.                         |
| **B — Proxy from return-shot direction, if charted**                                    | If the dataset separately charts the _direction of the return shot itself_ (not the returner's pre-serve position), use that as an indirect signal of returner tendency/coverage.                                                                                                                           | Plausible middle ground if that finer-grained shot data exists, but introduces its own new VERIFY, and conflates "where the ball went" with "where the player was standing" — a real semantic gap. |
| **C — Redefine the opponent's "strategy" as an empirically observable outcome profile** | Model the game as server's serve-direction mix vs. the _returner's point-win rate conditioned on each serve direction_ — an empirical effectiveness profile, not a positioning choice. The Nash equilibrium becomes "the serve-direction mix that's hardest for this specific returner to convert against." | Fully supported by data already confirmed to exist. Requires reframing "return positioning" language downstream — a real, visible change from how the roadmap phrases it.                          |

**Original proposal: Option C**, unless a VERIFY against `point_record.py` and `game_theory_spec.md` turned up positioning data that made Option A viable — flagged explicitly as the decision everything else in the document was downstream of.

#### Resolution (reconciled against `game_theory_spec.md`)

`game_theory_spec.md` §1.1, §2.1, §3.2, §3.3, and §6.1 mandate a genuine 2D matrix game Π ∈ ℝ^(m×n) between the server's serve-direction strategies and the returner's positioning/coverage strategies — explicitly, not as a compromise reading. **Option C is rejected.**

The data-availability gap Option C was built to solve is real and doesn't disappear — but the spec resolves it at the **data layer**, not by changing the game's structure: the returner-strategy axis is _constructed_ by mapping charted return-coverage/outcome data to discrete categories (e.g., `{"Cover Wide", "Cover T"}`) during matrix building (§5.4). `core/game_theory.py` itself never touches this mapping — it consumes a fully-built `PayoffMatrix` and is agnostic to how the returner axis was derived. This is closer to Option B's instinct (derive the axis from what's actually charted) than Option C's (redefine the game to avoid needing the axis at all) — but the spec settles on a genuine categorical mapping (B-adjacent), not a proxy outcome vector (C), and not a confirmation that literal position data exists (A).

**Downstream impact:** D-2 through D-9 below are written against this resolution.

---

### D-2 / D-2a 🟢 Approved (Option B / Data-Layer Escalation) — Matrix Dimensionality

> [!IMPORTANT]
> **Approved Resolution:** Default to closed-form 2×2 Nash solver; escalate to 3×3 LP solver when sample size supports three serve directions. Inclusion threshold lives in `params.yaml` and is checked during matrix construction. `core/game_theory.py` solver dispatches purely on matrix shape.

#### Originally Proposed (v0.1.0)

| Option                                                                | Mechanism                                                                                                                                                                                          | Trade-off                                                                                                                                                                                    |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — 3x3 by default, collapse to 2x2 only on failure**               | Always attempt the full 3-category matrix; fall back to 2x2 (merging Body into whichever neighbor it's statistically closer to) only if the LP is degenerate or a category is too sparse.          | Uses the richer data by default, but makes the exact, always-well-behaved 2x2 solver the exception rather than the rule — inverts the roadmap's own framing of which one is "primary."       |
| **B — 2x2 by default, escalate to 3x3 above a sample-size threshold** | Default to the closed-form 2x2 form; use 3x3 only once a specific opponent has enough charted points to support three independently-estimated columns reliably, per a new `params.yaml` threshold. | Mirrors the same escalation-only-with-sufficient-data philosophy already governing every other gate in this system. Matrix dimensionality becomes just another sufficiency-gated escalation. |
| **C — Fixed, non-adaptive 3x3 always**                                | Simplest code, no runtime branching.                                                                                                                                                               | Discards the exact-analytical path entirely, always depends on `linprog` convergence, and loses the "primary/fallback" structure the roadmap explicitly asks for.                            |

**Original proposal: Option B**, with a **D-2a** sub-decision: the threshold lives as a new `params.yaml` key, read by `core/game_theory.py` at fit time.

#### Resolution (reconciled — mechanism corrected)

The _choice_ — default to 2x2, escalate to 3x3 only with enough data — is confirmed; Option B's instinct was right. What's corrected is **where the decision lives**: it does **not** happen inside `core/game_theory.py` as a threshold check, as the original D-2a proposal assumed. It happens in the matrix-construction step (the data layer): include all three serve directions as rows when each has enough charted observations; collapse to two otherwise. `core/game_theory.py`'s solver purely dispatches on the actual shape of the `PayoffMatrix` it receives — exact closed-form for a literal 2x2, `scipy.optimize.linprog(method='highs')` for any `m > 2 or n > 2`. The solver itself is dimension-agnostic; it never evaluates a sample-size threshold.

**D-2a (revised):** the inclusion threshold is a `params.yaml` key read by the _matrix-construction_ step, not by `core/game_theory.py` — a location correction from the original write-up.

---

### D-3 🟢 Approved — Best-Response Deviation & EV-Shift Computation

> [!IMPORTANT]
> **Approved Resolution:** Single core function in `core/game_theory.py` evaluating empirical returner mix $\hat{y}$, pure best-response $x_{\text{BR}} = \arg\max_{x} x^T \Pi \hat{y}$, and EV gain $\delta = (x_{\text{BR}}^T \Pi \hat{y}) - V \ge 0$.

#### Originally Proposed (v0.1.0)

🟢 No real fork — the roadmap already fixed this output shape explicitly ("best-response deviation computation & expected value shift ΔEV"). Proposed: one function in `core/game_theory.py`, e.g. `compute_best_response(payoff_matrix, equilibrium_mix) -> (best_pure_strategy, ev_gain)`.

#### Resolution (confirmed, formula made explicit)

`compute_exploit()` evaluates the observed returner mix ŷ, finds the best pure-strategy response x_BR = argmax_x xᵀΠŷ, and computes δ = (x_BRᵀΠŷ) − V, where V is the equilibrium value. Matches the original proposal's shape; the spec (§4.1–§4.2) makes the exact formula explicit where the original draft only described the output.

---

### D-4 🟢 Approved (Option A) — Sufficiency-Gate Ownership

> [!IMPORTANT]
> **Approved Resolution (Option A):** `compute_exploit()` in `core/game_theory.py` owns the two-level sufficiency check (aggregate $N_{\text{opp}} < N_{\text{min}}$ OR cell count $< N_{\text{min}}$). `strategy_exploit.py` retires Phase 4 serve-count approximation.

#### Originally Proposed (v0.1.0)

**Context:** `strategy_exploit.py`'s `count_opponent_observations()` was explicitly built and documented as a temporary Phase-4 stand-in, using the Tier-1 stratum table's _serve_ observation counts as a rough proxy for opponent data volume — not a return-specific count.

| Option                                                                                           | Description                                                                                                                                                                                                                                                    | Trade-off                                                                                                                                          |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — `core/game_theory.py` owns sufficiency, `strategy_exploit.py` just reads it**              | The payoff-matrix fit returns a result object carrying its own `sample_size` and `is_sufficient: bool`, mirroring `PressureModelArtifact`'s `is_prior_estimated` pattern from Phase 3. `strategy_exploit.py` retires `count_opponent_observations()` entirely. | The sufficiency criterion is intrinsically about the data backing the payoff matrix — that's `core/game_theory.py`'s domain, not the graph node's. |
| **B — Keep the count in `strategy_exploit.py`, treat `core/game_theory.py` as pure computation** | Node keeps gating; `game_theory.py` assumes sufficiency was already checked.                                                                                                                                                                                   | Leaves the Phase-4 approximation's flawed proxy as the system of record for a decision it was never designed to make well.                         |

**Original proposal: Option A.**

#### Resolution (confirmed, extended)

`compute_exploit()` checks **both** `n_opp_total < N_min` (aggregate) **and** any `observation_counts[i][j] < N_min` (per-cell) before attempting a solve. Either condition failing returns `ExploitResult(sufficient_data=False, ...)` with every equilibrium/recommendation field left `None` — graceful degradation, not an exception (FR-6). Confirms Option A's ownership call exactly; the per-cell half of the check is new detail the original draft didn't specify at that granularity.

---

### D-5 🟢 Approved (Option A) — Payoff-Matrix Smoothing Method

> [!IMPORTANT]
> **Approved Resolution (Option A):** Matrix cell win probabilities $\pi_{ij}$ are smoothed via Empirical-Bayes Beta shrinkage per cell during matrix construction, reusing Phase 3 Method-of-Moments pattern.

#### Originally Proposed (v0.1.0)

**Context:** the roadmap specifies "empirical payoff matrix construction with Bayesian smoothing" without naming a method.

| Option                                                          | Description                                                                                                                                                                                              | Trade-off                                                                                                                                                      |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Empirical-Bayes Beta shrinkage per matrix cell**          | Reuse the exact pattern already built and validated in `pressure_deviation.py`: each cell's win-rate is shrunk toward a population/marginal baseline, strength set by that cell's own observation count. | Directly reuses tested, already-approved machinery and statistical philosophy.                                                                                 |
| **B — Uniform Laplace / add-k smoothing**                       | Simple additive smoothing constant.                                                                                                                                                                      | Easier, but inconsistent with this project's convention of fitting priors from data rather than picking arbitrary constants.                                   |
| **C — Joint Dirichlet-multinomial model over the whole matrix** | More statistically complete treatment of the joint distribution.                                                                                                                                         | Real added complexity and scope for a phase that's already data-constrained; the roadmap's wording reads as per-cell shrinkage, not a joint categorical model. |

**Original proposal: Option A.**

#### Resolution (confirmed)

Matrix cell entries π_ij are empirical win probabilities smoothed via Bayesian shrinkage before being written into the `PayoffMatrix`, per §5.4. No change from Option A — reuse `pressure_deviation.py`'s Method-of-Moments prior-fitting pattern per cell, exactly as originally recommended.

---

### D-6 🟢 Approved — Solver-Failure Handling

> [!IMPORTANT]
> **Approved Resolution:** Fail loud via `SolverException` on degenerate 2×2 games ($D=0$), invalid matrix values ($<0$ or $>1$), or LP solver failures.

#### Originally Proposed (v0.1.0)

🟢 No real fork. An LP that fails to converge is a different failure mode than "not enough data" — the sample-size gate already handles the latter gracefully by design (FR-6). This project's established exception policy is explicit that computational faults must fail loud. Proposed: reuse (or lightly subclass) the existing solver-failure exception already defined for the Markov solver's own mathematical/domain-state errors.

#### Resolution (confirmed)

Degenerate 2x2 games (zero-determinant condition), invalid probability inputs (outside `[0, 1]`), and LP-solver failures all explicitly raise `SolverException`. No change from the original proposal.

---

### D-7 🟢 Approved (Option A) — Where the Payoff Matrix Is Fit and Stored

> [!IMPORTANT]
> **Approved Resolution (Option A):** Offline-fit DVC-tracked artifact (`artifacts/models/game_theory/payoff_matrices.json`) + live in-process equilibrium solve ($<1\text{ms}$).

#### Originally Proposed (v0.1.0)

**Context:** this phase has two distinct computational steps: fitting the empirical payoff matrix (a data-estimation step), and solving the Nash equilibrium given that matrix (an exact optimization step). The project's own file layout already separates these categories elsewhere — `game_theory.py` lives under the deterministic core, not under the MLflow-tracked models directory.

| Option                                                            | Description                                                                                                                                                                                                                                | Trade-off                                                                                                                                                                                                                                                              |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Offline-fit, DVC-tracked artifact + live in-process solve** | A new pipeline step produces a payoff-matrix artifact (per-opponent, smoothed) and tracks it via DVC, mirroring `stratum_table.json`. `core/game_theory.py` exposes a loader plus a solver operating on the loaded matrix at request time. | Matches the "load once at graph-construction time" latency pattern this project has used since Phase 3/4. Not MLflow-tracked — no calibration curve or train/test split concept here, matching Phase 2's ingestion pattern more than Phase 3's model-training pattern. |
| **B — Fully live computation, no offline artifact**               | Build the payoff matrix from raw historical data on every request.                                                                                                                                                                         | Breaks the artifact-loading latency discipline this project has held to since Phase 4's own D-9.                                                                                                                                                                       |

**Original proposal: Option A** — described as "a strong recommendation, not a close call," grounded in the file-structure evidence (`game_theory.py` under `core/`, not `models/`).

#### Resolution (confirmed)

Ingestion/DVC builds the `PayoffMatrix` payload as a versioned artifact; `core/game_theory.py` performs the equilibrium solve live, in-process, in well under 1ms. No change from Option A — the file-structure evidence that motivated the original recommendation turns out to match the spec's own framing exactly.

---

### D-8 🟢 Approved (Option A) — `ExploitResult` Schema Extension

> [!IMPORTANT]
> **Approved Resolution (Option A):** `ExploitResult` carries structured numeric/categorical fields only (`sufficient_data`, `equilibrium_value`, `server_equilibrium_mix`, `returner_equilibrium_mix`, `observed_returner_mix`, `best_response_action`, `expected_value_if_exploiting`, `delta`, `n_opp_total`, `payoff_matrix`). Zero narrative prose in core; phrasing stays 100% downstream in `TacticalOutputNode`.

#### Originally Proposed (v0.1.0)

**Context:** the hand-off summary described this phase as making `ExploitResult` "return actionable tactical exploit recommendations." `ExploitResult.recommendation` was already typed `str | None`. `TacticalOutputNode` already exists specifically to turn structured signals into coach-readable prose — no upstream node writes narrative text today.

| Option                                                                                          | Description                                                                                                                                                     | Trade-off                                                                                                                                                                          |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Extend with structured numeric fields; leave narrative phrasing to `TacticalOutputNode`** | Add fields like `recommended_direction`, `expected_value_gain`, `equilibrium_mix`; drop or repurpose `recommendation` as structured data rather than free text. | Consistent with every other upstream node's contract; keeps the DeepEval groundedness check's job exactly as scoped today.                                                         |
| **B — Populate `recommendation` with actual prose now**                                         | Write the tactical sentence directly inside `strategy_exploit_node()`, matching the hand-off summary's literal phrasing.                                        | Duplicates `TacticalOutputNode`'s role, risks the LLM re-narrating an already-narrated string, gives the groundedness eval a second kind of narrative text it wasn't designed for. |

**Original proposal: Option A** — flagged explicitly as "a genuine, visible deviation from how the hand-off summary phrased the deliverable," not a silent reinterpretation.

#### Resolution (confirmed, 100%)

The spec is explicit (§1.2, §6.2) that `core/game_theory.py` is **not an LLM and not a recommendation engine** — it returns a structured payload; narrative phrasing stays exclusively downstream in `TacticalOutputNode`. Option A's pushback against the hand-off summary's phrasing is fully validated, not just accepted as a reasonable alternative.

**`PayoffMatrix` (input contract):**

```
matrix: list[list[float]]              # m x n empirical win probabilities, π_ij
row_labels: list[str]                  # e.g. ["Wide", "Body", "T"]
col_labels: list[str]                  # e.g. ["Cover Wide", "Cover T"]
observation_counts: list[list[int]]    # m x n cell observation counts
n_opp_total: int                       # total observations for opponent in this stratum
server_id: str
returner_id: str
surface: Literal["HARD", "CLAY", "GRASS"]
serve_number: int
```

**`ExploitResult` (output contract — replaces the Phase 4 stub's fields entirely):**

```
sufficient_data: bool
equilibrium_value: float | None        # [0, 1]
server_equilibrium_mix: list[float] | None
returner_equilibrium_mix: list[float] | None
observed_returner_mix: list[float] | None
best_response_action: str | None
expected_value_if_exploiting: float | None   # [0, 1]
delta: float | None                    # >= 0
n_opp_total: int
payoff_matrix: PayoffMatrix
```

---

### D-9 🟢 Approved (Option B) — Opponent-Matrix Granularity

> [!IMPORTANT]
> **Approved Resolution (Option B):** Matrix builder attempts finest `(opponent, surface, serve_number)` stratum first and falls back to opponent-level aggregate when sparse. (Fallback metadata handling verified in Stage 0).

#### Originally Proposed (v0.1.0)

**Context:** should the payoff matrix be fit per `(opponent, surface)`, or per opponent only?

| Option                                                                                           | Description                                                                                                                                | Trade-off                                                                                                         |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **A — Per `(opponent, surface)`**                                                                | Matches the classifier's finest stratum granularity.                                                                                       | Multiplies an already-thin signal by a surface dimension, on data likely sparse even before splitting by surface. |
| **B — Opponent-level only, with hierarchical fallback if it proves too thin even at that level** | Mirrors the classifier's own Tier 0→1→2→3 fallback philosophy, starting from a coarser base level given this signal is inherently sparser. | Reuses an already-validated pattern rather than inventing a new one.                                              |

**Original proposal: Option B.**

#### Resolution (confirmed — one detail still pending)

`PayoffMatrix` always carries `server_id`, `returner_id`, `surface`, `serve_number` metadata; the matrix builder attempts the finest `(opponent, surface, serve_number)` stratum first and falls back to an opponent-level aggregate when that stratum is too sparse, per §5.4/§6.1. Confirms Option B's approach exactly.

**One implementation detail carried forward, not a design fork:** since `surface` and `serve_number` are non-optional fields, what value they hold on a fallback-built (aggregated) artifact still needs confirming against the literal spec text — flagged for Stage 0 of the execution workflow.

---

### D-10 🟢 Approved — External Dependencies

> [!IMPORTANT]
> **Approved Resolution:** Reuses existing `scipy` baseline (`scipy.optimize.linprog(method='highs')`) with no new dependencies.

#### Originally Proposed (v0.1.0)

🟢 `scipy` has been present since Phase 1's baseline `pyproject.toml`. `scipy.optimize.linprog` requires no new dependency, no version bump, no environment change. Recorded for completeness.

#### Resolution

Confirmed, unchanged.

---

### D-11 🟢 Approved — `TacticalOutputNode`'s LLM-Call Guard

> [!IMPORTANT]
> **Approved Resolution:** LLM invocation guard logic remains `pressure_result is not None or exploit_result is not None`.

#### Originally Proposed (v0.1.0)

🟢 The guard that decides whether to invoke the LLM already fires on `pressure_result is not None or exploit_result is not None` — Phase 5 changes _what_ `exploit_result` contains once `StrategyExploitNode` fires, not _whether_ or _when_ it fires. No change needed to `tactical_output.py`. Recorded for completeness.

#### Resolution

Confirmed, unchanged. The guard condition itself doesn't change — but the payload it assembles now has an entirely different `exploit_result` shape (per D-8), which affects the integration and groundedness-eval fixtures, not the guard logic itself.

---

## 3. Decision Summary

| ID         | Status      | Approved Resolution                                                                              |
| ---------- | ----------- | ------------------------------------------------------------------------------------------------ |
| D-1        | 🟢 Approved | 2D Matrix Game $\Pi \in \mathbb{R}^{m \times n}$; returner axis constructed at data layer (§5.4) |
| D-2 / D-2a | 🟢 Approved | Option B (2×2 default, escalate to 3×3); threshold read at matrix-construction step              |
| D-3        | 🟢 Approved | Single best-response function in core ($x_{\text{BR}}, \delta \ge 0$)                            |
| D-4        | 🟢 Approved | Option A (Two-level sufficiency check owned by `core/game_theory.py`)                            |
| D-5        | 🟢 Approved | Option A (Empirical-Bayes Beta shrinkage per cell)                                               |
| D-6        | 🟢 Approved | Fail-loud solver exceptions (`SolverException`)                                                  |
| D-7        | 🟢 Approved | Option A (Offline DVC artifact + live in-process equilibrium solve)                              |
| D-8        | 🟢 Approved | Option A (Structured Pydantic contract; zero narrative prose in core)                            |
| D-9        | 🟢 Approved | Option B (Opponent-level granularity with hierarchical fallback)                                 |
| D-10       | 🟢 Approved | No new external dependencies (`scipy` baseline reused)                                           |
| D-11       | 🟢 Approved | `TacticalOutputNode` LLM-call guard unchanged                                                    |

**Status:** All 11 decisions are finalized, approved by Sebastian, and highlighted. Ready for execution workflow.
