# Phase 6.5 & 6.6 — Interactive Presentation Layer & Post-Match Reporting Architecture

## Executive Summary

Phases 6.5 and 6.6 deliver the **Embedded Real-Time Tactical Cockpit & Post-Match Intelligence Suite** for PULSE — a single-page, dark-mode glassmorphic presentation layer served directly by FastAPI. Designed specifically for portfolio evaluators, recruitment managers, coaches, broadcast teams, and performance analysts, the Tactical Cockpit provides an immediate visual lens into PULSE's event-driven intelligence during live match replay as well as retrospective post-match tactical debriefs, without requiring external frontend build tooling, npm packages, or third-party CDN scripts.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PULSE TACTICAL COCKPIT                                │
├───────────────────────────────────────┬─────────────────────────────────────────┤
│ 1. SCOREBOARD HEADER                  │ 2. LEVERAGE & MOMENTUM OSCILLOGRAM      │
│    Set/Game/Point Tracker             │    Bespoke Canvas 2D Engine             │
│    Server Indicator & P(Win) Gauge    │    Shaded Wilson 95% Confidence Band    │
│    Dynamic Leverage Alert Badge       │    Threshold (τ = 5%) & Inflection Dots │
├───────────────────────────────────────┼─────────────────────────────────────────┤
│ 3. LANGGRAPH TOPOLOGY INSPECTOR       │ 4. GAME-THEORETIC EXPLOIT PANEL         │
│    Real-Time Node Firing States       │    2×2 Minimax Payoff Serving Matrix    │
│    Latency Gauges & Routing Audit     │    Nash Serve Mix vs Observed Bias      │
│    Sufficiency Gate (N ≥ 10) Monitor  │    +EV Gain Callout & Best Response     │
├───────────────────────────────────────┴─────────────────────────────────────────┤
│ 5. TACTICAL ADVISORY FEED                                                       │
│    Coach & Broadcast Signal (Narrative Synthesis & Actionable Recommendations)  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 6. STREAM CONTROL BAR & POST-MATCH REPORT LAUNCHER                              │
│    Match Selection │ Speed (0.5x, 1x, 2x, Instant) │ [📑 View Post-Match Report]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 7. POST-MATCH TACTICAL INTELLIGENCE MODAL (Phase 6.6 Overlay)                   │
│    Executive Debrief │ Key Indicators KPI Grid │ Top 5 Pivotal Moments Table    │
│    Pressure Resilience Tiers │ Minimax Serve/Return Audit │ Markdown/JSON/Print │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Architectural Decisions & Principles

### 1.1 In-Process Static Asset Delivery (ADR-013)
- **Zero CDN & Zero NPM Invariant:** The entire cockpit is built using pure semantic HTML5, Vanilla CSS3 (Custom Properties & CSS Grid), and native ES6 JavaScript (`src/api/static/`). It requires zero Node.js runtime, zero frontend bundlers (Vite/Webpack), and zero remote CDN fetches (`unpkg`, `jsdelivr`, `cdnjs`).
- **FastAPI Static Mount:** Static assets are served via `fastapi.staticfiles.StaticFiles` mounted at `/static`. Root requests (`GET /`) and UI alias (`GET /ui`) deliver `index.html` with explicit `text/html` response typing.
- **Route Precedence Protection:** API routing (`/v1/matches`), OpenAPI documentation (`/docs`, `/openapi.json`), and system health checks (`/health`) retain strict precedence over static mounts.

### 1.2 Bespoke HTML5 Canvas 2D Engine (No Heavy Charting Libraries)
- **Rationale:** External charting libraries (Chart.js, Plotly, D3) introduce heavy multi-megabyte bundles, complex lifecycle coupling, and canvas rendering overhead during sub-second SSE bursts.
- **Implementation:** PULSE implements a lightweight, 60-FPS native Canvas 2D pipeline:
  - **High-DPI Display Scaling:** Uses `window.devicePixelRatio` to eliminate blurriness on Retina and 4K screens.
  - **Wilson Confidence Band Envelope:** Renders a shaded continuous polygon bounded by $[L_{\text{low}}, L_{\text{high}}]$ propagated from the Wilson score interval of $p$.
  - **Dynamic Leverage Spline:** Plots continuous $\Delta L$ with glowing stroke joins.
  - **Escalation Inflection Markers:** Draws highlighted nodes whenever point leverage crosses the $\tau = 5.0\%$ threshold.
  - **Interactive Hover Tooltip:** Tracks the nearest point coordinate under the mouse cursor to display point context and exact numerical bounds.

### 1.3 Event-Driven SSE Controller & State Store
- **Native EventSource Consumer:** Consumes standard Server-Sent Events over HTTP via `/v1/matches/{match_id}/stream?speed_multiplier={speed}`.
- **Multi-Panel Reactive Dispatch:** Unpacks incoming `StreamPointEvent` payloads and synchronously updates all 5 visual panels in a single frame.
- **Stream Lifecycle Management:** Supports Play, Pause, Reset, speed switching, and graceful end-of-match handling without memory leaks.

### 1.4 Post-Match Tactical Intelligence & Modal Integration (ADR-014 — Phase 6.6)
- **Deterministic Analytics Grounding:** Queries `GET /v1/matches/{match_id}/report?format=json` to retrieve the fully aggregated post-match tactical evaluation computed in $< 200\text{ms}$ by `src/analytics/match_report.py`.
- **Interactive Glassmorphic Modal:** Opens a non-disruptive, backdrop-filtered modal dialog displaying 6 structured debrief sections:
  - **Executive Tactical Debrief:** Grounded 3-paragraph synthesis (via configured async LLM client: Groq Cloud free-tier `llama-3.1-8b-instant` / Anthropic, or deterministic raw-signal fallback).
  - **Key Match Indicators:** Grid displaying Total Points, Set Scores, Mean Leverage, and Peak Leverage Point.
  - **Top Pivotal Moments Table:** Exact $\Delta L$ ranking with point context and interactive "Seek" buttons jumping directly to specific points on the timeline.
  - **Pressure Resilience Breakdown:** Side-by-side player win rate comparison across Routine, Elevated, and Critical leverage tiers with empirical shift ($\Delta p$).
  - **Game-Theoretic Audit Cards:** Realized serve direction distributions vs Nash equilibrium ($x^*$) and returner bias ($\hat{y}$) with data sufficiency status.
  - **Export Suite:** One-click clipboard copy (`Copy Markdown`), raw data export (`Download JSON`), and browser print stylesheet (`@media print` for PDF generation).

---

## 2. Component Blueprint & Data Contracts

| Sub-Component | DOM IDs | Consumed Data Contract | Visual Interaction |
|---|---|---|---|
| **1. Scoreboard** | `#scoreboard`, `#score-sets-p1`, `#score-games-p1`, `#score-points-p1`, `#server-indicator-p1`, `#high-leverage-badge` | `StreamPointEvent.point_context`, `leverage_result.p_hat` | Live tennis score progression, server ball icon position, elevated leverage pulse badge |
| **2. Oscillogram** | `#oscillogram-container`, `#leverage-canvas`, `#canvas-tooltip`, `#legend-container` | `StreamPointEvent.leverage_result` ($\Delta L, L_{\text{low}}, L_{\text{high}}$) | 60 FPS real-time leverage timeline, Wilson 95% CI shaded polygon, hover tooltips |
| **3. Topology Inspector** | `#topology-inspector`, `#node-state-monitor`, `#node-pressure-diagnostic`, `#node-strategy-exploit`, `#node-tactical-output` | `StreamPointEvent.decision_log`, `pressure_result`, `exploit_result` | Glowing node execution cards, latency badges, Sufficiency Gate ($N \ge 10$) state |
| **4. Game Theory** | `#game-theory-panel`, `#payoff-grid`, `#bar-nash`, `#bar-bias`, `#exploit-callout` | `StreamPointEvent.exploit_result.payoff_matrix`, `delta` | 2×2 payoff matrix with best-response cell highlight, Nash vs Bias progress bars, +EV gain badge |
| **5. Tactical Feed** | `#tactical-feed`, `#tactical-headline`, `#tactical-narrative`, `#tactical-recommendation-list` | `StreamPointEvent.tactical_output.narrative`, `raw_payload` | Coach-readable strategic guidance, pressure shift diagnosis, serve direction advice |
| **6. Control Bar** | `#stream-controls`, `#match-select`, `#speed-select`, `#btn-play`, `#btn-pause`, `#btn-reset`, `#btn-match-report` | `GET /v1/matches`, `GET /v1/matches/{match_id}` | Match selector, speed radio group (0.5x, 1.0x, 2.0x, Instant), stream lifecycle buttons, report trigger |
| **7. Post-Match Modal** | `#modal-match-report`, `#report-executive-summary`, `#report-pivotal-points`, `#report-pressure-breakdown`, `#btn-copy-markdown`, `#btn-download-json` | `MatchReportResponse` (`GET /v1/matches/{id}/report`) | Full-screen glassmorphic report dialog, pivotal point seek actions, clipboard copy & JSON export |

---

## 3. Directory Layout & File Responsibilities

```text
src/
├── analytics/
│   ├── match_report.py  # Deterministic post-match analytics engine, pivotal points & debrief synthesis (Phase 6.6)
│   └── formatting.py    # Markdown report formatter extracted to ensure strict modularity under 1,000 lines (Phase 6.6)
├── api/
│   ├── main.py          # FastAPI app instance, static asset mounting (/static), and root UI delivery (GET /, GET /ui)
│   ├── schemas.py       # Pydantic v2 request/response wire schemas (StreamPointEvent, MatchReportResponse, MatchMetadataResponse)
│   ├── streaming.py     # SSE event generator, REST match catalogue, and GET /v1/matches/{id}/report routes
│   └── static/          # 100% self-contained presentation layer assets
│       ├── index.html   # Semantic HTML5 layout with all 7 sub-component containers, report modal & inline SVG icons
│       ├── style.css    # CSS Custom Properties, glassmorphism backdrop filters, responsive grid & print stylesheet
│       └── app.js       # Canvas 2D engine, SSE controller, reactive DOM updater, and match report modal manager
tests/
├── integration/
│   ├── test_match_report_api.py # Automated integration tests for report endpoints (JSON, Markdown, BO5, mock LLM, 404)
│   └── test_static_ui.py        # Automated integration tests validating static delivery, DOM IDs, and MIME types
└── unit/
    ├── test_match_report.py     # Unit test suite for Markov leverage aggregation, ranking, pressure, and game-theory audit
    └── test_api_main.py         # Unit test suite verifying route registrations and health checks
```

---

## 4. Verification & Validation Summary

- **Total Integration Tests:** 10 dedicated integration tests across `test_static_ui.py` (HTML delivery, DOM contracts, MIME headers, zero-CDN compliance, route precedence) and `test_match_report_api.py` (JSON wire contracts, Markdown serialization, BO5 scoring rules, LLM async debrief, 404 handling).
- **Full Test Suite:** 176/176 tests passing (100%) with 0 warnings.
- **Type Checking & Linting:** 0 Pyright errors, 0 Ruff errors.
- **File Size Ceiling:** All files in `src/` strictly satisfy the CI ceiling limit (<1,000 lines).
