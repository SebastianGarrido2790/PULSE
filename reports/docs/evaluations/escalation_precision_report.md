# PULSE — Retrospective Escalation-Precision Evaluation Report

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Component:** Phase 7 — Retrospective Escalation Validation (`scripts/evaluate_escalation_precision.py`)  
**Authority:** `pulse_ml_canvas.md` §8, `prd.md` §7, Phase 7 Decisions [D-2, D-9]  
**Date:** 2026-08-27  
**Status:** 🟢 PASS — All Production Acceptance Gates Met

---

## 1. Executive Summary

This report delivers the retrospective ground-truth evaluation across **100 historical matches** (13,790 evaluated points).

The central evaluation principle of PULSE asserts that **deterministic math is ground truth**.
1. **Live Prediction:** `StateMonitorNode` evaluates pre-point leverage $L_t = V(S_{win}) - V(S_{loss})$ using $p_{serve}$. If $L_t \ge \tau_{esc}$ (0.10), an alert is triggered.
2. **Retrospective Ground Truth:** Realized swing $\Delta V_t = |V_{post} - V_{pre}|$ is calculated using the actual outcome via the Markov solver.
3. **Validation Criterion:** True Positive if $\Delta V_t \ge 0.038$.

### Production Acceptance Headline Gate

| Metric | PRD §7 Target | Measured Result | Status |
| :--- | :---: | :---: | :---: |
| **Alert Precision** | $\ge 0.75$ | **0.9602** (96.0%) | 🟢 **PASS** |
| **False Escalation Rate** | $< 0.15$ | **0.0398** (4.0%) | 🟢 **PASS** |
| **Alert Trigger Rate (Selectivity)** | Tracked ($5\% - 15\%$) | **6.93%** | 🟢 **OPTIMAL** |
| **Realized Swing Impact Ratio** | $\ge 5.0\times$ | **11.0\times** (8.74% vs 0.79%) | 🟢 **HIGH FIDELITY** |

---

## 2. Contingency & Confusion Matrix

Across 13,790 point observations:

| | Realized Swing $\ge 0.038$ | Realized Swing $< 0.038$ | Total |
| :--- | :---: | :---: | :---: |
| **Live Escalation Fired** | **917** (TP) | **38** (FP) | **955** |
| **Routine Point** | **515** (FN) | **12,320** (TN) | **12,835** |
| **Total** | **1,432** | **12,358** | **13,790** |

### Additional Performance Metrics:
- **Sensitivity / Recall:** `0.6404` (64.0%)
- **Specificity:** `0.9969` (99.7%)
- **F1 Score:** `0.7683`
- **Mean Pre-Point Leverage (Escalated Points):** `0.1864`
- **Mean Pre-Point Leverage (Routine Points):** `0.0162`

---

## 3. Stratified Breakdown Analysis

### 3.1 Breakdown by Court Surface

| Surface | Points | Alerts | Trigger Rate | Alert Precision | False Escalation | Mean Realized Swing |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CLAY** | 5,717 | 401 | 7.0% | **0.9800** | 0.0200 | 8.57% |
| **HARD** | 8,073 | 554 | 6.9% | **0.9458** | 0.0542 | 8.86% |

### 3.2 Breakdown by Match Scoring Format

| Match Format | Points | Alerts | Trigger Rate | Alert Precision | False Escalation | Mean Realized Swing |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BO3** | 13,790 | 955 | 6.9% | **0.9602** | 0.0398 | 8.74% |

### 3.3 High-Stakes Situational Points Breakdown

| Point Type | Points | Escalated | Escalation % | Mean Leverage | Mean Realized Swing |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Break Points** | 1,886 | 184 | 9.8% | 0.2877 | 13.25% |
| **Tiebreak Points** | 528 | 115 | 21.8% | 0.1472 | 7.38% |
| **Deuce / Advantage** | 1,672 | 201 | 12.0% | 0.2000 | 9.65% |
| **Game Points** | 1,839 | 101 | 5.5% | 0.1409 | 6.77% |
| **Routine Points** | 10,137 | 518 | 5.1% | 0.1630 | 7.62% |

---

## 4. Evaluation Semantics & Limitations ([D-2])

As established in Phase 7 Decision **[D-2]**:
1. **Statistical Holdout Context:** Stratum tables and serve statistics aggregate historical data across player appearances. While match IDs were held out from tuning, player baseline priors carry historical career data. This measures retrospective precision on unseen match sequences.
2. **Deterministic Mathematical Ground Truth:** The Markov solver is closed-form combinatorial probability theory. Pre-point leverage $L_t$ and post-point delta $\Delta V_t$ are exact conditional expectations.

---

## 5. Exit Criteria Sign-off

- [x] Retrospective evaluation script `evaluate_escalation_precision.py` passed.
- [x] Alert Precision ($\ge 0.75$) passed with **0.9602**.
- [x] False Escalation Rate ($< 0.15$) passed with **0.0398**.
- [x] Machine-readable metrics exported to `escalation_precision_metrics.json`.
- [x] Verified against PRD §7 and `pulse_ml_canvas.md` §8 criteria.
