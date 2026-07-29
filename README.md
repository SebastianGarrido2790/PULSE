# PULSE — Point-Level Understanding & Strategic Leverage Engine

An event-driven tactical intelligence system that monitors tennis matches point-by-point, computes exact leverage via a closed-form Markov solver, and conditionally escalates to a pressure diagnostic and game-theoretic tactical exploit only when both the match state and available observation counts statistically justify it.

Designed for coaches, performance analysts, and broadcast teams as an advisory tactical signal — never as an autonomous decision-maker.

---

## 🔑 Key Architecture & System Invariants

PULSE operates on four foundational architectural principles:

- **Ground-Truth Primacy:** The closed-form Markov solver provides mathematically exact leverage values. Deterministic mathematics is the ground truth; machine learning models only estimate inputs ($p_{\text{serve}}$ win probability).
- **The Sufficiency Gate:** Exploits and pressure diagnostics are confidence-gated by observation counts. If data is insufficient, signals are suppressed rather than emitting un-supported advice.
- **Advisory-Only Mandate:** PULSE provides high-precision intelligence to human analysts and coaches who make all final strategic decisions.
- **Conditional Graph Topology:** LangGraph workflow executes state monitoring continuously, while downstream diagnostic and exploit nodes fire conditionally based on threshold triggers.

---

## 🛠️ Stack & Technologies

- **Language:** Python 3.11+ (Strict typing with Pyright)
- **Dependency Management:** `uv`
- **Orchestration:** LangGraph (Conditional Event-Driven Graph)
- **Deterministic Core:** Closed-Form Markov Solver, Wilson Confidence Intervals, `scipy.optimize.linprog` (Game-Theoretic Equilibrium)
- **ML & Data:** scikit-learn (Point-Win Classifier), Empirical-Bayes Shrinkage (Pressure Estimator), MLflow, DVC
- **API & Streaming:** FastAPI (SSE / WebSockets)
- **Quality & Evaluation:** Ruff, Pyright, DeepEval (Narrative Groundedness), Pytest

---

## 📂 Repository Structure

```text
.
├── src/
│   ├── api/            # FastAPI streaming endpoints
│   ├── core/           # Deterministic Markov solver, game theory, & leverage uncertainty
│   ├── graph/          # LangGraph conditional orchestration nodes
│   ├── models/         # Tier 1 ML models (point-win classifier, pressure deviation)
│   ├── schemas/        # Pydantic v2 data contracts (PointRecord)
│   ├── simulator/      # Historical match replay simulator
│   ├── utils/          # Exception hierarchy, logger, sanitization
│   └── config/         # Parameters & config loaders
├── scripts/
│   └── check_file_size.py # CI line-count ceiling checker (max 1,000 lines/file)
├── tests/
│   ├── unit/           # Markov solver analytical correctness tests
│   ├── integration/    # LangGraph conditional topology tests
│   └── evals/          # DeepEval narrative groundedness checks
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

| Action | Command |
| :--- | :--- |
| **Run Line Count Check** | `python scripts/check_file_size.py` |
| **Run Test Suite** | `pytest` |
| **Lint & Type Check** | `ruff check .` |
| **Start Streaming API** | `fastapi dev src/api/main.py` |

---

## 📜 License

Licensed under the MIT License — see the [LICENSE.txt](file:///c:/Users/sebas/Desktop/PULSE/LICENSE.txt) file for details.
