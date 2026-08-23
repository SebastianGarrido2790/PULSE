# User Story & Problem Framing — PULSE

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine) | **Version:** 0.6.5 | **Date:** 2026-08-22

---

## 1. Personas & Stories

### Persona 1: Coach / Performance Analyst

**Story 1.1:** As a coach watching from the box, I want a real-time signal telling me when the current point is genuinely decisive, so that I don't waste my one changeover conversation on a moment that doesn't matter.

**Story 1.2:** As a coach preparing tactics against a specific opponent, I want to know where that opponent's return positioning deviates from a game-theoretically neutral mix, so that I can suggest a serve pattern that exploits a real, data-backed tendency rather than a hunch.

### Persona 2: Broadcast / Content Producer

**Story 2.1:** As a producer covering a live match, I want turning points flagged automatically and defensibly, so that commentary and highlight cuts land on moments that actually mattered, not just moments that looked dramatic.

**Story 2.2:** As a producer building a post-match package, I want an auto-generated list of the match's true high-leverage points with their outcomes, so that I don't have to manually rewatch and re-derive them.

### Persona 3: Player Development Analyst

**Story 3.1:** As an analyst reviewing a player's season, I want to know whether their high-leverage point performance is systematically below their own baseline or just ordinary variance, so that I direct training time at a real issue instead of a statistical artifact.

**Story 3.2:** As an analyst with limited data on an emerging player, I want the system to tell me plainly when it doesn't have enough data to draw a conclusion, so that I don't act on a false-confidence signal.

### Persona 4: Technical Evaluator & Portfolio Manager

**Story 4.1:** As a technical evaluator or hiring manager reviewing the repository, I want an interactive real-time browser cockpit streaming match points, so that I can immediately inspect the live leverage curve, Wilson confidence bounds, LangGraph node execution states, and game-theoretic payoff matrices in action without setting up custom curl or SSE clients.

**Story 4.2:** As a portfolio manager or product evaluator, I want an intuitive visual dashboard with match playback controls, live scoreboard, and tactical coach cards, so that I can evaluate the product's UX, market viability, and domain translation in under 60 seconds.

---

## 2. The 5 Whys — Root Cause Analysis

1. **Why** do coaches and broadcasters rely on intuition to identify decisive points? → Because no available tool computes a continuous, mathematically exact leverage value as the match unfolds.
2. **Why** does no available tool do this? → Because most tennis analytics platforms are built for post-match, batch-style reporting, not live conditional reasoning.
3. **Why** are they built that way? → Because the underlying data pipelines and dashboards were designed around descriptive statistics (aces, unforced errors, win percentages), not a model of the match as a nested probability process.
4. **Why** does that distinction matter? → Because leverage is not a descriptive statistic it is a derivative quantity (the marginal effect of one point on match-win probability) that requires the entire nested Markov structure to compute correctly at every score state.
5. **Why** hasn't that structure been operationalized as a live system? → Because doing so requires treating the mathematical model as the ground truth and building an event-driven architecture around it a systems-design problem, not a statistics problem, which is the actual root cause this project addresses.

---

## 3. Jobs-to-be-Done (JTBD)

**Primary functional job:** "When a match reaches a high-pressure moment, tell me with a stated confidence level whether it is genuinely decisive and what a data-grounded response looks like, so I can act during the match, not after it."

**Emotional job:** Replace the low-grade uncertainty of "is this actually a big moment or does it just feel like one" with a concrete, checkable answer.

**Social job:** Let a coach or analyst justify a tactical call with a specific, defensible number rather than "experience" alone useful in a locker-room or broadcast-booth conversation where the reasoning needs to be shareable, not just felt.

---

## 4. Problem Statement (Formal)

**For** coaches, performance analysts, and broadcast teams who need to distinguish decisive match moments from routine play in real time, **PULSE** is an event-driven tactical intelligence system **that** computes exact point leverage via closed-form probability theory and escalates to opponent-specific tactical analysis only when the situation and the available data both support it. **Unlike** existing tennis analytics tools, which are descriptive, retrospective, and opponent-agnostic, **PULSE** treats leverage as a live, continuously computed quantity with an explicit confidence basis, and treats "insufficient data" as a valid, honest output rather than a gap to be silently filled.

---

## 5. Failure Mode Analysis — What Breaks Without This System

| Failure Mode                             | Consequence                                                                                                                                                                      |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No continuous leverage signal            | Coaches and broadcasters default to intuition; decisive moments are inconsistently identified across analysts                                                                    |
| No opponent-specific tactical model      | Serve/return advice stays generic, missing exploitable, real tendencies specific to the opponent in front of them                                                                |
| No baseline-deviation model for pressure | A player's high-leverage underperformance is misread as either "choking" (when it's variance) or dismissed as variance (when it's a real, addressable pattern)                   |
| No confidence gating                     | A system without a sample-size gate would eventually produce a confident-sounding exploit recommendation backed by three historical points actively worse than no recommendation |
| Batch-only analytics                     | Insight arrives after the match is over, when it can no longer inform an in-match decision                                                                                       |

---

## 6. User Journey Map — Current State vs. Future State

_(Primary persona: Coach / Performance Analyst, during a live match)_

| Stage                                            | Current State                                                                        | Future State (with PULSE)                                                                                                                                                                         |
| ------------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Match in progress, routine points                | Coach watches passively, forming a general impression                                | `StateMonitorNode` logs leverage silently; no interruption                                                                                                                                        |
| Score reaches a tense moment (e.g., break point) | Coach relies on experience to judge whether this is "the" moment                     | Leverage crosses threshold; `PressureDiagnosticNode` and, if data supports it, `StrategyExploitNode` fire                                                                                         |
| Changeover                                       | Coach has seconds to give general encouragement or a generic tactical reminder       | Coach has a specific, data-backed note: e.g., an opponent-specific serve-direction adjustment with a stated expected-value gain, or an honest "no exploit available, focus on leverage awareness" |
| Post-match review                                | Manual rewatch or reliance on aggregate box-score stats to reconstruct what mattered | Auto-generated retrospective report of true high-leverage points and each player's performance relative to their own baseline                                                                     |
| Season-level development planning                | Anecdotal sense of a player's "clutch" ability                                       | Data-backed distinction between systematic high-leverage underperformance and ordinary variance                                                                                                   |

---

## 7. Constraints Acknowledged by Users

- Alerts are not perfect; the target precision is 0.75, not 1.0 users must accept occasional false escalations as a designed trade-off, not a defect.
- The exploit module will often say "insufficient data" for lower-tier or infrequently charted opponents. This is intended behavior, not a missing feature.
- PULSE is advisory. It does not make or execute tactical decisions; the human retains full authority over what to do with the signal.
- The current version operates on historical match replay, not a live official feed a coach using this in an actual live match is a future-phase capability, gated by the data-licensing constraints documented in the Project Charter.
