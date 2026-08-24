# Post-Match Tactical Reporting & Intelligence Engine — Execution Workflow

**Ordered Implementation Steps & Stage Gate Verification**

**Product:** PULSE | **Feature:** Post-Match Reporting (Option A) | **Version:** 1.0.0 | **Date:** 2026-08-24  
**Status:** 🟡 Drafted & Awaiting Approval  
**Authority:** `post_match_reporting_implementation_plan_and_decisions.md` (Approved D-1–D-8), `prd.md` (FR-12, FR-13), `system_design.md` (ADR-013)  
**Scope of this document:** Sequencing and quality gating only; no code changes.

---

## Execution Flow Overview

```
Stage 0 (Pre-Flight Audit) ──► Stage 1 (Analytics Core & Engine) ──► Stage 2 (Wire Schemas & Serialization)
                                                                               │
                                                                               ▼
Stage 5 (Cockpit Modal & UI) ◄── Stage 4 (API Route Delivery) ◄── Stage 3 (Grounded Narrative Synthesis)
          │
          ▼
Stage 6 (Integration Tests & Quality Gate Audit)
```

---

## Stage 0 — Pre-Implementation Verification & Workspace Pre-Flight

1. Verify workspace cleanliness via `git status`.
2. Confirm baseline test suite is 100% green (`uv run pytest` passes 152/152 tests with 0 warnings).
3. Confirm all existing `src/` files satisfy the line-count ceiling (`python scripts/check_file_size.py` passes).
4. Verify required model artifacts exist in `artifacts/models/`:
   - `point_win_classifier/stratum_table.json`
   - `pressure_deviation/pressure_deviation.json`
   - `game_theory/payoff_matrices.json`

**Gate 0:** Workspace clean; 152/152 baseline tests passing; all model artifacts verified.

---

## Stage 1 — Deterministic Post-Match Analytics Engine (`src/analytics/match_report.py`)

5. Create `src/analytics/` directory and docstring-only `src/analytics/__init__.py`. **[D-1]**
6. Implement `src/analytics/match_report.py` containing deterministic aggregation logic: **[D-1, D-6, D-7]**
   - `compute_match_summary(records: list[PointRecord]) -> MatchSummaryStats`:
     - Aggregates total points, games, sets, final score, match winner, average $\Delta L$, peak $\Delta L$, and high-leverage point count.
   - `extract_top_pivotal_points(records: list[PointRecord], top_n: int = 5) -> list[PivotalPointEntry]`:
     - Ranks points by $\Delta L$, computes Wilson 95% confidence intervals $[L_{\text{low}}, L_{\text{high}}]$, and identifies match outcome swings.
   - `compute_pressure_resilience(records: list[PointRecord]) -> list[PlayerPressureMetrics]`:
     - Partitions points into Routine ($[0.0, 0.10)$), Elevated ($[0.10, 0.25)$), and Critical ($[0.25, 1.00]$) buckets and evaluates realized point-win rates vs Empirical-Bayes shrinkage priors.
   - `compute_game_theory_audit(records: list[PointRecord]) -> list[GameTheoryExploitAudit]`:
     - Compiles realized serve direction distributions vs Nash equilibrium mix across deuce and ad courts, quantifying returner bias and realized $+EV$ exploit margins ($\delta$).
7. Implement `format_match_report_markdown(payload: MatchReportPayload) -> str` to generate a standardized, human-readable Markdown report. **[D-3]**

**Gate 1:** `src/analytics/match_report.py` implemented; unit tests confirm exact mathematical outputs and bucket partitioning across golden test match fixtures.

---

## Stage 2 — Pydantic v2 Wire Contracts (`src/api/schemas.py`)

8. Update `src/api/schemas.py` to define typed request and response contracts: **[D-2]**
   - `PivotalPointEntry`: Pydantic model for top pivotal points with score context and Wilson intervals.
   - `PlayerPressureMetrics`: Pydantic model for player win rates across leverage tiers and $\Delta p$ pressure shifts.
   - `GameTheoryExploitAudit`: Pydantic model for serve direction distributions, Nash mix, and $+EV$ margins.
   - `MatchReportResponse`: Comprehensive response schema containing match metadata, executive summary, pivotal points, pressure resilience, game theory audit, and markdown output.

**Gate 2:** Pydantic schemas validate cleanly; serialization roundtrips verified in `tests/unit/test_api_schemas.py`.

---

## Stage 3 — Grounded Narrative Synthesis Integration (`src/analytics/match_report.py`)

9. Implement `generate_executive_debrief(payload: MatchReportPayload, llm_client: Any | None = None) -> str`: **[D-4]**
   - Calls the grounded LLM narrative synthesis client to draft a 3-paragraph executive tactical summary referencing exact numbers ($\Delta L$, $\Delta p$, $\delta$).
   - Implements a deterministic template-based fallback if the LLM client is unreachable or disabled, ensuring 100% availability.

**Gate 3:** Narrative debrief contains 0 hallucinated numbers; deterministic fallback passes when LLM is mocked out.

---

## Stage 4 — FastAPI Report Endpoints (`src/api/streaming.py`)

10. Register `GET /v1/matches/{match_id}/report` endpoint in `src/api/streaming.py`: **[D-3]**
    - Query parameters: `format: Literal["json", "markdown"] = "json"`.
    - Returns `MatchReportResponse` (JSON) or `PlainTextResponse` (Markdown).
    - Handles missing match IDs with HTTP 404 and uninitialized graphs with HTTP 503.
11. Update `tests/unit/test_streaming.py` and `tests/unit/test_api_main.py` with endpoint route registration tests.

**Gate 4:** `GET /v1/matches/{match_id}/report` returns HTTP 200 with both JSON and Markdown formats for existing match IDs.

---

## Stage 5 — Tactical Cockpit Interactive Modal (`src/api/static/`)

12. Update `src/api/static/index.html`: **[D-5]**
    - Add `#btn-match-report` button to `#stream-controls` (styled with reporting icon `📊`).
    - Add `#modal-match-report` container with semantic sections:
      - `#report-header`: Match title, surface, score badge, and close button.
      - `#report-executive-summary`: Grounded tactical briefing text card.
      - `#report-pivotal-points`: Top-5 pivotal points table with clickable jump-to-point links.
      - `#report-pressure-breakdown`: Routine vs Critical leverage win rate comparison bars.
      - `#report-game-theory-audit`: Serve direction vs Nash mix comparison cards.
      - `#report-actions`: `Copy Markdown`, `Download JSON`, `Print / Save PDF`, `Close`.
13. Update `src/api/static/style.css`: **[D-5]**
    - Add glassmorphic modal overlay styles (`.modal-backdrop`, `.modal-dialog`, `--bg-surface`).
    - Add tabular report formatting with monospace numbers (`font-variant-numeric: tabular-nums`).
    - Add responsive print styles (`@media print`) for clean PDF generation.
14. Update `src/api/static/app.js`: **[D-5]**
    - Implement `openMatchReportModal(matchId)` and `closeMatchReportModal()`.
    - Fetch report from `GET /v1/matches/${matchId}/report`.
    - Bind clipboard copy and JSON download event handlers.
    - Wire pivotal point row clicks to seek the Canvas 2D oscillogram to the exact point index.

**Gate 5:** Modal opens smoothly in browser; data populates correctly; copy/download/jump-to-point actions function cleanly with zero console errors.

---

## Stage 6 — Automated Integration Tests & Quality Gate Audit

15. Create `tests/unit/test_match_report.py`:
    - Tests exact leverage ranking, pressure bucket partitioning, and game theory audit calculations.
16. Create `tests/integration/test_match_report_api.py`:
    - Tests `GET /v1/matches/{id}/report` endpoint across JSON and Markdown formats.
    - Asserts DOM contracts and static asset delivery in `tests/integration/test_static_ui.py`.
17. Run full quality gate audit:
    - `uv run pytest` (confirming all unit, integration, and eval tests pass).
    - `uv run ruff check .` and `uv run pyright` (0 errors, 0 warnings).
    - `python scripts/check_file_size.py` (confirm all files < 1,000 lines).
18. Update documentation artifacts:
    - Update `README.md`, `technical_roadmap.md`, and `reports/docs/architecture/system_design.md`.

**Gate 6:** All tests passing (100%); strict types and linter clean; file sizes < 1,000 lines; Phase complete.

---

## Reconciled Stage Gate Summary

| Stage | Focus Area | Closing Gate Condition | Status |
|:---:|---|---|:---:|
| **Stage 0** | Pre-Flight Audit | Workspace clean, baseline tests (152/152) green | 🟡 Pending |
| **Stage 1** | Analytics Engine | `src/analytics/match_report.py` deterministic aggregation | 🟡 Pending |
| **Stage 2** | Wire Schemas | `MatchReportResponse` Pydantic v2 schemas validated | 🟡 Pending |
| **Stage 3** | Grounded Synthesis | Executive debrief synthesis + deterministic fallback | 🟡 Pending |
| **Stage 4** | API Endpoints | `GET /v1/matches/{id}/report` JSON & Markdown routes | 🟡 Pending |
| **Stage 5** | Cockpit Modal UI | Interactive glassmorphic modal & export tools | 🟡 Pending |
| **Stage 6** | Quality Gate Audit | Full test suite green (`pytest`, `pyright`, `ruff`, line ceiling) | 🟡 Pending |

---

**Execution Rule:** Do not begin any stage until the preceding stage's gate has fully passed and user approval has been explicitly granted.
