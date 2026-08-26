# ADR: Free-Tier LLM Provider Selection & Integration (Groq Cloud)

## Status
**Decided & Implemented** (Option 1: Groq Cloud — `llama-3.1-8b-instant`).

---

## Context & Problem Statement
PULSE requires a small, fast, instruction-following LLM for two advisory presentation tasks:
1. **Live Point Tactical Narrative (`TacticalOutputNode`)**: Synthesizes structured state and leverage outputs into a concise, coach-readable note (1–2 sentences) only on escalated points.
2. **Post-Match Tactical Debrief (`src/analytics/match_report.py`)**: Synthesizes aggregated pivotal moments, pressure metrics, and game-theoretic audits into a 3-paragraph executive summary.

The original default was Anthropic (`claude-3-5-haiku-20241022`), which requires a paid API key and credit balance. To eliminate barriers for local developers, practitioners, and reviewers, PULSE requires an out-of-the-box free-tier LLM provider that meets the following constraints:
- **Sub-1s Latency Budget**: Real-time replay cannot block on slow cloud inference.
- **Strict Numerical Groundedness**: Must faithfully reproduce exact Markov leverage and pressure numbers without hallucination.
- **Generous Free Tier**: High rate limits without requiring a credit card.

---

## Comparative Evaluation

| Provider & Model | Free Tier Limits | Typical Latency | Decision |
| :--- | :--- | :--- | :--- |
| **Option 1: Groq Cloud**<br>`llama-3.1-8b-instant` | **30 RPM / 14,400 RPD**<br>Free API Key | **~100–300 ms** (Fastest) | **SELECTED** |
| **Option 2: Google Gemini (AI Studio)**<br>`gemini-2.5-flash` | 15 RPM / 1,500 RPD | ~400–800 ms | Viable secondary option |
| **Option 3: Local Ollama**<br>`llama3.2:1b` / `qwen2.5:1.5b` | Unlimited (Local Hardware) | ~200–600 ms | High local dependency |
| **Option 4: OpenRouter Free Models**<br>`meta-llama/llama-3.2-3b-instruct:free` | Dynamic community quotas | ~600–1200 ms | Latency variance |

---

## Decision Drivers & Rationale
1. **Ultra-Low Inference Latency**: Groq's Language Processing Units (LPUs) deliver text in 100–300ms, easily satisfying the triggered node latency budget ($<5\text{s}$) and live streaming pacing.
2. **Generous Rate Limits**: 30 requests per minute and 14,400 requests per day on Groq's free tier comfortably supports hundreds of points and multi-match replay sessions.
3. **Deterministic Fallback Preserved**: If `GROQ_API_KEY` is not present in the environment, the system automatically falls back to deterministic raw-signal passthrough without crashing or throwing errors.
4. **Dual Provider Compatibility**: The codebase supports both `groq` and `anthropic` configurable via `params.yaml`.

---

## Configuration & Usage Guide

### 1. Configure in `params.yaml`
```yaml
llm:
  provider: "groq"                # Default free-tier provider
  model_name: "llama-3.1-8b-instant" # Fast LPU model
  max_tokens: 300
  temperature: 0.2
  request_timeout_s: 4.0
```

### 2. Set Environment Variable
Create or update your `.env` file:
```bash
# Get your free key at: https://console.groq.com
GROQ_API_KEY=gsk_your_free_groq_api_key_here
```

### 3. Verification
Run the test suite:
```bash
uv run pytest tests/unit/test_tactical_output.py tests/unit/test_match_report.py
```
