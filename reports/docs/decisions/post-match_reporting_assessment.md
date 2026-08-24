# Post Match Reporting & Tactical Analysis Feature

To implement a post-match reporting and tactical analysis feature in **PULSE**, we must assess how it aligns with the project's core invariants, existing architecture, and user personas.

---

## 1. Context & Architectural Assessment

In the existing architecture:

1. **Deterministic Core & ML Invariants:** During a match replay, PULSE computes point-level Markov leverage ($\Delta L$), Wilson confidence bounds $[L_{\text{low}}, L_{\text{high}}]$, Empirical-Bayes pressure shifts ($\Delta p$), and minimax game-theoretic exploit margins ($\delta$).
2. **Session Persistence:** [`src/utils/persistence.py`](../../../src/utils/persistence.py) asynchronously stores all `decision_logs` and `tactical_outputs` in SQLite (`artifacts/pulse_session.db`).
3. **The Reporting Gap:** Currently, once a match stream concludes (`Stream Ended`), the results are displayed only point-by-point. There is no consolidated post-match intelligence artifact that aggregates:
   - **Pivotal Points Audit:** Ranking the top 5 highest-leverage inflection moments of the match where the outcome swung most violently.
   - **Pressure Resilience Analysis:** Quantifying whether either player's realized win rate significantly elevated or deteriorated under pressure vs their routine baseline.
   - **Game-Theoretic Strategy Evaluation:** Comparing actual serve distributions against the computed Nash equilibrium and evaluating how effectively returner anticipation bias was exploited.
   - **Coach-Ready Executive Brief:** A structured, numbers-grounded narrative summary ready for export.

---

## 2. Comparative Planning: Proposed Implementation Options

In accordance with our project planning standards, here are **three viable architectural approaches** for adding match reporting:

### 🌟 Option A: Embedded In-Engine Report Generator & Interactive Cockpit Modal (Recommended)

- **Backend Implementation:**
  - Create a deterministic post-match aggregation module (`src/analytics/match_report.py`) that computes match-wide metrics (Leverage swing distribution, pressure breakdown per bucket, exploit execution yield).
  - Register `GET /v1/matches/{match_id}/report` in [`src/api/main.py`](../../../src/api/main.py) returning a typed `MatchReportResponse` schema.
  - Use `TacticalOutputNode` for an LLM-synthesized post-match debrief that is 100% numerically grounded.
- **Frontend / Cockpit UX:**
  - Add a **"Generate Match Report"** action button in the Tactical Cockpit (activated when a replay reaches its final point or upon request).
  - Opens a dark-mode glassmorphic modal displaying the executive summary, pivotal points table, pressure breakdown, and game-theoretic audit, with a one-click **"Export Markdown / JSON"** button.
- **Trade-Offs:**
  - _Pros:_ Fully self-contained within the zero-dependency FastAPI + Vanilla HTML/CSS stack (ADR-013); delivers immediate value to analysts and evaluators inside the browser.
  - _Cons:_ Requires minor extensions to both backend schemas and `src/api/static/` DOM/CSS.

---

### Option B: Offline CLI & Batch Pipeline Generator (`src/simulator/report.py`)

- **Backend Implementation:**
  - Implement a standalone CLI tool `python -m src.simulator.report --match-id <id>` that ingests match records, runs the analytical pipeline, and exports formatted Markdown/JSON reports to `reports/matches/<match_id>_report.md`.
  - Optionally integrate as a DVC stage (`evaluate_match_reports`).
- **Trade-Offs:**
  - _Pros:_ Fully decoupled from the web UI; ideal for batch benchmarking across thousands of historical matches.
  - _Cons:_ Lacks direct visual integration in the Tactical Cockpit; requires manual terminal execution.

---

### Option C: Terminal SSE Summary Event + Live Cockpit Tab

- **Backend Implementation:**
  - Extend the streaming generator ([`src/simulator/replay.py`](../../../src/simulator/replay.py)) to emit a final `event_type: "match_summary"` frame containing the full post-match analysis upon reaching the terminal match point.
  - The Cockpit automatically transitions from the live oscillogram into a dedicated **"Post-Match Analysis"** view.
- **Trade-Offs:**
  - _Pros:_ Completely automated transition at match completion.
  - _Cons:_ Increases final SSE payload size; less flexible if a user wants to generate a report on-demand for an arbitrary match without streaming every point.

---

## 3. Recommended Structure of the Post-Match Report

Regardless of the delivery mechanism, the generated report would be structured as follows:

```markdown
# PULSE Match Intelligence Report: [Player 1] vs [Player 2]

- Surface: [HARD/CLAY/GRASS] | Score: [e.g. 6-4, 3-6, 6-2] | Total Points: [207]

### 1. Executive Tactical Summary (LLM-Grounded Synthesis)

### 2. Pivotal Moments Audit (Top-5 Highest Leverage Inflection Points)

### 3. Pressure Resilience Diagnostic (Routine vs Critical Leverage Win Rates)

### 4. Game-Theoretic Serve/Return Execution (Nash Mix vs Observed Exploit Margin)

### 5. Sufficiency & Statistical Data Disclosure
```

---

## Next Steps

Select which approach you prefer to proceed with:

1. **Option A (Recommended):** In-Engine API endpoint (`GET /v1/matches/{id}/report`) + Embedded Cockpit Modal with Markdown/JSON export.
2. **Option B:** Standalone CLI tool (`src/simulator/report.py`) + DVC pipeline integration.
3. **Option C:** Streaming terminal summary event + automatic UI transition.

Once you confirm your choice, we will draft the formal implementation plan!
