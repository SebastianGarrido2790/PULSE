# Phase 6.5 — Implementation Plan & Decisions
**Interactive Presentation Layer (Tactical Cockpit)**

**Product:** PULSE | **Phase:** 6.5 of 7 | **Version:** 0.1.0 (Draft — Pending Approval) | **Date:** 2026-08-23  
**Status:** 🟡 Planning — no UI code written  
**Authority:** `technical_roadmap.md` (Phase 6.5), `prd.md` (FR-13, NFR Frontend Assets), `system_design.md` (ADR-013), `ui_assessment.md`  
**Approval required from:** Sebastian, before any implementation begins

---

## 0. How to Read This Document

Same conventions as every prior phase's decisions document:

- **Section 1** is the mandatory current-state audit. It drives Section 2.
- **Section 2** holds one entry per decision, tagged 🔴 **Decision required** or 🟢 **No input required** (recorded for completeness of the decision record).
- Sub-decisions are nested under the primary decision they branch from.
- **Section 3** provides the decision summary matrix.

---

## 1. Current State Audit

### 1.1 Phase 6.5 Deliverable Files

| File | Status | Notes |
|---|---|---|
| `src/api/static/index.html` | **Does not exist.** Phase 6.5 scope. | Semantic HTML5 single-page structure for the tactical cockpit dashboard. |
| `src/api/static/style.css` | **Does not exist.** Phase 6.5 scope. | Modern dark-mode, glassmorphism design system, responsive grid layout, dynamic node status indicators. |
| `src/api/static/app.js` | **Does not exist.** Phase 6.5 scope. | ES6 module managing SSE `EventSource` lifecycle, dynamic DOM updates, scoreboard state, leverage plotting, and game-theory payoff matrix rendering. |
| `src/api/main.py` | **Exists**, lacks static file mounting. | Needs `app.mount("/static", ...)` and explicit root/UI route handlers (`GET /`, `GET /ui`) to serve the tactical cockpit seamlessly alongside Swagger `/docs` and `/health`. |
| `tests/integration/test_static_ui.py` | **Does not exist.** Phase 6.5 scope. | Integration tests verifying static asset delivery, HTTP 200 responses, Content-Type headers (`text/html`, `text/javascript`, `text/css`), and SSE route compatibility. |

### 1.2 Upstream Dependencies (Stable & Verified)

- `src/api/main.py::app` — FastAPI application instance with lifespan loading compiled LangGraph on `app.state.graph` (Phase 6).
- `src/api/streaming.py` — `GET /v1/matches` (list available match IDs), `GET /v1/matches/{match_id}` (`MatchMetadataResponse`), `GET /v1/matches/{match_id}/stream` (SSE event stream emitting `StreamPointEvent` JSON lines).
- `src/api/schemas.py::StreamPointEvent` — validated Pydantic v2 event payload containing `point_context`, `leverage_result`, `pressure_result`, `exploit_result`, `decision_log`, and `tactical_output`.
- `src/simulator/replay.py::get_available_matches()` — scans `artifacts/validated_data/points.parquet` for valid match IDs.

### 1.3 Findings

**Finding A — Route Precedence & Root Mounting in FastAPI/Starlette:**  
Mounting `StaticFiles(directory="src/api/static", html=True)` directly at `/` can inadvertently mask or interfere with subsequent sub-routers or catch-all route handlers if not sequenced carefully. Explicitly mounting `/static` for assets combined with explicit `@app.get("/", response_class=HTMLResponse)` and `@app.get("/ui", response_class=HTMLResponse)` route handlers ensures unambiguous routing precedence, clean OpenAPI documentation, and explicit cache headers. → **D-3**.

**Finding B — Air-Gapped / Offline Reproducibility vs. External CDN Dependencies:**  
PULSE is designed to run completely offline from clean checkouts (`uv run api.main` / `docker compose up --build`). Relying on external CDN scripts (e.g. unpkg/cdnjs for charting or fonts) introduces network failure modes during offline evaluations, corporate firewall restrictions, or air-gapped demo environments. A standalone visualization approach (pure HTML5 Canvas 2D or vendored standalone JS) guarantees 100% offline resilience. → **D-2, D-6**.

**Finding C — Stream Playback Controls & Replay Speed Interactivity:**  
The backend `GET /v1/matches/{match_id}/stream` endpoint accepts `speed_multiplier` as a query parameter (from `0.0` for instant replay to `1.0`, `2.0`, etc.). The frontend must allow evaluators to select matches from `GET /v1/matches`, dynamically adjust replay speed, pause/resume streaming, and view instantaneous point-by-point telemetry without reloading the browser. → **D-4**.

---

## 2. Decisions

### D-1 🔴 Static Asset Architecture — Single Flat Directory vs. Modular Subdirectories

**Context:** Phase 6.5 introduces static web assets into `src/api/static/`. We must establish a clean, maintainable structure that complies with the repo's file organization conventions without adding build steps.

| Option | Description | Trade-off |
|---|---|---|
| **A — Clean Modular Structure (`src/api/static/`)** | `src/api/static/index.html`, `src/api/static/css/style.css`, `src/api/static/js/app.js` (or flat `src/api/static/` root with 3 dedicated files: `index.html`, `style.css`, `app.js`). | **Simplest and cleanest:** Clear separation of HTML structure, CSS design tokens, and JS event-handling logic; zero build steps; direct 1:1 mapping for FastAPI static mounting. |
| **B — Monolithic Inlined `index.html`** | All HTML, CSS in `<style>`, and JavaScript in `<script>` packed into a single `index.html`. | Eliminates extra HTTP asset requests, but creates an unwieldy, unmodular 600+ line file violating separation of concerns and making code review harder. |
| **C — Full Multi-Module JS Hierarchy** | Separate JS modules: `api.js`, `chart.js`, `state.js`, `scoreboard.js`, `topology.js`. | High modularity, but introduces multiple ES6 module imports across browser script tags for what is fundamentally a single-view event cockpit (~300 lines of JS). |

**Recommendation: Option A (Flat Dedicated Directory: `index.html`, `style.css`, `app.js`).** Keeps asset organization clean, maintainable, and directly inspectable without unnecessary nesting or monolithic entanglement.

---

### D-2 🔴 Data Visualization & Charting Engine — Pure HTML5 Canvas vs. Vendored/CDN Charting

**Context:** The tactical cockpit requires a real-time **Leverage & Momentum Oscillogram** plotting point-by-point leverage $\Delta L$, shaded Wilson confidence bands $[L_{\text{low}}, L_{\text{high}}]$, and the configured escalation threshold line ($\tau = 0.05$).

| Option | Description | Trade-off |
|---|---|---|
| **A — Pure Bespoke HTML5 Canvas 2D Engine (Zero External Dependencies)** | A lightweight, custom-built Canvas 2D rendering function in `app.js` (~100 lines) drawing the continuous leverage line, shaded Wilson CI polygon, threshold dash-line, and interactive point hover coordinates. | **100% offline & air-gapped:** 0 KB external library weight; 0 CDN dependencies; sub-millisecond 60 FPS animation loop; complete styling alignment with the dark glassmorphism theme; zero third-party breaking changes. |
| **B — External CDN-Loaded Chart.js (v4.x)** | Load `https://cdn.jsdelivr.net/npm/chart.js` via `<script>` tag in `index.html`. | Feature-rich out of the box (built-in tooltips/axes), but introduces an external internet dependency, breaking air-gapped demos and causing visual delays if CDN is slow or blocked. |
| **C — Vendored Local `chart.umd.js` in `src/api/static/vendor/`** | Commit a minified standalone build of Chart.js (~60 KB) into the repository. | Self-contained, but adds a binary/minified foreign JS bundle into source control, increasing repository bloat for a single line-chart requirement. |

**Recommendation: Option A (Pure Bespoke HTML5 Canvas 2D Engine).** It provides complete mathematical control over the Wilson confidence band polygon $[L_{\text{low}}, L_{\text{high}}]$ and leverage threshold markers with zero external scripts, zero CDN dependencies, and zero repository bloat.

---

### D-3 🔴 FastAPI Static Mount & Route Delivery Strategy (Resolves Finding A)

**Context:** FastAPI must serve the static frontend assets while preserving `/docs` (Swagger UI), `/openapi.json`, `/health`, and `/v1/matches/...`.

| Option | Description | Trade-off |
|---|---|---|
| **A — Dedicated `/static` Mount + Explicit `GET /` and `GET /ui` Route Handlers** | `app.mount("/static", StaticFiles(directory=static_dir), name="static")`<br>`@app.get("/", response_class=HTMLResponse)`<br>`@app.get("/ui", response_class=HTMLResponse)` returning `FileResponse(static_dir / "index.html")`. | **Explicit and unambiguous:** Guarantees standard API routes (`/health`, `/docs`, `/v1/...`) take absolute priority; exposes `/` and `/ui` as first-class endpoints in OpenAPI schemas; allows setting custom cache headers on HTML vs static assets. |
| **B — Catch-All Root StaticFiles Mount (`app.mount("/", StaticFiles(...), name="static")`)** | Mount `StaticFiles` directly at `/` with `html=True`. | Relies on Starlette route registration ordering; can create subtle edge-case routing collisions with sub-routes or 404 handlers. |

**Recommendation: Option A.** Explicit route handlers for `/` and `/ui` with a dedicated `/static` mount ensure predictable routing, full Swagger compatibility, and clean test assertions.

---

### D-4 🔴 Stream Consumption, Playback Controls & Connection Lifecycle (Resolves Finding C)

**Context:** The UI must manage SSE connections to `GET /v1/matches/{match_id}/stream`, allowing users to switch matches, adjust playback speed, and pause/resume streams.

| Option | Description | Trade-off |
|---|---|---|
| **A — Dynamic Browser `EventSource` with Live Parameter Reconnection** | When the user selects a match or clicks "Play", `app.js` opens `new EventSource('/v1/matches/' + matchId + '/stream?speed_multiplier=' + speed)`. On "Pause", it closes the connection; on "Resume", it resumes or restarts. Dynamic UI buffers point history locally. | **Direct, authentic streaming:** Directly exercises the SSE backend in real time; reflects true server-side latency and keep-alive heartbeats; zero complex client-side playback state machine. |
| **B — Batch Pre-fetch with Pure Client-Side Playback Simulation** | Client fetches all points via instant replay (`speed_multiplier=0`), stores them in a JS array, and plays them via `setInterval` in browser memory. | Enables instant scrubbing/rewinding, but misrepresents the streaming API by replacing live server push with client-side timer playback. |

**Recommendation: Option A.** Authentically demonstrates real-time server-pushed SSE streams, reflecting actual network events, heartbeat comments, and server-side graph execution.

---

### D-5 🟢 Design System Aesthetic & Dark-Mode Glassmorphism Standards

> [!NOTE]
> **Design Standard: Dark-Mode Tactical Glassmorphism.**  
> Sourced from the project's aesthetic guidelines:
> - **Palette:** Deep slate background (`#0B0F19`), surface card glass panels (`rgba(17, 24, 39, 0.75)` with `backdrop-filter: blur(12px)` and `border: 1px solid rgba(255, 255, 255, 0.08)`), vibrant emerald accents (`#10B981`) for active nodes/leverage baseline, cyan/blue (`#06B6D4`) for game theory, violet (`#8B5CF6`) for LLM synthesis, and crimson/amber (`#F59E0B` / `#EF4444`) for high-leverage escalations.
> - **Typography:** Clean system font stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`) with monospace tabular numbers for scores and leverage percentages.
> - **Responsiveness:** Desktop-first responsive CSS grid with collapsible side panels for 1080p+ presentation displays.

Recorded for completeness of the design record.

---

### D-6 🟢 Offline Font & Vector Icon Strategy (Resolves Finding B)

> [!NOTE]
> **Asset Standard: 100% Inline SVGs & System Fonts.**  
> All icons (Play, Pause, Reset, Tennis Ball, Activity/Graph, Brain/LLM, Server, Warning) are embedded as inline SVG elements within `index.html` and `app.js`. No external font or icon stylesheets (e.g. FontAwesome, Google Fonts) are fetched over the network, ensuring instant <10ms rendering and complete offline operation.

Recorded for completeness.

---

### D-7 🔴 Component Decomposition & Tactical Dashboard Blueprint

**Context:** The cockpit UI must visually present the 4 core mathematical and architectural pillars of PULSE simultaneously without clutter.

```
+----------------------------------------------------------------------------------------------------+
|  PULSE — Point-Level Understanding & Strategic Leverage Engine                   [Match Selector v] |
|  Status: Streaming (1.0x)  |  Score: Alcaraz vs Djokovic  |  Set 2: [4-4, 30-40] *Break Point*      |
+----------------------------------------------------------------------------------------------------+
|  [ 1. LIVE LEVERAGE & MOMENTUM TIMELINE (Canvas 2D)                                                ] |
|   Delta L (%)                                                                                      |
|   15% |            /\                                          -- Escalation Threshold (tau = 5%)  |
|   10% |           /  \      /\                                                                     |
|    5% |----------/----\----/--\---------------------------------                                   |
|    0% |___/\____/______\__/____\________ [Shaded Wilson 95% Confidence Band]                       |
|       Point 1 ......................................... Point 84 (Current: Delta L = 12.4% +/- 1.8%)|
+----------------------------------------------------------------------------------------------------+
|  [ 2. LANGGRAPH CONDITIONAL TOPOLOGY ]    |  [ 3. GAME-THEORETIC EXPLOIT (T-2) ]                   |
|  • StateMonitorNode:      🟢 ACTIVE (12ms) |  • Opponent: N. Djokovic                               |
|  • PressureDiagnosticNode:🟢 FIRED  (18ms) |  • Wide vs Body Serve Payoff Matrix: [2x2 Grid]        |
|    - Delta P: -4.2% (Shrinkage: 0.68)      |  • Nash Equilibrium: 54% Wide / 46% T                  |
|  • StrategyExploitNode:   🟢 FIRED  (25ms) |  • Observed Bias: 72% Wide (N = 28 >= 10 Sufficiency)  |
|    - Sufficiency Gate: PASSED (N=28 >= 10) |  • Recommended Exploit: Serve T (+6.8% EV Gain)        |
|  • TacticalOutputNode:    🟣 LLM SYNTHESIS |                                                        |
+----------------------------------------------------------------------------------------------------+
|  [ 4. COACH / BROADCAST TACTICAL FEED (Real-Time Advisory Card)                                    ] |
|  Headline: Critical Break Point — Exploit Opponent Wide-Serve Bias                                 |
|  Narrative: Leverage has surged to 12.4% (Set 2, 4-4, 30-40). Pressure model detects server       |
|             win-rate degradation of -4.2%. Returner shows statistically significant wide-coverage   |
|             bias. Exploit serve down the T yields +6.8% expected win probability.                  |
+----------------------------------------------------------------------------------------------------+
|  Controls: [Play / Pause]  [Speed: 0.5x | 1x | 2x | Max]  [Latency: 58ms]  [OTel Trace ID: #4f8a9]  |
+----------------------------------------------------------------------------------------------------+
```

| Sub-Component | Visual Elements & Data Sources |
|---|---|
| **1. Header & Live Scoreboard** | Current Match ID, Player Names, Surface badge, Set score boxes, Game score boxes, Current Point score (e.g. `30-40`), Server ball indicator `🎾`, High-Leverage badge. |
| **2. Leverage Oscillogram** | HTML5 Canvas 2D chart, $\Delta L$ line plot, Wilson 95% CI upper/lower bounds envelope, escalation threshold line ($\tau$), point cursor tooltip. |
| **3. LangGraph Topology** | 4-node pipeline cards (`StateMonitorNode`, `PressureDiagnosticNode`, `StrategyExploitNode`, `TacticalOutputNode`) with real-time status badges (`ACTIVE`, `FIRED`, `SUPPRESSED`, `INSUFFICIENT_DATA`), execution latency, and Sufficiency Gate badges. |
| **4. Game Theory Exploit** | 2x2 or 3x2 Payoff Matrix grid, Nash equilibrium serve mix bars, opponent returner observed bias bars, best-response exploit direction, EV gain $\delta$. |
| **5. Tactical Advisory Feed** | Headline banner, LLM narrative synthesis text, bulleted recommendations, advisory disclaimer tag. |
| **6. Stream Control Bar** | Match selector dropdown (`GET /v1/matches`), Speed multiplier radio/buttons (`0.5x`, `1.0x`, `2.0x`, `Instant`), Play/Pause/Reset buttons, Stream status indicator (`Connected`, `Streaming`, `Complete`, `Error`). |

**Recommendation: Approve Sub-Component Blueprint.**

---

### D-8 🔴 Automated Integration Testing Strategy for Static Assets

**Context:** We must ensure automated CI verification of the static frontend without introducing Node.js or browser driver dependencies (e.g. Playwright/Selenium).

| Option | Description | Trade-off |
|---|---|---|
| **A — FastAPI / HTTPX Integration & DOM Verification (`tests/integration/test_static_ui.py`)** | Automated integration tests using `httpx.AsyncClient` verifying:<br>1. `GET /` and `GET /ui` return HTTP 200 with `Content-Type: text/html; charset=utf-8`.<br>2. HTML body contains all required structural container IDs (`#leverage-canvas`, `#scoreboard`, `#topology-container`, `#payoff-grid`, `#tactical-feed`, `#match-select`).<br>3. `GET /static/style.css` and `GET /static/app.js` return HTTP 200 with correct MIME types (`text/css`, `text/javascript`).<br>4. Replay matches list endpoint (`GET /v1/matches`) returns valid non-empty match array. | **Fast, lean, and CI-native:** Executes in <150ms; runs in existing pytest suite; 0 external dependencies; rigorously verifies server-side asset delivery and contracts. |
| **B — Headless Browser Automation (Playwright / Selenium)** | Install Playwright browser binaries to run live browser UI tests. | Catches canvas pixel rendering, but adds >300 MB of browser binaries and heavy CI pipeline latency. |

**Recommendation: Option A (FastAPI / HTTPX Integration & DOM Verification).** Fully validates routing, asset delivery, DOM structure, and API contract alignment within milliseconds.

---

## 3. Reconciled Decision Summary Matrix

| ID | Title | Status | Recommended Choice |
|---|---|:---:|---|
| **D-1** | Static Asset Directory Structure | 🔴 Pending | **Option A** — Flat modular directory (`index.html`, `style.css`, `app.js`) in `src/api/static/` |
| **D-2** | Charting & Data Visualization Engine | 🔴 Pending | **Option A** — Bespoke HTML5 Canvas 2D engine (100% offline, zero dependencies) |
| **D-3** | FastAPI Static Mount & Route Delivery | 🔴 Pending | **Option A** — Dedicated `/static` mount + explicit `GET /` and `GET /ui` route handlers |
| **D-4** | Stream Consumption & Playback Controls | 🔴 Pending | **Option A** — Dynamic `EventSource` (SSE) with query parameter speed and connection controls |
| **D-5** | Design System & Dark-Mode Aesthetics | 🟢 Recorded | Dark-mode glassmorphism theme (`#0B0F19`, glass cards, glowing node accents) |
| **D-6** | Offline Font & Vector Icon Strategy | 🟢 Recorded | 100% inline SVGs and system font stack (zero external CDN requests) |
| **D-7** | Component Decomposition Blueprint | 🔴 Pending | 6 core sub-components: Scoreboard, Canvas Oscillogram, Topology, Game Theory, Coach Feed, Controls |
| **D-8** | Automated Testing Strategy | 🔴 Pending | **Option A** — FastAPI/HTTPX integration & DOM verification in `test_static_ui.py` |

---

**Before any implementation begins:** Explicit approval from Sebastian is required on decisions **D-1, D-2, D-3, D-4, D-7, and D-8**.
