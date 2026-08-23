# Phase 7 — Execution Workflow
**Observability, CI/CD, Shadow-Mode Acceptance — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 7 of 7 (final) | **Version:** 1.0.0 | **Date:** 2026-08-20
**Status:** 🟡 Ready to execute — no code written yet
**Authority:** `phase7_implementation_plan_and_decisions.md` v1.0.0 (D-1–D-13, all approved)
**Scope of this document:** sequencing only, no code.

---

## How to Read This

11 stages (0–10), strictly ordered. Steps numbered continuously (1–35) so any step is unambiguously referenceable. Each step is tagged with the decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

**Note on VERIFY items:** the approved decisions document's §1.3 VERIFY items are still open — approval of the *decisions* didn't waive the requirement to actually read `project_charter.md` §5, `pulse_ml_canvas.md` §8, and `src/utils/logger.py` directly. Stage 0 resolves these before anything else proceeds, exactly as it did for the two prior phases that had blocking VERIFY items.

---

## Stage 0 — Pre-Implementation Verification

1. Read `project_charter.md` §5 (Definition of Done) in full. Produce an explicit checklist mapping every DoD item to the Phase 7 deliverable or decision that satisfies it — this checklist is what Stage 9's final report gets reconciled against, not a generic summary written from memory of this document.
2. Read `pulse_ml_canvas.md` §8 in full. Confirm or revise D-9's scaffolding assumption (a standalone offline script mirroring `build_payoff_matrices.py`'s shape) against the actual stated methodology — if §8 implies something structurally different, that's resolved here, not improvised at Stage 7.
3. Read `src/utils/logger.py` directly. Confirm whether `structlog` JSON output already exists project-wide (making D-11 an audit pass) or needs introducing for the first time (making it a real migration, per D-11's own explicit caveat that this changes the scope of Stage 3 below).
4. Read the current `.github/workflows/ci.yml` directly — not the Phase 1 roadmap's description of what it was meant to contain — to know exactly what Stage 6 needs to add versus what's already there.
5. Confirm `llm_client.py`'s exact untested line ranges (lines 42–82 per the last-seen Phase 6 coverage report) to scope Stage 1's tests precisely rather than guessing at what's uncovered.

**Gate 0:** all three VERIFY items resolved against literal source text; D-9's and D-11's actual scope confirmed, not assumed; `ci.yml`'s current real content known.

---

## Stage 1 — Close the `llm_client.py` Coverage Gap

6. Write tests mocking: (a) a network/timeout exception from the Anthropic SDK call, (b) a missing `ANTHROPIC_API_KEY`, (c) a malformed or empty API response — each asserting the deterministic-passthrough fallback fires correctly (no exception propagates out, a structured payload is returned instead). **[D-8]**
7. Re-run coverage on `llm_client.py` specifically; confirm it moves well clear of where it sat before, closing Finding C directly rather than letting the aggregate absorb it again.

**Gate 1:** `llm_client.py` coverage measurably improved; all three fallback paths have explicit, individually-named tests — not folded into one parametrized test that could hide which path actually failed.

---

## Stage 2 — OTel Spans for Solver & Model Layers

8. Add per-call spans to `core/markov_solver.py`'s public functions (e.g., `compute_leverage()`), `core/leverage_uncertainty.py`'s `propagate_leverage_uncertainty()`, `models/point_win_classifier.py`'s `resolve_point_win_probability()`, `models/pressure_deviation.py`'s `get_pressure_deviation()`, and `core/game_theory.py`'s `compute_exploit()` — each opening a span at entry, relying on OTel's automatic context propagation to nest under whatever node-level span is already open. **[D-10]**
9. Confirm span attributes carry genuinely useful latency-profiling detail (e.g., which fallback tier resolved, matrix dimensions solved) without just duplicating what `decision_log` already records.
10. Manual trace inspection: run one replayed point through the graph — specifically an escalated one, not a routine one — and confirm the resulting span tree shows node → solver/model child spans correctly nested, not appearing as unrelated siblings.

**Gate 2:** span tree correctly nested for at least one escalated point, exercising `PressureDiagnosticNode`'s and `StrategyExploitNode`'s new child spans, not just `StateMonitorNode`'s.

---

## Stage 3 — Structured Logging Finalization

11. Per Stage 0 step 3's outcome: if `structlog` JSON output already exists, audit every module for stray `print()` calls or bare stdlib `logging` calls bypassing `get_logger()`. If it doesn't exist yet, stop here and renegotiate this stage's scope before proceeding — per D-11's own caveat, that's a materially bigger task than this workflow currently accounts for. **[D-11]**
12. Fix any bypasses found.

**Gate 3:** grep-confirmed zero `print()` statements and zero bare `logging.` calls anywhere in `src/`; every log line traceable back to `get_logger()`.

---

## Stage 4 — Dockerfile

13. Write a multi-stage `Dockerfile`: a builder stage installing dependencies via `uv`, a final stage running as a non-root user on a SHA256 digest-pinned Python base image, `COPY`ing the application code and the current `artifacts/` directory (stratum table, pressure artifact, payoff matrices, validated points parquet) into the image. **[D-4, D-5, D-7]**
14. Set the default `CMD` to run `api.main`; confirm `uv run simulator.replay ...` still works correctly via a runtime override against the same image, not a separate one.
15. Add a `HEALTHCHECK` instruction probing `GET /health`. **[D-12]**

**Gate 4:** `docker build` succeeds; the built image runs the API by default and correctly runs the CLI when invoked that way; `docker inspect` confirms a non-root user and a digest-pinned (not tag-pinned) base image.

---

## Stage 5 — `docker-compose.yml`

16. Define the API service: exposes `params.yaml`'s configured port, mounts a named volume at the SQLite database's path (`artifacts/pulse_session.db` or its parent directory) so the audit trail survives `docker compose down`/restart. **[D-4, D-6]**
17. Confirm `docker compose up --build` — the project's established one-click command, previously broken by the missing compose file — works end-to-end for the first time.

**Gate 5:** `docker compose up --build` starts cleanly; a `docker compose down` followed by `docker compose up` with no rebuild confirms the SQLite database file survived the restart.

---

## Stage 6 — CI Pipeline Completion

18. Extend `.github/workflows/ci.yml` to the full target order: lint → type-check → file-size check → unit tests → integration tests → eval suite → coverage gate (≥70% aggregate, per D-8's Option C — no per-module floor) → Docker build → Trivy image scan — adding every stage past what Phase 1's baseline already covers, confirmed in Stage 0. **[D-3, D-8]**
19. Confirm the coverage gate step actually fails the pipeline on a deliberately-introduced coverage regression — a real negative test of the gate, not just a positive run that happens to pass.
20. Confirm the Trivy step fails the pipeline on a deliberately-introduced CRITICAL CVE if that can be tested safely (e.g., temporarily pinning a known-vulnerable base image tag in a throwaway branch), or at minimum confirm it runs and reports correctly against the real image.

**Gate 6:** full pipeline green on a clean run; both the coverage-gate and Trivy-gate negative tests confirm the gates actually block — or, where a negative test genuinely couldn't be run safely, the reasoning for that is documented rather than silently skipped.

---

## Stage 7 — Retrospective Escalation-Precision Evaluation

21. Implement `scripts/evaluate_escalation_precision.py` per Stage 0 step 2's confirmed methodology from `pulse_ml_canvas.md` §8 — not the placeholder shape this document assumed before that was read. **[D-9]**
22. Run it across the full historical match set (or whatever population §8 actually specifies); produce `reports/docs/evaluations/escalation_precision_report.md`, stating D-2's "held-out" limitation explicitly — matches not used for manual calibration/debugging, not a leakage-free statistical holdout, given the per-player-aggregated artifact design. **[D-2]**
23. Report the measured alert-precision and false-escalation-rate numbers against `prd.md` §7's targets (≥0.75, <0.15) plainly, whichever way they land — not summarized in a way that implies they cleared the bar if they didn't.

**Gate 7:** evaluation script runs reproducibly (same seed, same result); report published with the D-2 limitation stated explicitly, not omitted or softened.

---

## Stage 8 — Shadow-Mode Acceptance Run

24. With the Docker image and compose stack from Stages 4–5 running, select a held-out set of matches (per D-2's operational framing, not the stricter statistical one from Stage 7) and drive each one through the real `GET /v1/matches/{match_id}/stream` endpoint end-to-end — the deployed system, not internal function calls. **[D-1, D-2]**
25. For each match, confirm: correct event sequencing, correct SQLite persistence (cross-checked against the streamed events, mirroring Phase 6's own persistence-parity integration test pattern), latency within the `StateMonitorNode` <1s / triggered-node <5s budgets, and zero unhandled exceptions.
26. Record any failures precisely — which match, which point, what broke — rather than reporting a pass rate that would hide exactly the kind of operational surprise this run exists to catch.

**Gate 8:** the full held-out match set replays cleanly through the deployed system with zero unhandled failures, or every failure found is triaged and either fixed or explicitly logged as a known, accepted limitation before proceeding.

---

## Stage 9 — Final Evaluation Report & Definition-of-Done Reconciliation

27. Write the final evaluation report in the established exit-criteria sign-off format, checked item-by-item against Stage 0 step 1's `project_charter.md` §5 checklist — a literal per-item reconciliation, not a generic summary. **[D-13]**
28. For any DoD item this decisions document didn't anticipate — a real possibility, since §5's actual content was never available while D-1 through D-13 were being written — flag it explicitly rather than silently omitting it from the sign-off table.

**Gate 9:** every item in `project_charter.md` §5 has an explicit ✅/❌ line in the final report, with evidence cited, not an aggregate "complete" claim standing in for the checklist.

---

## Stage 10 — Full Verification & Project Close-Out

29. `uv run ruff check .` and `uv run ruff format --check .` — 0 errors.
30. `uv run pyright` — 0 errors.
31. `python scripts/check_file_size.py` — confirm all files, including any new Docker-related scripts, stay under the 1,000-line ceiling.
32. `uv run pytest --cov=src --cov-report=term-missing` — full suite green, aggregate ≥70%, `llm_client.py` specifically confirmed improved from Stage 1's baseline.
33. Full CI pipeline green on the actual GitHub Actions runner — the real gate, not a local approximation of it.
34. Log a final ADR into `system_design.md`, continuing the established numbering, capturing this phase's genuinely architectural decisions: D-1/D-2 (shadow-mode and holdout definitions), D-4/D-7 (Docker build shape and artifact-baking), D-3 (Trivy scan target), D-8 (coverage gate policy) — logged as a new dated entry, matching the convention every prior phase used.
35. Update `technical_roadmap.md`'s Phase 7 entry to ✅ Complete — the last phase on the roadmap.

**Gate 10 (final):** all green; ADR logged; `technical_roadmap.md` shows every phase complete.

---

## Summary — Stage Dependency Chain

```
Stage 0 (verify) → Stage 1 (close llm_client.py gap) → Stage 2 (OTel spans)
   → Stage 3 (logging audit) → Stage 4 (Dockerfile) → Stage 5 (docker-compose.yml)
   → Stage 6 (CI pipeline completion) → Stage 7 (precision evaluation)
   → Stage 8 (shadow-mode acceptance) → Stage 9 (final report + DoD reconciliation)
   → Stage 10 (full verification + close-out)
```

35 steps, 11 gates. No implementation starts until Stage 0's Gate passes — and Stage 0's first item is reading the document that actually defines what "done" means for this project.
