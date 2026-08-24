# Phase 6.5 — Execution Workflow

**Interactive Presentation Layer (Tactical Cockpit) — Ordered Implementation Steps**

**Product:** PULSE | **Phase:** 6.5 of 7 | **Version:** 1.0.0 | **Date:** 2026-08-23  
**Status:** 🟡 Ready for Implementation — All 8 Stages (0–7) Defined  
**Authority:** `phase6_5_implementation_plan_and_decisions.md` (Approved D-1–D-8), `prd.md` (FR-13, NFR Frontend Assets), `system_design.md` (ADR-013)  
**Scope of this document:** Sequencing and quality gating only; no code changes.

---

## How to Read This

8 stages (0–7), strictly ordered. Steps numbered continuously (1–28) so any step is unambiguously referenceable. Each step is tagged with the approved decision(s) it implements. **A Gate closes every stage — nothing in the next stage starts until its gate passes.**

```
Stage 0 (Pre-Flight) ──► Stage 1 (HTML5 Skeleton) ──► Stage 2 (CSS Design Tokens)
                                                                 │
                                                                 ▼
Stage 5 (FastAPI Mount) ◄── Stage 4 (SSE Controller) ◄── Stage 3 (Canvas Engine)
         │
         ▼
Stage 6 (Integration Tests) ──► Stage 7 (E2E Verification & Quality Gates)
```

---

## Stage 0 — Pre-Implementation Verification & Workspace Pre-Flight ✅

1. Verify that `src/api/static/` does not exist yet and that no partial UI code is present in the workspace.
2. Confirm upstream API dependencies are healthy: `src/api/main.py::app`, `src/api/streaming.py` (`GET /v1/matches`, `GET /v1/matches/{match_id}`, `GET /v1/matches/{match_id}/stream`), and `src/simulator/replay.py::get_available_matches()`.
3. Verify that `httpx` and `fastapi.staticfiles.StaticFiles` are installed and available in the `uv` environment.
4. Run baseline test suite (`uv run pytest`) to confirm all 146 existing tests pass with 0 warnings before touching any file.

**Gate 0:** Workspace clean; upstream API routes verified; 146/146 baseline tests passing. ✅ **PASSED (2026-08-23)**


---

## Stage 1 — HTML5 Semantic Layout & Sub-Component Skeleton (`src/api/static/index.html`) ✅

5. Create `src/api/static/` directory. **[D-1]**
6. Build semantic HTML5 single-page structure in `src/api/static/index.html` containing the 6 core sub-components: **[D-1, D-5, D-7]**
   - **Sub-Component 1 (Scoreboard Header):** `#scoreboard`, `#match-title`, `#match-surface-badge`, `#server-indicator`, `#score-sets`, `#score-games`, `#score-points`, `#high-leverage-badge`.
   - **Sub-Component 2 (Leverage Oscillogram):** `#oscillogram-container`, `<canvas id="leverage-canvas">`, `#canvas-tooltip`, `#legend-container` ($\Delta L$, Wilson 95% CI, $\tau=5\%$ threshold).
   - **Sub-Component 3 (LangGraph Topology Inspector):** `#topology-inspector`, 4 node execution cards (`#node-state-monitor`, `#node-pressure-diagnostic`, `#node-strategy-exploit`, `#node-tactical-output`) with dynamic status badges (`ACTIVE`, `FIRED`, `SUPPRESSED`, `INSUFFICIENT_DATA`) and latency indicators.
   - **Sub-Component 4 (Game-Theoretic Exploit Panel):** `#game-theory-panel`, `#payoff-grid` (2x2 matrix), `#nash-distribution-bars`, `#observed-bias-bars`, `#exploit-callout` (+EV gain badge).
   - **Sub-Component 5 (Tactical Advisory Feed):** `#tactical-feed`, `#tactical-headline`, `#tactical-narrative`, `#tactical-recommendation-list`, `#advisory-disclaimer`.
   - **Sub-Component 6 (Stream Control Bar):** `#stream-controls`, `#match-select` dropdown, `#speed-select` radio group (`0.5x`, `1.0x`, `2.0x`, `Instant`), `#btn-play`, `#btn-pause`, `#btn-reset`, `#stream-status-badge`, `#otel-trace-badge`.
7. Embed 100% inline SVG vector icons for Play, Pause, Reset, Tennis Ball `🎾`, Activity/Graph, Brain/LLM, Server, and Alert icons. **[D-6]**
8. Link stylesheet `<link rel="stylesheet" href="/static/style.css">` and module script `<script type="module" src="/static/app.js"></script>` with zero external CDN dependencies. **[D-1, D-6]**

**Gate 1:** `src/api/static/index.html` created; all structural element IDs from the approved blueprint present; 0 external `<link>` or `<script>` tags. ✅ **PASSED (2026-08-23)**


---

## Stage 2 — Design System Tokens & Dark-Mode Glassmorphism Styling (`src/api/static/style.css`) ✅

9. Create `src/api/static/style.css` defining CSS Custom Properties and design tokens: **[D-1, D-5]**
   - Palette tokens: `--bg-base: #0B0F19`, `--bg-surface: rgba(17, 24, 39, 0.75)`, `--border-glass: rgba(255, 255, 255, 0.08)`, `--accent-emerald: #10B981`, `--accent-cyan: #06B6D4`, `--accent-violet: #8B5CF6`, `--accent-amber: #F59E0B`, `--accent-crimson: #EF4444`, `--text-main: #F9FAFB`, `--text-muted: #9CA3AF`.
   - Font stack: `--font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` and `--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`.
10. Implement responsive desktop-first CSS Grid layout (`grid-template-areas: "header header" "oscillogram topology" "game-theory tactical" "controls controls"`) with glassmorphism backdrop filters (`backdrop-filter: blur(12px)`). **[D-5, D-7]**
11. Style tabular typography for scoreboard digits and leverage percentages (`font-feature-settings: "tnum"`). **[D-5]**
12. Define dynamic node execution animations and status pill classes (`.status-active`, `.status-fired`, `.status-suppressed`, `.status-insufficient-data`) with glowing border transitions. **[D-5, D-7]**
13. Style the 2x2 Payoff Matrix grid and probability distribution progress bars with high-contrast tactical accents. **[D-5, D-7]**

**Gate 2:** `src/api/static/style.css` created; glassmorphism styles and grid layouts complete; 0 external `@import` rules; clean token hierarchy. ✅ **PASSED (2026-08-23)**


---

## Stage 3 — Bespoke HTML5 Canvas 2D Leverage & Confidence Band Engine (`src/api/static/app.js` — Part 1) ✅

14. Implement Canvas 2D rendering pipeline in `src/api/static/app.js`: **[D-1, D-2, D-7]**
    - High-DPI screen scaling via `window.devicePixelRatio` to ensure sharp rendering on Retina/4K screens.
    - Coordinate transformation mapping point indices to X-axis and leverage values ($\Delta L \in [0.0, 0.30]$) to Y-axis.
    - Shaded Wilson 95% confidence interval polygon (`ctx.fillStyle = "rgba(16, 185, 129, 0.15)"`) bounded between $L_{\text{low}}$ and $L_{\text{high}}$.
    - Continuous $\Delta L$ leverage spline/line plot (`ctx.strokeStyle = "#10B981"`).
    - Escalation threshold reference line at $\tau = 0.05$ (`ctx.setLineDash([4, 4])`, `#F59E0B`).
    - High-leverage inflection point markers (crimson/amber glowing dots for points where leverage crossed threshold).
15. Implement interactive canvas hover/cursor overlay tracking the nearest point index and rendering a floating tooltip with point score, server name, exact $\Delta L$, and Wilson bounds $[L_{\text{low}}, L_{\text{high}}]$. **[D-2]**

**Gate 3:** Canvas 2D rendering functions complete and verified with synthetic sample point arrays; coordinate transforms and Wilson envelope polygon rendering verified. ✅ **PASSED (2026-08-23)**


---

## Stage 4 — SSE Event Consumption, Reactive State Store & UI Controller (`src/api/static/app.js` — Part 2) ✅

16. Implement match initialization controller: **[D-4, D-7]**
    - `async function initMatchList()`: fetches `GET /v1/matches`, populates `#match-select` dropdown with available match IDs, and selects default match.
    - `async function loadMatchMetadata(matchId)`: fetches `GET /v1/matches/{match_id}`, updating player names, tournament/surface badge, and total point count.
17. Implement native browser `EventSource` lifecycle manager: **[D-4]**
    - `startStream(matchId, speedMultiplier)`: creates `new EventSource('/v1/matches/' + matchId + '/stream?speed_multiplier=' + speedMultiplier)`.
    - `pauseStream()`: closes `EventSource` instance, sets status badge to `Paused`.
    - `resetStream()`: clears local points history buffer, resets Canvas and Scoreboard, and restarts stream from point 0.
18. Wire incoming `StreamPointEvent` dispatch handler updating all DOM sub-components reactively: **[D-4, D-7]**
    - **Scoreboard:** Set/Game/Point scores, server tennis ball icon position, server-is-p1 indicator.
    - **Oscillogram:** Append point $[L_{\text{low}}, \Delta L, L_{\text{high}}]$, request Canvas redraw.
    - **Topology:** Update node badges (`ACTIVE`, `FIRED`, `SUPPRESSED`), display node execution latencies from decision logs, and toggle Sufficiency Gate badge ($N \ge 10$).
    - **Game Theory:** Render 2x2 matrix values, update Nash equilibrium vs observed returner bias bars, and highlight best-response exploit direction + EV gain.
    - **Tactical Feed:** Render headline, LLM narrative synthesis, and actionable recommendations.
19. Implement connection error handling and stream completion: catch stream close/error events, display completion toast, and interleave `: keep-alive` comment silence handling. **[D-4]**

**Gate 4:** `src/api/static/app.js` fully implemented; 100% wire-compatible with `StreamPointEvent` Pydantic contract; playback controls and reactive UI updates verified. ✅ **PASSED (2026-08-23)**


---

## Stage 5 — FastAPI Static Asset Mounting & Route Delivery (`src/api/main.py`) ✅

20. Update `src/api/main.py` with static asset delivery: **[D-3, ADR-013]**
    - Import `StaticFiles` from `fastapi.staticfiles` and `FileResponse, HTMLResponse` from `fastapi.responses`.
    - Locate static directory: `STATIC_DIR = Path(__file__).resolve().parent / "static"`.
    - Mount `/static`: `app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")`.
    - Register explicit root routes:
      ```python
      @app.get("/", response_class=HTMLResponse, tags=["UI"], summary="Tactical Cockpit Dashboard")
      async def serve_root_ui() -> FileResponse:
          return FileResponse(STATIC_DIR / "index.html")

      @app.get("/ui", response_class=HTMLResponse, tags=["UI"], summary="Tactical Cockpit Dashboard (Alias)")
      async def serve_ui_alias() -> FileResponse:
          return FileResponse(STATIC_DIR / "index.html")
      ```
21. Verify OpenAPI routes: ensure `/docs`, `/openapi.json`, and `/health` retain highest route precedence. **[D-3]**

**Gate 5:** `uv run api.main` launches cleanly; `GET /` and `GET /ui` return the HTML dashboard; `/static/style.css` and `/static/app.js` resolve with HTTP 200; `/health` returns healthy. ✅ **PASSED (2026-08-24)**


---

## Stage 6 — Automated Integration & DOM Contract Test Suite (`tests/integration/test_static_ui.py`) ✅

22. Create `tests/integration/test_static_ui.py` using `httpx.AsyncClient` with `ASGITransport(app=app)`. **[D-8]**
23. Implement integration test cases: **[D-8]**
    - `test_root_and_ui_endpoints_serve_html`: Asserts `GET /` and `GET /ui` return HTTP 200 with `Content-Type: text/html; charset=utf-8`.
    - `test_html_contains_required_cockpit_dom_contracts`: Asserts HTML body contains all blueprint container IDs (`#leverage-canvas`, `#scoreboard`, `#topology-inspector`, `#payoff-grid`, `#tactical-feed`, `#match-select`, `#stream-controls`).
    - `test_static_assets_serve_correct_mime_types`: Asserts `GET /static/style.css` returns `text/css` and `GET /static/app.js` returns `text/javascript` (or `application/javascript`).
    - `test_match_preflight_and_stream_route_availability`: Asserts `GET /v1/matches` returns non-empty list and `GET /v1/matches/{match_id}/stream` endpoint is accessible.
24. Update existing unit test `tests/unit/test_api_main.py` to assert new static routes and UI endpoints are registered.

**Gate 6:** `pytest tests/integration/test_static_ui.py` passes 100% in <200ms; all route and DOM contract assertions green. ✅ **PASSED (2026-08-24)**


---

## Stage 7 — End-to-End Visual Verification & Quality Gate Audit ✅

25. Execute full test suite: `uv run pytest` (confirming all unit, integration, and eval tests pass with 0 warnings).
26. Run strict linter and type-checking: `uv run ruff check .` and `uv run pyright`.
27. Run file size ceiling check: `python scripts/check_file_size.py` (confirm all files in `src/` remain strictly <1,000 lines).
28. Run historical match replay smoke test: execute `uv run python -m src.simulator.replay --match-id <id> --speed-multiplier 0` and verify real-time stream processing end-to-end.

**Gate 7:** All quality gates pass (pytest 100%, pyright 0 errors, ruff clean, file size <1,000 lines); Phase 6.5 complete and ready for Phase 7 CI/CD Dockerization. ✅ **PASSED (2026-08-24)**

---

## Reconciled Stage Gate Summary

| Stage | Focus Area | Closing Gate Condition | Status |
|:---:|---|---|:---:|
| **Stage 0** | Pre-Flight Audit | Workspace clean, baseline tests (146/146) green | 🟢 **Closed & Passed** |
| **Stage 1** | HTML5 Skeleton | `src/api/static/index.html` with all 6 sub-component IDs, 0 external scripts | 🟢 **Closed & Passed** |
| **Stage 2** | CSS Design System | `src/api/static/style.css` dark-mode glassmorphism styling complete | 🟢 **Closed & Passed** |
| **Stage 3** | Canvas 2D Engine | Bespoke leverage & Wilson CI rendering engine implemented in `app.js` | 🟢 **Closed & Passed** |
| **Stage 4** | SSE UI Controller | Native `EventSource` consumer and reactive DOM updater implemented | 🟢 **Closed & Passed** |
| **Stage 5** | FastAPI Route Mount | `app.mount("/static", ...)` and explicit `GET /`, `GET /ui` handlers in `main.py` | 🟢 **Closed & Passed** |
| **Stage 6** | Integration Tests | `test_static_ui.py` passes all asset, MIME, and DOM contract assertions | 🟢 **Closed & Passed** |
| **Stage 7** | Quality Gate Audit | Full suite green (`pytest`, `pyright`, `ruff`, `check_file_size.py`) | 🟢 **Closed & Passed** |



---

**Execution Rule:** Do not begin any stage until the preceding stage's gate has fully passed.
