# Product Requirements Document — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.1.0 | **Date:** 2026-07-20 | **Status:** Phase 0 — Draft

---

## 1. Executive Summary

PULSE is a production-grade, event-driven system that monitors a tennis match point-by-point, computes exact leverage through a closed-form Markov solver, and conditionally escalates to deeper diagnostic and tactical analysis only when the match state warrants it. It is built to demonstrate a specific architectural discipline: a deterministic mathematical core as ground truth, ML layers that are honest about their own uncertainty, and an agentic orchestration layer whose shape changes with the situation rather than running a fixed routine on every input.

---

## 2. Project Analogy

PULSE is architecturally closer to an **ICU cardiac telemetry system** than to a reporting dashboard. A telemetry monitor runs continuously and cheaply, watching heart rhythm second by second. Most of the time it does nothing but log. When a reading crosses a threshold, it escalates first to a nurse-level alert, and if warranted, to a full diagnostic workup. It never bypasses the clinician's judgment, and it is explicit about signal confidence rather than crying wolf on marginal readings.

`StateMonitorNode` is the always-on rhythm monitor. `PressureDiagnosticNode` and `StrategyExploitNode` are the triggered escalations. The system is advisory by design, the same way a telemetry monitor informs a doctor rather than administering treatment. This analogy is the one to lead with when explaining PULSE to someone unfamiliar with the tennis domain it makes the event-driven, confidence-gated architecture legible immediately.

---

## 3. Goals & Non-Goals

### Goals

| Goal                                                  | Rationale                                                                                                    |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Continuous, mathematically exact leverage computation | Ground truth for every downstream decision                                                                   |
| Conditional escalation, not fixed-topology analysis   | Matches the actual shape of a live match                                                                     |
| Explicit uncertainty on every emitted signal          | A leverage value or exploit recommendation without a confidence basis is not trustworthy in an advisory tool |
| Full reproducibility of the deterministic core        | The one component of this system that must never silently drift                                              |
| Advisory-only outputs                                 | No autonomous action; a human always makes the final call                                                    |

### Non-Goals

| Non-Goal                                          | Rationale                                                                                 |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Live official data-feed integration               | Cost-prohibitive at this stage (see Project Charter §6); explicitly deferred              |
| Doubles-match support                             | Different scoring and positioning structure; out of scope for v1                          |
| Video/vision-based state extraction               | A separate, much larger engineering problem; PULSE consumes structured point data         |
| Autonomous coaching or in-match automated actions | Governance requirement advisory only                                                      |
| Betting-market integration                        | Not the product's purpose; would also introduce regulatory scope PULSE isn't designed for |

---

## 4. Personas (Summary)

Full stories and journey maps are in `user_story.md`. Summary:

| Persona                          | Core Need                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------- |
| **Coach / Performance Analyst**  | A trustworthy, real-time signal for when a point matters and what to do about it |
| **Broadcast / Content Producer** | Automatic, defensible identification of true turning points                      |
| **Player Development Analyst**   | Separating genuine weakness from ordinary variance in post-match review          |

---

## 5. Functional Requirements

| ID    | Requirement                                                                                                                               | Priority | Related Objective        |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------ |
| FR-1  | System computes leverage for every point via the closed-form Markov solver                                                                | Critical | O1                       |
| FR-2  | Leverage computation includes a confidence band derived from the observation count backing the underlying point-win probability           | Critical | O1, O5 (see ADR-005)     |
| FR-3  | `StateMonitorNode` runs on every point with no escalation by default                                                                      | Critical | O4                       |
| FR-4  | `PressureDiagnosticNode` triggers only when leverage crosses the configured threshold                                                     | Critical | O2, O4                   |
| FR-5  | `StrategyExploitNode` triggers only when leverage crosses the threshold **and** opponent sample size meets the configured minimum         | Critical | O3, O4, O8               |
| FR-6  | `StrategyExploitNode` degrades gracefully to a leverage-only alert when the sample-size gate is not met, rather than erroring or guessing | Critical | O8                       |
| FR-7  | `TacticalOutputNode` assembles only the signals that actually fired into the final output                                                 | High     | O4                       |
| FR-8  | All thresholds (leverage, sample size, latency) are defined in `params.yaml`, never hardcoded                                             | High     | O6                       |
| FR-9  | System streams leverage and escalation events via SSE/WebSocket per point                                                                 | High     | Inference requirements   |
| FR-10 | Every escalation decision (fire or suppress) is logged with its triggering condition                                                      | High     | O7                       |
| FR-11 | Historical matches can be replayed point-by-point at real-time cadence to simulate a live feed                                            | High     | Feasibility (Charter §6) |
| FR-12 | Every numeric output is traceable to a persisted, versioned artifact                                                                      | Critical | End State (Charter §1)   |

---

## 6. Non-Functional Requirements

| Category            | Requirement                                                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Latency**         | `StateMonitorNode` < 1s per point; triggered nodes < 5s                                                                      |
| **Reproducibility** | Markov solver and full replay bit-identical under a fixed seed; solver deviation from closed-form theory < 1e-9, CI-blocking |
| **Observability**   | OpenTelemetry spans per node; `structlog` JSON logs for every escalation decision, including suppressions                    |
| **Governance**      | Advisory-only outputs; no autonomous actions; every recommendation carries an explicit confidence/sample-size basis          |
| **Configurability** | Every threshold changeable via `params.yaml` without a code change or redeploy                                               |
| **Test Coverage**   | ≥70% line coverage, CI-enforced                                                                                              |
| **Security**        | No CRITICAL CVEs (Trivy-scanned); no secrets in code                                                                         |

---

## 7. Success Metrics

Full detail in `ml_canvas.md` §7–8. Headline targets:

- Solver-vs-closed-form deviation < 1e-9 (non-negotiable)
- Alert precision ≥ 0.75 on retrospective evaluation
- False-escalation rate < 0.15
- State Monitor latency < 1s

---

## 8. Assumptions & Constraints

- Historical, publicly available point-by-point charted match data is sufficient for offline development, training, and backtesting.
- No live official data-feed access exists at this stage; production deployment against a real live feed is explicitly a future, cost-gated phase.
- Opponent-specific exploit data will be sparse for lower-tier or infrequently charted players; the system must be honest about this rather than silently extrapolating.
- The system is advisory. It is not designed, tested, or intended to make autonomous coaching decisions.

---

## 9. Out of Scope

Matches `ml_canvas.md` §4 exactly: live official data-feed integration, doubles matches, video/vision-based state extraction, betting-market integration, autonomous actions.

---

## 10. Open Questions / Risks

| Question / Risk                                                                                                      | Status                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Should Tier 1 point-win probability move from calibrated LR + Wilson interval to a full hierarchical Bayesian model? | Resolved for v1 (LR + Wilson interval retained); documented as a candidate v2 decision in `system_design.md` (ADR-005)                                                  |
| What calibration method should `CalibratedClassifierCV` use, and does it change if the model changes?                | Resolved: Platt for LR v1; isotonic mandatory if LightGBM v2 is adopted (`system_design.md`, ADR-006)                                                                   |
| How should escalation thresholds account for leverage confidence-band width, not just the point value?               | Open to be finalized during Phase 3 design; provisionally: wide bands should raise the effective threshold, not just wide sample-size gates on the exploit module alone |
| Minimum viable historical dataset size for a credible v1 demo                                                        | Open to be determined once data ingestion (Phase 1) begins                                                                                                              |
