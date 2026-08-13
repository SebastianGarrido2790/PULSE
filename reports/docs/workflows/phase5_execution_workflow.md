# Phase 5 — Execution Workflow
**Game-Theoretic Exploit Module — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 5 of 7 | **Version:** 1.0.0 | **Date:** 2026-08-12
**Status:** 🟡 Ready to execute, pending Stage 0 — no code written yet
**Authority:** `phase5_implementation_plan_and_decisions.md` (D-1–D-11) as reconciled against `reports/specs/game_theory_spec.md`
**Scope of this document:** sequencing only, no code.

**Open item this workflow depends on:** the reconciliation document and its own chat summary disagree on D-1's actual resolution (2D matrix game vs. the originally-proposed 1D outcome-profile reframing — see the message preceding this document). Everything below assumes the reconciliation document's detailed technical analysis is correct (full 2D matrix, per the given `PayoffMatrix`/`ExploitResult` contracts). **Stage 0, step 1 confirms this before anything else proceeds.**

---

## How to Read This

12 stages (0–11), strictly ordered. Steps numbered continuously (1–48) so any step is unambiguously referenceable. Each step is tagged with the decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

---

## Stage 0 — Pre-Implementation Verification

1. **Resolve the D-1 contradiction directly** — confirm with Sebastian which of the two conflicting statements (reconciliation document's 2D-matrix finding vs. the chat summary's "Option C approved" label) is actually correct. This workflow proceeds on the 2D-matrix reading; do not proceed past this step on an assumption alone. **[D-1]**
2. Read `reports/specs/game_theory_spec.md` directly, in full — not the reconciliation's paraphrase of it. Confirm §1.1–§1.3, §2.1 (the game's formal definition) and §5.4 (empirical matrix construction / returner-strategy mapping methodology) against what's assumed below.
3. Confirm the exact field(s) in `src/schemas/point_record.py` that §5.4's returner-strategy mapping actually derives from (rally shot direction, point-winner side, or something else charted). This is the single most load-bearing VERIFY in the phase — Stage 2 cannot be written correctly without it.
4. Read §8 in full and record the actual list of golden-value/gate-verification properties (the reconciliation cites "9 properties" without enumerating them) — Stage 8's test suite is written against this list directly, not a count.
5. Confirm §6.1's stated behavior for `PayoffMatrix.surface` / `serve_number` when a matrix is built from a hierarchical fallback (D-9) rather than at the exact `(opponent, surface, serve_number)` stratum — both fields are typed as required and non-optional, so confirm what value they carry on a fallback-built artifact.
6. Confirm `src/graph/`, `src/core/game_theory.py`, and `dvc.yaml` are still in their Phase 4.1 state — no Phase 5 file exists yet.

**Gate 0:** D-1 confirmed directly, not inferred; VERIFY items 2–5 resolved against the literal spec text, not the reconciliation's summary of it.

---

## Stage 1 — Shared Contracts

7. Create the `src/core/game_theory.py` module skeleton (imports, module docstring). Per step 2's VERIFY, confirm whether `PayoffMatrix` lives in this file or a separate schemas module — default assumption, absent contrary confirmation: alongside the solver, mirroring `markov_solver.py`'s own pattern of keeping its domain model (`MatchState`) in the same file. **[D-7]**
8. Define `PayoffMatrix` (Pydantic v2) exactly per the given contract: `matrix: list[list[float]]`, `row_labels: list[str]`, `col_labels: list[str]`, `observation_counts: list[list[int]]`, `n_opp_total: int`, `server_id: str`, `returner_id: str`, `surface: Literal["HARD","CLAY","GRASS"]`, `serve_number: int`. Add a cross-field `model_validator` enforcing `len(matrix) == len(row_labels)`, every row's length `== len(col_labels)`, and `observation_counts` matching `matrix`'s shape — this is exactly the class of structural bug a missing cross-field validator caused once already in this project (Phase 3's `MatchState` hardening fix). **[D-1]**
9. Update `src/graph/state.py`'s `ExploitResult` to the given contract: `sufficient_data: bool`, `equilibrium_value: float | None` (0–1), `server_equilibrium_mix: list[float] | None`, `returner_equilibrium_mix: list[float] | None`, `observed_returner_mix: list[float] | None`, `best_response_action: str | None`, `expected_value_if_exploiting: float | None` (0–1), `delta: float | None` (≥0), `n_opp_total: int`, `payoff_matrix: PayoffMatrix`. **This replaces the Phase 4 stub's fields — `status`, `opponent_id`, `sample_size`, `is_sufficient_sample`, `recommendation` all disappear.** Grep the codebase now for every reference to those old field names so Stage 7 knows exactly what needs updating, not just the node itself. **[D-8]**
10. Add new `params.yaml` keys: the two-level sufficiency thresholds (`n_opp_total` and per-cell `observation_counts`, per D-4 — exact names/values from the spec, not invented here) and Bayesian-smoothing prior parameters for D-5's per-cell shrinkage, naming them consistently with Phase 3's `pressure_prior_alpha`/`pressure_prior_beta`/`pressure_prior_min_players_per_bucket` convention. **[D-4, D-5]**

**Gate 1:** `PayoffMatrix` and the updated `ExploitResult` each pass a standalone Pydantic validation smoke test; the grep from step 9 is a complete, recorded list.

---

## Stage 2 — Data Layer: Returner-Strategy Mapping & Matrix Construction

11. Implement the mapping from charted point data to a discrete returner-strategy label (`"Cover Wide"`, `"Cover T"`, etc.) per §5.4's confirmed rule (Stage 0, step 3). New transformation logic — belongs in `scripts/`, alongside `scripts/train_classifier.py`/`train_pressure.py`'s existing offline-fitting pattern, not inside `core/game_theory.py` itself. **[D-1]**
12. Implement the serve-direction row-label inclusion rule: include all three (Wide/Body/Tee) when each has enough charted observations for a given opponent; collapse to two otherwise. This decision lives here, in matrix construction — **not** inside the solver's dispatch logic (a refinement of the original D-2/D-2a framing, which implied the threshold lived in `core/game_theory.py`; the solver itself is dimension-agnostic, see Stage 4). **[D-2]**
13. Implement per-cell empirical win-rate computation (`π_ij`) from the mapped, labeled data.
14. Apply D-5's empirical-Bayes Beta shrinkage per cell, reusing `pressure_deviation.py`'s fitting pattern (MoM prior fit, sparse-cell fallback to a fixed weak prior).
15. Implement D-9's hierarchical fallback: attempt `(opponent, surface, serve_number)` first; fall back to an opponent-level aggregate when that stratum is too thin, resolving Stage 0 step 5's VERIFY for what the fallback artifact's `surface`/`serve_number` fields carry.
16. Write the matrix-construction function(s) with single responsibility: one function per opponent returning either a valid `PayoffMatrix` or an explicit insufficient-data marker — this return contract is what Stage 3's DVC stage and Stage 5's sufficiency gate both build on.

**Gate 2:** matrix construction produces a valid `PayoffMatrix` (passing Stage 1's validator) for at least one real, spot-checked opponent; the insufficient-data return path is exercised and confirmed distinct from a successful build.

---

## Stage 3 — DVC Pipeline Stage for Payoff-Matrix Artifacts

17. Add `scripts/build_payoff_matrices.py`, following `scripts/train_pressure.py`'s shape: reads `artifacts/validated_data/points.parquet`, runs Stage 2's construction for every opponent with enough data, writes `artifacts/models/game_theory/payoff_matrices.json` (keyed by `returner_id`, and by `(returner_id, surface, serve_number)` where the finer stratum was used). **[D-7]**
18. Add a new `dvc.yaml` stage (`build_payoff_matrices`): `deps` on the script, `src/core/game_theory.py`, `params.yaml`, `artifacts/validated_data/points.parquet`; `outs` on the artifact path.
19. Run `uv run dvc repro build_payoff_matrices`; confirm clean end-to-end execution.

**Gate 3:** `dvc.lock` updated; artifact exists on disk and round-trips through Stage 1's `PayoffMatrix` validator for a sample of entries.

---

## Stage 4 — Equilibrium Solver

20. In `core/game_theory.py`, implement the closed-form 2x2 analytical Nash solver — exact algebraic formula, no `scipy` dependency on this path. **[D-2]**
21. Implement the degenerate-game check (determinant-based, per D-6); on detection, raise `SolverException` rather than returning a degraded result. **[D-6]**
22. Implement the `scipy.optimize.linprog(method='highs')` path, dispatched purely on `PayoffMatrix.matrix`'s actual shape (`m > 2 or n > 2`) — not a sample-size comparison; that decision already happened in Stage 2. **[D-2]**
23. Implement input validation at the solver boundary (any matrix entry outside `[0, 1]` → `SolverException`), matching the Markov solver's own existing defensive-input pattern rather than relying solely on Stage 1's schema-level `Field` constraints. **[D-6]**
24. Write solver-level unit tests: 2x2 closed-form vs. a hand-computed golden value, 3x3 via `linprog` vs. a known equilibrium, the degenerate-game exception path, the invalid-probability exception path.

**Gate 4:** both dispatch paths and both exception paths pass; `linprog` calls confirmed well under the reconciliation's cited <1ms figure via a quick timing sanity check (not a formal benchmark).

---

## Stage 5 — Sufficiency Gate & `compute_exploit()` Orchestration

25. Implement the two-level sufficiency check (D-4): `n_opp_total < threshold` OR any relevant `observation_counts[i][j] < threshold` → return `ExploitResult(sufficient_data=False, ..., n_opp_total=..., payoff_matrix=...)` with every equilibrium/recommendation field left `None`. Graceful degradation (FR-6), not an exception — distinct from Stage 4's fail-loud solver-fault path.
26. Implement `compute_exploit(payoff_matrix, params) -> ExploitResult`: sufficiency check first; if sufficient, call Stage 4's solver for the equilibrium mixes and value, compute the observed returner mix from `observation_counts`, find the best-response pure strategy and its value, compute `delta` (best-response value minus equilibrium value) and `expected_value_if_exploiting`. **[D-3, D-4]**
27. Write unit tests for `compute_exploit()`: sufficient-data path (fully-populated result), insufficient-data path (gracefully degraded), and assert `delta >= 0` holds across every fixture — best response can never be worse than the equilibrium value, by definition.

**Gate 5:** both branches pass; the `delta >= 0` invariant holds on every test fixture, not asserted once and assumed.

---

## Stage 6 — Solver-Failure Exception Wiring

28. Confirm (or add) a `SolverException` subclass/reuse path in `src/utils/exceptions.py` specific enough to distinguish a game-theory fault from a Markov-solver fault in logs, while inheriting the same `BasePulseException` hierarchy — a naming decision, not a new policy (D-6 already settled fail-loud itself). **[D-6]**
29. Confirm neither Stage 4's solver functions nor Stage 5's `compute_exploit()` ever silently catch and swallow a `SolverException` anywhere.

**Gate 6:** a deliberately degenerate/malformed fixture reliably raises `SolverException` and is never accidentally caught by a bare `except Exception`.

---

## Stage 7 — `StrategyExploitNode` Integration

30. In `src/graph/strategy_exploit.py`, remove `count_opponent_observations()` entirely (retiring the Phase-4 approximation, per D-4) and its now-unused `StratumTable` import if nothing else in the file needs it. **[D-4]**
31. Update `make_strategy_exploit_node()`'s factory signature to close over the loaded payoff-matrix artifact (Stage 3's output), matching `make_pressure_diagnostic_node(pressure_artifact, params)`'s established closure pattern.
32. Update `strategy_exploit_node()`'s body: look up the current point's `PayoffMatrix` by `(returner_id, surface, serve_number)`, falling back per Stage 2's hierarchical convention; if no matrix exists for this opponent at all (never charted), return an explicit insufficient-data `ExploitResult` — still the FR-6 path, triggered one level earlier than Stage 5's not-enough-data-in-an-existing-matrix case.
33. Call `compute_exploit()` with the looked-up matrix; return its result as `exploit_result`.
34. Update `pulse_graph.py`'s `load_graph_artifacts()` to also load the payoff-matrix artifact once, alongside the existing `StratumTable`/`PressureModelArtifact` loads, and thread it into `make_strategy_exploit_node()`'s registration in `build_pulse_graph()`. **[D-7]**
35. Update `tests/unit/test_strategy_exploit.py`: replace the two Phase-4 tests (built around the retired `count_opponent_observations()`/`status` string) with tests against the new contract — sufficient-data, insufficient-data, and no-matrix-at-all.

**Gate 7:** `build_pulse_graph()` compiles cleanly with the new artifact wired in; all `test_strategy_exploit.py` tests pass; grep confirms zero remaining references to `count_opponent_observations`, `status`, `recommendation`, or `is_sufficient_sample` on `exploit_result` anywhere in `src/` or `tests/` — closing Gate 1's grep list.

---

## Stage 8 — `tests/unit/test_game_theory.py`

36. Consolidate the full set of golden-value/gate-verification properties from spec §8 (confirmed in Stage 0, step 4) into `tests/unit/test_game_theory.py`, the filename the roadmap and hand-off summary both already commit to.
37. Confirm each property has its own explicitly-named test function — not folded into one parametrized test that could hide which specific property failed.

**Gate 8:** every property from §8 has a corresponding, individually-named, passing test.

---

## Stage 9 — Integration Tests Through `PulseGraphState`

38. Update `tests/integration/test_conditional_graph.py`'s existing "high-leverage, high-data" fixture (built in Phase 4) to assert against the new `ExploitResult` contract instead of the retired `status: "module_not_yet_implemented"` value — this fixture already reaches `StrategyExploitNode`; its assertions need updating, not a rebuild.
39. Add one new fixture for the no-payoff-matrix-exists case (an opponent never charted) — Phase 4's original three fixtures never had reason to cover this branch.
40. Confirm `TacticalOutputNode`'s existing LLM-call guard still fires correctly on the new `ExploitResult` shape (no code change expected, per D-11) — but its assembled payload's JSON shape has changed, so rebuild at least one `tests/evals/test_tactical_output_groundedness.py` fixture against the new field names. **[D-11]**

**Gate 9:** all integration fixtures pass; the groundedness eval's fixtures reflect the new `ExploitResult` fields, not the retired ones.

---

## Stage 10 — Full Phase 5 Verification

41. `uv run ruff check .` and `uv run ruff format --check .` — 0 errors.
42. `uv run pyright` — 0 errors.
43. `python scripts/check_file_size.py` — confirm `core/game_theory.py` and the new script stay under the 1,000-line ceiling; if the solver, sufficiency gate, and matrix-construction logic risk crowding one file, split now rather than after the ceiling is hit.
44. `uv run pytest --cov=src --cov-report=term-missing` — full suite green, coverage ≥70%, with `core/game_theory.py` and the updated `strategy_exploit.py` checked specifically given they're this phase's highest-novelty, highest-risk code.
45. `uv run dvc repro` — confirm the full pipeline, including the new `build_payoff_matrices` stage, reproduces cleanly end to end.

**Gate 10:** all green. Phase 5 is functionally complete.

---

## Stage 11 — Documentation Closeout

46. Write a Phase 5 evaluation report mirroring `walkthrough.md`/`langgraph_orchestration_report.md`'s structure — exit-criteria table, example `ExploitResult` payloads (sufficient and insufficient-data cases), golden-value results.
47. Log the new `SolverException` reuse and the hierarchical matrix-fallback pattern into `system_design.md` as a new dated ADR entry, not a silent edit; mark `technical_roadmap.md`'s Phase 5 entry ✅ Complete.
48. **Formally resolve and record the D-1 discrepancy** — write down, in one place, which of the two conflicting statements (reconciliation document vs. its own chat summary) was actually correct, so this doesn't become an unresolved ambiguity for whoever reads this project's history later. This is the one item in the whole workflow that traces back to a contradiction rather than a forward task, and it deserves an explicit closure note rather than an assumption baked silently into the code.

**Gate 11 (final):** documentation closeout complete; D-1's resolution is unambiguously recorded in exactly one place.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify + resolve D-1) → Stage 1 (contracts) → Stage 2 (matrix construction)
   → Stage 3 (DVC artifact stage) → Stage 4 (solver) → Stage 5 (sufficiency gate + orchestration)
   → Stage 6 (exception wiring) → Stage 7 (node integration) → Stage 8 (solver test suite)
   → Stage 9 (integration suite) → Stage 10 (CI gate) → Stage 11 (docs + D-1 closure)
```

48 steps, 12 gates. No implementation starts until Stage 0's Gate passes — and Stage 0's first item is resolving which document was actually correct about D-1.
