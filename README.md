# PULSE — Point-Level Understanding & Strategic Leverage Engine

An event-driven tactical intelligence system that monitors tennis matches point-by-point, computes exact leverage via a closed-form Markov solver, and conditionally escalates to a pressure diagnostic and game-theoretic tactical exploit only when both the match state and available observation counts statistically justify it.

Designed for coaches, performance analysts, and broadcast teams as an advisory tactical signal — never as an autonomous decision-maker.

---

## 🚦 Project Status

| Phase | Description | Status |
| :--- | :--- | :---: |
| **Phase 0 — Planning** | ML Canvas, Project Charter, PRD, User Story, Technical Roadmap, System Design | ✅ Complete |
| **Phase 1 — Project Scaffolding** | Repository structure, `uv` toolchain, `params.yaml`, CI/CD, line ceiling gate | ✅ Complete |
| **Phase 2 — Data Layer & Core** | `PointRecord` schema, validation pipeline, closed-form Markov solver | ✅ Complete |
| **Phase 3 — Tier 1 ML** | Point-win classifier & pressure deviation empirical-Bayes shrinkage model | ✅ Complete |
| **Phase 4 — Agent Orchestration** | Event-driven LangGraph (State Monitor + conditional diagnostic/exploit nodes) | ✅ Complete |
| **Phase 5 — Game Theory Module** | Minimax Nash equilibrium, best-response return exploit & empirical-Bayes priors | ✅ Complete |
| **Phase 6 — API & Simulation** | FastAPI streaming API (SSE/WS), real-time match replay simulator & SQLite audit | ✅ Complete |
| **Phase 6.5 — Presentation Layer** | Embedded real-time Tactical Cockpit SPA (Canvas 2D, zero-CDN, glassmorphic UI) | ✅ Complete |
| **Phase 6.6 — Post-Match Analytics** | Deterministic leverage summary, pivotal point audit, pressure & game-theory report | ✅ Complete |
| **Phase 7 — Observability & CI/CD** | OpenTelemetry tracing spans, multi-stage Docker container & GitHub Actions | 🟡 Next Up |

---

## 🔑 Key Architecture & System Invariants

PULSE operates on four foundational architectural principles:

- **Ground-Truth Primacy:** The closed-form Markov solver provides mathematically exact leverage values. Deterministic mathematics is the ground truth; machine learning models only estimate inputs ($p_{\text{serve}}$ win probability).
- **The Sufficiency Gate:** Exploits and pressure diagnostics are confidence-gated by observation counts. If data is insufficient, signals are suppressed rather than emitting unsupported advice.
- **Advisory-Only Mandate:** PULSE provides high-precision intelligence to human analysts and coaches who make all final strategic decisions.
- **Conditional Graph Topology:** LangGraph workflow executes state monitoring continuously, while downstream diagnostic and exploit nodes fire conditionally based on threshold triggers.

---

## 🎾 Mathematical Foundations

For a conceptual deep dive into how Markov chains, leverage calculations, and game-theoretic equilibrium operate within tennis scoring dynamics, see:

📖 **[The Secret Math Hiding Inside Every Tennis Match](tennis_mathematical_elegance.md)**

---

## 🛠️ Stack & Technologies

- **Language:** Python 3.11+ (Strict typing with Pyright)
- **Dependency Management:** `uv`
- **Orchestration:** LangGraph (Conditional Event-Driven Graph)
- **Deterministic Core:** Closed-Form Markov Solver, Wilson Confidence Intervals, `scipy.optimize.linprog` (Game-Theoretic Equilibrium)
- **Analytics & Reporting:** Deterministic Post-Match Analytics Engine, Pivotal Point Extractor, Markdown & JSON Exporters
- **ML & Data:** scikit-learn (Point-Win Classifier), Empirical-Bayes Shrinkage (Pressure Estimator), MLflow, DVC
- **API & Streaming:** FastAPI (SSE / WebSockets), `aiosqlite`
- **Presentation Layer:** Embedded Dark-Mode Tactical Cockpit (Vanilla HTML5, CSS Grid, Canvas 2D, Zero CDN)
- **Quality & Evaluation:** Ruff, Pyright, DeepEval (Narrative Groundedness), Pytest

---

## 📂 Repository Structure

```text
.
├── src/
│   ├── analytics/      # Post-match aggregation, pivotal point extraction, & reporting
│   ├── api/            # FastAPI streaming endpoints & static asset delivery
│   │   ├── main.py     # FastAPI application, static mounts (/static), and UI entrypoint
│   │   ├── schemas.py  # Pydantic v2 request/response wire contracts
│   │   ├── streaming.py# SSE & WebSocket streaming route handlers
│   │   └── static/     # Embedded real-time Tactical Cockpit (HTML/CSS/JS)
│   ├── core/           # Deterministic Markov solver, game theory, & leverage uncertainty
│   ├── graph/          # LangGraph conditional orchestration nodes
│   ├── models/         # Tier 1 ML models (point-win classifier, pressure deviation)
│   ├── schemas/        # Pydantic v2 data contracts (PointRecord)
│   ├── simulator/      # Historical match replay simulator
│   ├── utils/          # Exception hierarchy, logger, SQLite persistence
│   └── config/         # Parameters & config loaders
├── scripts/
│   ├── check_file_size.py # CI line-count ceiling checker (max 1,000 lines/file)
│   └── build_payoff_matrices.py # Payoff matrix compilation DVC pipeline stage
├── tests/
│   ├── unit/           # Analytical correctness & module unit tests
│   ├── integration/    # Static UI delivery, SSE streaming, match report API, & graph tests
│   └── evals/          # DeepEval narrative groundedness checks
├── reports/
│   └── docs/           # Architecture, decisions, evaluations, references, & workflows
├── tennis_mathematical_elegance.md # Mathematical background documentation
├── params.yaml         # Centralized operational thresholds
├── dvc.yaml            # Data version control pipeline
└── pyproject.toml      # Project configuration & dependencies
```

---

## 🚀 Getting Started

### Prerequisites

Ensure Python 3.11+ and `uv` are installed.

```bash
# Clone the repository
git clone https://github.com/SebastianGarrido2790/PULSE.git
cd PULSE

# Install dependencies using uv
uv sync
```

### Running Commands

| Action | Command | Purpose |
| :--- | :--- | :--- |
| **One-Click Cockpit Launch** | `.\launch_app.bat` | Syncs env, verifies artifacts, opens browser, and starts FastAPI app |
| **Start Tactical Cockpit & API** | `uv run api.main` | Starts FastAPI service locally at `http://localhost:8000/` |
| **Replay Match in Terminal** | `uv run simulator.replay --match-id <id>` | Replays historical match point-by-point to simulate live feed |
| **Run Full Test Suite** | `uv run pytest` | Runs all 172 unit, integration, and groundedness eval tests |
| **Lint & Type Check** | `uv run ruff check . && uv run pyright` | Validates strict code style and 100% Pyright type safety |
| **Run Line Count Check** | `python scripts/check_file_size.py` | Enforces 1,000-line ceiling per file under `src/` |


---

## 📜 License & Data Attribution

- **Software License:** Licensed under the MIT License — see the [LICENSE.txt](LICENSE.txt) file for details.
- **Data Attribution:** Raw tennis match charting data sourced from [The Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject) by Jeff Sackmann, licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Used for non-commercial research and analytics demonstration.
