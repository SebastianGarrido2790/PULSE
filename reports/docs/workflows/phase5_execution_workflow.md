# Phase 5 — Execution Workflow

**Game-Theoretic Exploit Module — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 5 of 7 | **Version:** 2.0.0 (rebuilt against reconciled decisions v2.0.0) | **Date:** 2026-08-12
**Status:** 🟢 Stage 0 complete — 5 steps verified
**Authority:** `phase5_implementation_plan_and_decisions.md` v2.0.0 (D-1–D-11, all resolved)
**Scope of this document:** sequencing only, no code.

---

## How to Read This

12 stages (0–11), strictly ordered. Steps numbered continuously (1–47) so any step is unambiguously referenceable. Each step is tagged with the decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

---

## Stage 0 — Pre-Implementation Verification ✅

D-1 is resolved, not open — this stage is about confirming exact details the reconciliation summarized but didn't quote verbatim, not about re-litigating the game's structure.

1. Read `reports/specs/game_theory_spec.md` directly, in full. Confirm §5.4's exact returner-strategy mapping rule (which charted field(s) in `src/schemas/point_record.py` it maps _from_) — this is the single most load-bearing item in the whole phase, since Stage 2 can't be written without it. **[D-1]**
2. Read §8 in full and record the literal list of golden-value/gate-verification properties — Stage 8's test suite is written against this list directly, not a count of them.
3. Confirm §6.1's stated value for `PayoffMatrix.surface`/`serve_number` on a fallback-built (opponent-level aggregate) artifact, given both fields are non-optional. **[D-9]**
4. Confirm the exact `params.yaml` key names and threshold values the spec expects for: the serve-direction inclusion rule (D-2a), the two-level sufficiency gate (D-4), and the Bayesian-smoothing priors (D-5) — don't invent names not already implied by the spec's own terminology.
5. Confirm `src/graph/`, `src/core/game_theory.py`, and `dvc.yaml` are still in their Phase 4.1 state — no Phase 5 file exists yet.

**Gate 0:** items 1–4 resolved against the literal spec text; no outstanding VERIFY items carried into Stage 1.

---

## Stage 1 — Shared Contracts ✅

6. Create the `src/core/game_theory.py` module skeleton (imports, module docstring). Confirm from Stage 0 whether `PayoffMatrix` belongs in this file or a separate schemas module — default assumption absent contrary confirmation: alongside the solver, mirroring `markov_solver.py`'s own pattern of keeping its domain model (`MatchState`) in the same file. **[D-7]**
7. Define `PayoffMatrix` (Pydantic v2) exactly per D-8's contract: `matrix`, `row_labels`, `col_labels`, `observation_counts`, `n_opp_total`, `server_id`, `returner_id`, `surface: Literal["HARD","CLAY","GRASS"]`, `serve_number: int`. Add a cross-field `model_validator` enforcing `len(matrix) == len(row_labels)`, every row's length `== len(col_labels)`, and `observation_counts` matching `matrix`'s shape — the same class of structural bug a missing cross-field validator caused once already in this project (Phase 3's `MatchState` hardening fix). **[D-1, D-8]**
8. Update `src/graph/state.py`'s `ExploitResult` to D-8's contract in full: `sufficient_data`, `equilibrium_value`, `server_equilibrium_mix`, `returner_equilibrium_mix`, `observed_returner_mix`, `best_response_action`, `expected_value_if_exploiting`, `delta`, `n_opp_total`, `payoff_matrix`. **This is a full replacement, not an extension** — `status`, `opponent_id`, `sample_size`, `is_sufficient_sample`, `recommendation` are all gone. Grep the codebase now for every reference to those old field names so Stage 7 knows the complete list of what needs updating. **[D-8]**
9. Add the new `params.yaml` keys confirmed in Stage 0 step 4: the serve-direction inclusion threshold (D-2a), the two-level sufficiency thresholds (D-4), and the smoothing priors (D-5) — naming consistently with Phase 3's `pressure_prior_alpha`/`pressure_prior_beta`/`pressure_prior_min_players_per_bucket` convention.

**Gate 1:** `PayoffMatrix` and the new `ExploitResult` each pass a standalone Pydantic validation smoke test; the grep from step 8 is a complete, recorded list.

---

## Stage 2 — Data Layer: Returner-Strategy Mapping & Matrix Construction

10. Implement the mapping from charted point data to a discrete returner-strategy label (e.g. `"Cover Wide"`, `"Cover T"`) per Stage 0 step 1's confirmed rule. New transformation logic — belongs in `scripts/`, alongside `scripts/train_classifier.py`/`train_pressure.py`'s existing offline-fitting pattern, not inside `core/game_theory.py` itself. **[D-1]**
11. Implement the serve-direction row-label inclusion rule (D-2a): include all three (Wide/Body/Tee) when each has enough charted observations for a given opponent; collapse to two otherwise. This lives here, in matrix construction — **not** inside the solver (see Stage 4). **[D-2]**
12. Implement per-cell empirical win-rate computation (π_ij) from the mapped, labeled data.
13. Apply D-5's empirical-Bayes Beta shrinkage per cell, reusing `pressure_deviation.py`'s fitting pattern (MoM prior fit, sparse-cell fallback to a fixed weak prior).
14. Implement D-9's hierarchical fallback: attempt `(opponent, surface, serve_number)` first; fall back to an opponent-level aggregate when that stratum is too thin, using Stage 0 step 3's confirmed convention for what the fallback artifact's `surface`/`serve_number` fields carry.
15. Write the matrix-construction function(s) with single responsibility: one function per opponent returning either a valid `PayoffMatrix` or an explicit insufficient-data marker — this return contract is what Stage 3's DVC stage and Stage 5's sufficiency gate both build on.

**Gate 2:** matrix construction produces a valid `PayoffMatrix` (passing Stage 1's validator) for at least one real, spot-checked opponent; the insufficient-data return path is exercised and confirmed distinct from a successful build.

---

## Stage 3 — DVC Pipeline Stage for Payoff-Matrix Artifacts

16. Add `scripts/build_payoff_matrices.py`, following `scripts/train_pressure.py`'s shape: reads `artifacts/validated_data/points.parquet`, runs Stage 2's construction for every opponent with enough data, writes `artifacts/models/game_theory/payoff_matrices.json` (keyed by `returner_id`, and by `(returner_id, surface, serve_number)` where the finer stratum was used). **[D-7]**
17. Add a new `dvc.yaml` stage (`build_payoff_matrices`): `deps` on the script, `src/core/game_theory.py`, `params.yaml`, `artifacts/validated_data/points.parquet`; `outs` on the artifact path.
18. Run `uv run dvc repro build_payoff_matrices`; confirm clean end-to-end execution.

**Gate 3:** `dvc.lock` updated; artifact exists on disk and round-trips through Stage 1's `PayoffMatrix` validator for a sample of entries.

---

## Stage 4 — Equilibrium Solver

19. In `core/game_theory.py`, implement the closed-form 2x2 analytical Nash solver — exact algebraic formula, no `scipy` dependency on this path. **[D-2]**
20. Implement the degenerate-game check (zero-determinant condition, per D-6); on detection, raise `SolverException` rather than returning a degraded result. **[D-6]**
21. Implement the `scipy.optimize.linprog(method='highs')` path, dispatched purely on `PayoffMatrix.matrix`'s actual shape (`m > 2 or n > 2`) — not a sample-size comparison; that decision already happened in Stage 2. **[D-2]**
22. Implement input validation at the solver boundary (any matrix entry outside `[0, 1]` → `SolverException`), matching the Markov solver's own existing defensive-input pattern rather than relying solely on Stage 1's schema-level `Field` constraints. **[D-6]**
23. Write solver-level unit tests: 2x2 closed-form vs. a hand-computed golden value, 3x3 via `linprog` vs. a known equilibrium, the degenerate-game exception path, the invalid-probability exception path.

**Gate 4:** both dispatch paths and both exception paths pass; `linprog` calls confirmed well under 1ms via a quick timing sanity check (not a formal benchmark).

---

## Stage 5 — Sufficiency Gate & `compute_exploit()` Orchestration

24. Implement the two-level sufficiency check (D-4): `n_opp_total < threshold` OR any relevant `observation_counts[i][j] < threshold` → return `ExploitResult(sufficient_data=False, ..., n_opp_total=..., payoff_matrix=...)` with every equilibrium/recommendation field left `None`. Graceful degradation (FR-6), not an exception — distinct from Stage 4's fail-loud solver-fault path.
25. Implement `compute_exploit(payoff_matrix, params) -> ExploitResult`: sufficiency check first; if sufficient, call Stage 4's solver for the equilibrium mixes and value, compute the observed returner mix from `observation_counts`, find the best-response pure strategy x_BR = argmax_x xᵀΠŷ, compute `delta` and `expected_value_if_exploiting`. **[D-3, D-4]**
26. Write unit tests for `compute_exploit()`: sufficient-data path (fully-populated result), insufficient-data path (gracefully degraded), and assert `delta >= 0` holds across every fixture — best response can never be worse than the equilibrium value, by definition.

**Gate 5:** both branches pass; the `delta >= 0` invariant holds on every test fixture.

---

## Stage 6 — Solver-Failure Exception Wiring

27. Confirm (or add) a `SolverException` subclass/reuse path in `src/utils/exceptions.py` specific enough to distinguish a game-theory fault from a Markov-solver fault in logs, while inheriting the same `BasePulseException` hierarchy. **[D-6]**
28. Confirm neither Stage 4's solver functions nor Stage 5's `compute_exploit()` ever silently catch and swallow a `SolverException` anywhere.

**Gate 6:** a deliberately degenerate/malformed fixture reliably raises `SolverException` and is never accidentally caught by a bare `except Exception`.

---

## Stage 7 — `StrategyExploitNode` Integration

29. In `src/graph/strategy_exploit.py`, remove `count_opponent_observations()` entirely and its now-unused `StratumTable` import if nothing else in the file needs it — this Phase-4 approximation is superseded by `PayoffMatrix.n_opp_total`/`observation_counts`. **[D-4]**
30. Update `make_strategy_exploit_node()`'s factory signature to close over the loaded payoff-matrix artifact (Stage 3's output), matching `make_pressure_diagnostic_node(pressure_artifact, params)`'s established closure pattern.
31. Update `strategy_exploit_node()`'s body: look up the current point's `PayoffMatrix` by `(returner_id, surface, serve_number)`, falling back per Stage 2's hierarchical convention; if no matrix exists for this opponent at all (never charted), return an explicit insufficient-data `ExploitResult` — still the FR-6 path, triggered one level earlier than Stage 5's not-enough-data-in-an-existing-matrix case.
32. Call `compute_exploit()` with the looked-up matrix; return its result as `exploit_result`.
33. Update `pulse_graph.py`'s `load_graph_artifacts()` to also load the payoff-matrix artifact once, alongside the existing `StratumTable`/`PressureModelArtifact` loads, and thread it into `make_strategy_exploit_node()`'s registration in `build_pulse_graph()`. **[D-7]**
34. Update `tests/unit/test_strategy_exploit.py`: replace the two Phase-4 tests (built around the retired `count_opponent_observations()`/`status` string) with tests against the new contract — sufficient-data, insufficient-data, and no-matrix-at-all.

**Gate 7:** `build_pulse_graph()` compiles cleanly with the new artifact wired in; all `test_strategy_exploit.py` tests pass; grep confirms zero remaining references to `count_opponent_observations`, `status`, `recommendation`, or `is_sufficient_sample` on `exploit_result` anywhere in `src/` or `tests/` — closing Gate 1's grep list.

---

## Stage 8 — `tests/unit/test_game_theory.py`

35. Consolidate the full set of golden-value/gate-verification properties from Stage 0 step 2 into `tests/unit/test_game_theory.py`.
36. Confirm each property has its own explicitly-named test function — not folded into one parametrized test that could hide which specific property failed.

**Gate 8:** every property from §8 has a corresponding, individually-named, passing test.

---

## Stage 9 — Integration Tests Through `PulseGraphState`

37. Update `tests/integration/test_conditional_graph.py`'s existing "high-leverage, high-data" fixture (built in Phase 4) to assert against the new `ExploitResult` contract instead of the retired `status: "module_not_yet_implemented"` value — this fixture already reaches `StrategyExploitNode`; its assertions need updating, not a rebuild.
38. Add one new fixture for the no-payoff-matrix-exists case (an opponent never charted) — Phase 4's original three fixtures never had reason to cover this branch.
39. Confirm `TacticalOutputNode`'s existing LLM-call guard still fires correctly on the new `ExploitResult` shape (no code change expected, per D-11) — but its assembled payload's JSON shape has changed, so rebuild at least one `tests/evals/test_tactical_output_groundedness.py` fixture against the new field names. **[D-11]**

**Gate 9:** all integration fixtures pass; the groundedness eval's fixtures reflect the new `ExploitResult` fields, not the retired ones.

---

## Stage 10 — Full Phase 5 Verification

40. `uv run ruff check .` and `uv run ruff format --check .` — 0 errors.
41. `uv run pyright` — 0 errors.
42. `python scripts/check_file_size.py` — confirm `core/game_theory.py` and the new script stay under the 1,000-line ceiling; split now rather than after the ceiling is hit if the solver, sufficiency gate, and matrix-construction logic risk crowding one file.
43. `uv run pytest --cov=src --cov-report=term-missing` — full suite green, coverage ≥70%, with `core/game_theory.py` and the updated `strategy_exploit.py` checked specifically given they're this phase's highest-novelty, highest-risk code.
44. `uv run dvc repro` — confirm the full pipeline, including the new `build_payoff_matrices` stage, reproduces cleanly end to end.

**Gate 10:** all green. Phase 5 is functionally complete.

---

## Stage 11 — Documentation Closeout

45. Write a Phase 5 evaluation report mirroring `walkthrough.md`/`langgraph_orchestration_report.md`'s structure — exit-criteria table, example `ExploitResult` payloads (sufficient and insufficient-data cases), golden-value results.
46. Log the new `SolverException` reuse and the hierarchical matrix-fallback pattern into `system_design.md` as a new dated ADR entry, not a silent edit; mark `technical_roadmap.md`'s Phase 5 entry ✅ Complete.
47. Note in the same ADR entry that D-1's original three-option framing (from the pre-reconciliation draft) was resolved by the spec in favor of the full 2D matrix game — a one-line historical note, not an open item, since D-1 is already closed as of the reconciled decisions document.

**Gate 11 (final):** documentation closeout complete.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify exact spec details) → Stage 1 (contracts) → Stage 2 (matrix construction)
   → Stage 3 (DVC artifact stage) → Stage 4 (solver) → Stage 5 (sufficiency gate + orchestration)
   → Stage 6 (exception wiring) → Stage 7 (node integration) → Stage 8 (solver test suite)
   → Stage 9 (integration suite) → Stage 10 (CI gate) → Stage 11 (docs)
```

47 steps, 12 gates. No implementation starts until Stage 0's Gate passes.
