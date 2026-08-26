# ADR: LLM Client Architecture — Direct Vendor SDKs vs. LangChain Chat Wrappers

## Status

**Decided & Approved** (Option A: Direct SDKs — `groq` & `anthropic`).

---

## Context & Problem Statement

In Phase 4 and Phase 6.6, PULSE introduced LLM-based narrative synthesis for two specific presentation tasks:

1. **Live Escalated Point Phrasing (`TacticalOutputNode`)**: Translating pre-computed leverage, pressure deviations, and exploit advantages into 1–2 coach-readable sentences.
2. **Post-Match Executive Debriefing (`src/analytics/match_report.py`)**: Synthesizing match-wide aggregate metrics into a 3-paragraph summary.

We evaluated whether to use **Direct Vendor SDKs** (`groq.AsyncGroq`, `anthropic.AsyncAnthropic`) or **LangChain Chat Model Wrappers** (`langchain-groq`, `langchain-anthropic`, `init_chat_model`).

---

## Comparative Evaluation

| Criterion                          | Direct SDKs (`groq`, `anthropic`) — **CURRENTLY IN USE**                                                                                                                                      | LangChain (`ChatGroq`, `ChatAnthropic`, `langchain-core`)                                                                                                                      |
| :--------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Architectural Fit**              | **Optimal**: PULSE is a deterministic mathematical engine. The LLM has only one narrow task: phrasing pre-computed signals into 1–2 sentences without tool-calling or multi-turn agent loops. | **Over-engineered**: LangChain abstractions (prompt templates, output parsers, message chains) add unnecessary complexity where simple f-strings and direct API calls suffice. |
| **Latency Overhead**               | **Minimal (~0ms wrapper overhead)**: Directly executes async HTTP requests on the client.                                                                                                     | **Noticeable (+20–50ms overhead)**: Serializes through `BaseMessage`, `AIMessage`, callback managers, and Pydantic validation chains.                                          |
| **Dependency Footprint**           | **Lightweight**: Just `groq` and `anthropic`.                                                                                                                                                 | **Heavy**: Requires `langchain`, `langchain-core`, `langchain-groq`, `langchain-anthropic`, `langsmith`, `tenacity`, etc.                                                      |
| **Maintenance & Stability**        | **High**: Vendor SDKs adhere to standard semver and rarely break basic chat completion APIs.                                                                                                  | **Moderate**: LangChain frequently refactors imports, schemas, and wrappers across minor versions (`0.1` $\to$ `0.2` $\to$ `0.3`).                                             |
| **Deterministic Fallback Control** | **Explicit & Bulletproof**: A clean `try/except` immediately triggers raw-signal passthrough if the API key is missing or the call times out.                                                 | **Complex**: Requires disabling internal retries, fallbacks, and tracer hooks to prevent latency spikes during match streaming.                                                |

---

## Decision Drivers & Rationale

1. **Alignment with Core Philosophy**:
   > _Deterministic math is the ground truth; the agent is a thin layer on top of it. PULSE inverts the usual ratio — most of the system's 'intelligence' is exact probability theory and game theory, not model inference or LLM reasoning._
2. **LangGraph Handles Orchestration**: LangGraph (`src/graph/pulse_graph.py`) manages conditional edges, routing, and state transitions. LLMs never make routing decisions or execute tool calls dynamically.
3. **Strict Latency Budget (<5s per triggered node, <1s per point overall)**: Direct SDKs provide predictable, ultra-low-overhead asynchronous I/O without extra abstraction layers.
4. **Deterministic Resilience**: If an API key is missing or an outage occurs, `src/graph/llm_client.py` and `src/analytics/match_report.py` catch the error in-place and immediately return deterministic structured payloads without failing or stalling the live replay stream.

---

## Why PULSE Inverts the Standard AI Stack

1. **LangGraph handles the graph**: We already use `LangGraph` (`src/graph/pulse_graph.py`) to manage conditional edges and state transitions between nodes.
2. **No LLM Tool-Calling or Agentic Loops**: The LLM does not perform arithmetic, lookup tables, or make tool decisions — all inputs to `TacticalOutputNode` and post-match debriefs are pre-computed by deterministic Python solvers.
3. **Sub-Second Latency Budget**: Direct SDKs guarantee the fastest round-trip possible during live stream playback.

---

## Approved Implementation

- **Direct Async Wrappers**: Implemented in [`src/graph/llm_client.py`](../../../src/graph/llm_client.py) using `groq.AsyncGroq` and `anthropic.AsyncAnthropic`.
- **Config-Driven Provider Selection**: Sourced from [`params.yaml`](../../../src/params.yaml) (`llm.provider: "groq"`, `llm.model_name: "llama-3.1-8b-instant"`).
- **Graceful Fallback**: Deterministic raw-signal passthrough enabled whenever `GROQ_API_KEY` or `ANTHROPIC_API_KEY` is not present in `.env`.
