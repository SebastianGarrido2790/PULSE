# Post-Match Reporting & Tactical Intelligence Engine — Implementation Plan & Decisions

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Feature:** Post-Match Reporting & Tactical Intelligence Engine (Option A)  
**Version:** 1.0.0 | **Date:** 2026-08-24  
**Status:** Approved & Ready for Execution  
**Authority:** `reports/docs/decisions/post-match_reporting_assessment.md`, `prd.md` (FR-12, FR-13), `system_design.md` (ADR-013)

---

## 1. Executive Summary & Design Rationale

While PULSE excels as an event-driven, real-time streaming leverage monitor, coaches, performance analysts, and tournament evaluators require a comprehensive, mathematically grounded **post-match report** once the match concludes.

In accordance with **Option A** (approved in `post-match_reporting_assessment.md`), PULSE will implement an in-engine report generator and interactive modal within the Tactical Cockpit. This preserves the **zero-dependency, single-container architecture (ADR-013)** while transforming point-by-point telemetry into a persistent, actionable strategic artifact.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          PULSE POST-MATCH INTELLIGENCE REPORT                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. MATCH OVERVIEW & SCORE PROGRESSION                                                  │
│    Match ID, Surface, Players, Final Score, Total Points, Winner                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. EXECUTIVE TACTICAL BRIEFING                                                         │
│    LLM-Synthesized Strategic Debrief (Strictly Grounded in Computed Metrics)           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. PIVOTAL MOMENTS AUDIT                                                               │
│    Top-5 Highest Leverage Inflection Points (Ranked by ΔL with Wilson 95% CI)          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. PRESSURE RESILIENCE DIAGNOSTIC                                                      │
│    Routine vs Elevated vs Critical Leverage Win Rates (Empirical-Bayes Δp Shift)       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 5. GAME-THEORETIC SERVE & RETURN AUDIT                                                 │
│    Realized Serve Mix vs Nash Equilibrium (x*) │ Returner Bias (ŷ) │ Realized +EV (δ)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 6. SUFFICIENCY GATE & DATA TRANSPARENCY                                                │
│    Sample Size (N) Disclosures Backing Every Assertion                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Formal Architectural Decisions (D-1 through D-8)

### D-1: Deterministic In-Process Aggregation Module (`src/analytics/match_report.py`)

- **Decision:** Build a dedicated analytics module `src/analytics/match_report.py` that processes a complete match's point records and returns a fully computed `MatchReportPayload`.
- **Rationale:** Keeps mathematical aggregation strictly deterministic and separated from API serialization and presentation logic. Pure Python/NumPy computation with zero LLM arithmetic.

### D-2: Typed Pydantic v2 Wire Contracts (`src/api/schemas.py`)

- **Decision:** Define explicit Pydantic v2 schemas:
  - `PivotalPointEntry`: `point_index`, `set_num`, `game_score`, `point_score`, `server_id`, `returner_id`, `delta_leverage`, `leverage_low`, `leverage_high`, `winner`, `impact_narrative`.
  - `PlayerPressureMetrics`: `player_id`, `routine_win_rate`, `elevated_win_rate`, `critical_win_rate`, `pressure_shift_delta_p`, `resilience_assessment`.
  - `GameTheoryExploitAudit`: `stratum_key`, `server_id`, `returner_id`, `court_side`, `nash_serve_mix`, `realized_serve_mix`, `returner_bias`, `exploit_gain_delta`, `sample_size`, `sufficiency_gated`.
  - `MatchReportResponse`: Full typed contract with markdown export convenience method.
- **Rationale:** Strict typing enforces valid boundaries and seamless JSON/OpenAPI schema documentation.

### D-3: REST API Endpoint with Dual Serialization (`GET /v1/matches/{match_id}/report`)

- **Decision:** Register `GET /v1/matches/{match_id}/report` in `src/api/streaming.py` supporting `?format=json` (default) and `?format=markdown`.
- **Rationale:** Enables programmatic consumption by external analytics pipelines and direct copy/download of ready-to-share Markdown reports.

### D-4: Grounded LLM Narrative Synthesis via `TacticalOutputNode`

- **Decision:** Re-use the existing `TacticalOutputNode` prompt template and LLM client to generate the high-level executive debrief from the deterministic report payload. If the LLM is unreachable or disabled, fall back cleanly to a deterministic templated executive summary.
- **Rationale:** Adheres to the Brain/Brawn boundary (§5 of `AGENTS.md`) and guarantees zero hallucination of figures.

### D-5: Embedded Cockpit Modal UI (`src/api/static/index.html`, `style.css`, `app.js`)

- **Decision:**
  - Add `#btn-match-report` to the Cockpit controls (enabled on-demand or automatically upon match replay completion).
  - Implement `#modal-match-report` with glassmorphic styling, scrollable tabbed sections, and action buttons (`Copy Markdown`, `Download JSON`, `Print / Save PDF`, `Close`).
  - Interactive link: Clicking a pivotal point in the report table seeks the Canvas 2D oscillogram to that exact point index.
- **Rationale:** Zero-CDN and zero-NPM compliance (ADR-013); seamless, instantaneous post-match review directly in the browser.

### D-6: Top-5 Pivotal Points Ranking Algorithm

- **Decision:** Rank points by point leverage $\Delta L(S)$, resolving ties by total match probability swing $|\Delta M(S)|$. Include set and game context and Wilson 95% confidence bounds $[L_{\text{low}}, L_{\text{high}}]$.
- **Rationale:** Provides coaches with an unambiguous, mathematically provable record of where the match was won or lost.

### D-7: Leverage Bucket Partitioning for Pressure Analysis

- **Decision:** Classify points into three standardized leverage buckets:
  - _Routine:_ $\Delta L < 0.10$
  - _Elevated:_ $0.10 \le \Delta L < 0.25$
  - _Critical:_ $\Delta L \ge 0.25$
    Compute realized server and returner point-win rates in each bucket and compare against the Empirical-Bayes population prior.
- **Rationale:** Directly maps to the Phase 3 pressure deviation model and isolates genuine clutch performance from small-sample noise.

### D-8: Automated Quality Gate & CI Test Coverage

- **Decision:** Implement comprehensive unit tests (`tests/unit/test_match_report.py`) and integration tests (`tests/integration/test_match_report_api.py`), verifying 100% schema validation, mathematical accuracy, MIME types, and DOM contracts.
- **Rationale:** Blocks merges if report metrics diverge or file sizes exceed the 1,000-line ceiling.

---

## 3. Component Architecture & Flow

```mermaid
flowchart TD
    A[Historical Match Dataset / SQLite Session DB] --> B[src/analytics/match_report.py]
    B --> C[Compute Leverage Distribution & Top-5 Pivotal Points]
    B --> D[Compute Pressure Resilience Breakdown]
    B --> E[Compute Game Theory Nash & Bias Audit]
    C & D & E --> F[Assemble MatchReportPayload]
    F --> G[TacticalOutputNode Grounded Synthesis]
    G --> H[FastAPI: GET /v1/matches/{id}/report]
    H -->|JSON / Markdown| I[Tactical Cockpit Modal: src/api/static/]
```

---

## 4. Deliverables & File Changes Summary

| Target File                                                         | Component Layer   | Action |
| :------------------------------------------------------------------ | :---------------- | :----: |
| `src/analytics/__init__.py`                                         | Package Stub      | Create |
| `src/analytics/match_report.py`                                     | Analytics Engine  | Create |
| `src/api/schemas.py`                                                | Wire Schemas      | Modify |
| `src/api/streaming.py`                                              | Route Handlers    | Modify |
| `src/api/static/index.html`                                         | HTML5 Layout      | Modify |
| `src/api/static/style.css`                                          | CSS Design System | Modify |
| `src/api/static/app.js`                                             | UI Controller     | Modify |
| `tests/unit/test_match_report.py`                                   | Unit Tests        | Create |
| `tests/integration/test_match_report_api.py`                        | Integration Tests | Create |
| `reports/docs/workflows/post_match_reporting_execution_workflow.md` | Workflow          | Create |
