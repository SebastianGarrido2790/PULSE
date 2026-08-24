# Phase 6.5 — Interactive Presentation Layer Architecture

## Executive Summary

Phase 6.5 delivers the **Embedded Real-Time Tactical Cockpit** for PULSE — a single-page, dark-mode glassmorphic presentation layer served directly by FastAPI. Designed specifically for portfolio evaluators, recruitment managers, coaches, and performance analysts, the Tactical Cockpit provides an immediate visual lens into PULSE's event-driven intelligence without requiring external frontend build tooling, npm packages, or third-party CDN scripts.

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
│ 6. STREAM CONTROL BAR                                                           │
│    Match Selection (3,300+ matches) │ Speed (0.5x, 1.0x, 2.0x, Instant) │ Trace   │
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

---

## 2. Component Blueprint & Data Contracts

| Sub-Component | DOM IDs | Consumed Data Contract | Visual Interaction |
|---|---|---|---|
| **1. Scoreboard** | `#scoreboard`, `#score-sets-p1`, `#score-games-p1`, `#score-points-p1`, `#server-indicator-p1`, `#high-leverage-badge` | `StreamPointEvent.point_context`, `leverage_result.p_hat` | Live tennis score progression, server ball icon position, elevated leverage pulse badge |
| **2. Oscillogram** | `#oscillogram-container`, `#leverage-canvas`, `#canvas-tooltip`, `#legend-container` | `StreamPointEvent.leverage_result` ($\Delta L, L_{\text{low}}, L_{\text{high}}$) | 60 FPS real-time leverage timeline, Wilson 95% CI shaded polygon, hover tooltips |
| **3. Topology Inspector** | `#topology-inspector`, `#node-state-monitor`, `#node-pressure-diagnostic`, `#node-strategy-exploit`, `#node-tactical-output` | `StreamPointEvent.decision_log`, `pressure_result`, `exploit_result` | Glowing node execution cards, latency badges, Sufficiency Gate ($N \ge 10$) state |
| **4. Game Theory** | `#game-theory-panel`, `#payoff-grid`, `#bar-nash`, `#bar-bias`, `#exploit-callout` | `StreamPointEvent.exploit_result.payoff_matrix`, `delta` | 2×2 payoff matrix with best-response cell highlight, Nash vs Bias progress bars, +EV gain badge |
| **5. Tactical Feed** | `#tactical-feed`, `#tactical-headline`, `#tactical-narrative`, `#tactical-recommendation-list` | `StreamPointEvent.tactical_output.narrative`, `raw_payload` | Coach-readable strategic guidance, pressure shift diagnosis, serve direction advice |
| **6. Control Bar** | `#stream-controls`, `#match-select`, `#speed-select`, `#btn-play`, `#btn-pause`, `#btn-reset`, `#stream-status-badge` | `GET /v1/matches`, `GET /v1/matches/{match_id}` | Match selector, speed radio group (0.5x, 1.0x, 2.0x, Instant), stream lifecycle buttons |

---

## 3. Directory Layout & File Responsibilities

```text
src/api/
├── main.py              # FastAPI app instance, static asset mounting (/static), and root UI delivery (GET /, GET /ui)
├── schemas.py           # Pydantic v2 request/response wire schemas (StreamPointEvent, MatchMetadataResponse)
├── streaming.py         # SSE event generator and REST match catalogue endpoints
└── static/              # 100% self-contained presentation layer assets
    ├── index.html       # Semantic HTML5 layout with all 6 sub-component containers & inline SVG vector icons
    ├── style.css        # CSS Custom Properties, glassmorphism backdrop filters, and responsive CSS Grid
    └── app.js           # Canvas 2D rendering engine, SSE EventSource consumer, and reactive DOM controller
tests/
├── integration/
│   └── test_static_ui.py  # Automated integration test suite validating static delivery, DOM IDs, and MIME types
└── unit/
    └── test_api_main.py   # Unit test suite verifying route registrations and health checks
```

---

## 4. Verification & Validation Summary

- **Total Integration Tests:** 5 dedicated tests in `test_static_ui.py` covering HTML delivery, DOM contract validation, MIME headers, zero-CDN compliance, and route precedence.
- **Full Test Suite:** 152/152 tests passing (100%) with 0 warnings.
- **Type Checking & Linting:** 0 Pyright errors, 0 Ruff errors.
- **File Size Ceiling:** All files in `src/` strictly satisfy the CI ceiling limit (<1,000 lines).
