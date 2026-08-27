# PULSE — Shadow-Mode Acceptance Run Report

**Product:** PULSE (Point-Level Understanding & Strategic Leverage Engine)  
**Component:** Phase 7 Stage 8 — Shadow-Mode Operational Acceptance  
**Authority:** `pulse_ml_canvas.md`, `prd.md` §7, Phase 7 Decisions [D-1, D-2, D-13]  
**Date:** 2026-08-27  
**Status:** 🟢 PASS — All Operational Acceptance Gates Met

---

## 1. Executive Summary

This report documents the end-to-end shadow-mode acceptance run executed against the deployed containerized PULSE service stack. In compliance with Phase 7 Decision **[D-1] (Option A)**, evaluation exercised the deployed FastAPI service, SSE streaming engine, LangGraph state monitor, SQLite audit persistence, and Tactical Cockpit browser UI across held-out historical matches.

### Acceptance Criteria Verification Table

| Operational Requirement | Target SLA | Measured Value | Status |
| :--- | :---: | :---: | :---: |
| **Tactical Cockpit UI Delivery** | HTTP 200 + HTML | HTTP 200 (4.2ms) | 🟢 PASS |
| **Live SSE Stream Replay** | Zero Disconnects | 400 pts across 3 matches | 🟢 PASS |
| **StateMonitorNode Latency** | $< 1,000\text{ms}$ | Avg 35.56ms (P95 132.93ms) | 🟢 PASS |
| **Post-Match Report Latency** | $< 2,000\text{ms}$ | Avg 819.6ms (Max 886.7ms) | 🟢 PASS |
| **SQLite Persistence (FR-12)** | Audit Trail Persisted | 6,367 pts, 266 alerts | 🟢 PASS |

---

## 2. Match Replay Streaming Performance

| Match ID | Points | Alerts | Time | Avg Latency | P95 Latency | Max Latency | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev` | 207 | 11 | 7.8s | 35.56ms | 132.93ms | 145.45ms | 🟢 PASS |
| `20200104-M-ATP_Cup-RR-Stefanos_Tsitsipas-Alexander_Zverev` | 100 | 3 | 3.54s | 31.36ms | 33.27ms | 150.79ms | 🟢 PASS |
| `20200105-M-ATP_Cup-RR-Casper_Ruud-Fabio_Fognini` | 93 | 0 | 3.28s | 30.75ms | 48.61ms | 56.72ms | 🟢 PASS |

---

## 3. Post-Match Tactical Intelligence Retrieval

| Match ID | Total Points | Critical Moments | Latency (ms) | Target SLA | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `20200103-M-ATP_Cup-RR-Alex_De_Minaur-Alexander_Zverev` | 207 | 5 | 886.67ms | $< 2,000\text{ms}$ | 🟢 PASS |
| `20200104-M-ATP_Cup-RR-Stefanos_Tsitsipas-Alexander_Zverev` | 100 | 5 | 799.23ms | $< 2,000\text{ms}$ | 🟢 PASS |
| `20200105-M-ATP_Cup-RR-Casper_Ruud-Fabio_Fognini` | 93 | 5 | 772.95ms | $< 2,000\text{ms}$ | 🟢 PASS |

---

## 4. SQLite Audit Persistence (FR-12 Compliance)

- **Database Path:** `C:\Users\sebas\Desktop\PULSE\artifacts\pulse_session.db`
- **Total Points Persisted:** `6,367`
- **Total Escalation Logs Persisted:** `266`
- **Distinct Matches Stored:** `7`
- **All Acceptance Matches Present:** `True`

---

## 5. Gate 8 Sign-off

- [x] Containerized service stack booted and validated via `/health`.
- [x] Held-out match suite replays cleanly through `/v1/matches/{id}/stream`.
- [x] Sub-second latency budget maintained across all processed points.
- [x] Post-match tactical intelligence retrieval benchmarked under 2000ms.
- [x] SQLite session persistence verified across sessions.
- [x] Tactical Cockpit browser UI verified operational.
