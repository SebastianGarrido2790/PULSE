"""PULSE — Post-Match Report Markdown Formatting Engine (src/analytics/formatting.py).

Provides deterministic formatting of structured MatchReportPayload objects into
standardized, publication-ready Markdown reports.

Authority: Phase 6.6 Post-Match Reporting Decisions D-6, D-7, FR-12, FR-13.
"""

from src.api.schemas import MatchReportResponse


def format_match_report_markdown(payload: MatchReportResponse) -> str:
    """Format the complete MatchReportPayload into a standardized Markdown document.

    Args:
        payload: Aggregated MatchReportResponse container.

    Returns:
        str: Fully formatted Markdown report.
    """
    s = payload.summary
    lines: list[str] = [
        f"# PULSE Match Intelligence Report: {s.player_1} vs {s.player_2}",
        f"> **Surface:** {s.surface} | **Winner:** {s.winner} | **Score:** {s.final_score} | "
        f"**Total Points:** {s.total_points}",
        "",
        "---",
        "",
        "## 1. Executive Strategic Summary",
        payload.executive_debrief,
        "",
        "---",
        "",
        "## 2. Match Overview & Key Indicators",
        "",
        "| Metric | Value |",
        "|:---|:---|",
        f"| **Match ID** | `{s.match_id}` |",
        f"| **Surface** | `{s.surface}` |",
        f"| **Final Winner** | **{s.winner}** |",
        f"| **Score Progression** | {s.final_score} |",
        f"| **Total Points Played** | {s.total_points} |",
        f"| **{s.player_1} Points Won** | {s.p1_points_won} ({s.p1_win_pct:.1%}) |",
        f"| **{s.player_2} Points Won** | {s.p2_points_won} ({s.p2_win_pct:.1%}) |",
        f"| **Average Leverage (Mean ΔL)** | {s.mean_delta_leverage:.2%} |",
        f"| **Peak Leverage (Max ΔL)** | {s.max_delta_leverage:.2%} |",
        f"| **Escalated Points (ΔL ≥ 5%)** | {s.high_leverage_point_count} points |",
        f"| **Break Points** | {s.break_points_converted} / {s.break_point_count} converted |",
        "",
        "---",
        "",
        "## 3. Top Pivotal Moments Audit (Highest Leverage Inflections)",
        "",
        "| Rank | Point # | Score Context | Server | Winner | ΔL | Wilson 95% CI | Impact |",
        "|:---:|:---:|:---|:---|:---|:---:|:---:|:---|",
    ]

    for idx, pt in enumerate(payload.pivotal_points, start=1):
        ci_str = f"[{pt.leverage_low:.1%}, {pt.leverage_high:.1%}]"
        lines.append(
            f"| **#{idx}** | `{pt.point_index}` | Set {pt.set_num}: {pt.game_score} "
            f"({pt.point_score}) | {pt.server_id} | **{pt.point_winner_id}** | "
            f"`{pt.delta_leverage:.1%}` | `{ci_str}` | {pt.impact_narrative} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Pressure Resilience Diagnostic",
            "",
            "| Player | Routine (ΔL < 10%) | Elevated (10% ≤ ΔL < 25%) | Critical (ΔL ≥ 25%) | "
            "Shift (Δp) | Resilience Rating |",
            "|:---|:---:|:---:|:---:|:---:|:---|",
        ]
    )

    for p in payload.pressure_resilience:
        lines.append(
            f"| **{p.player_id}** | {p.routine_win_rate:.1%} ({p.routine_points_count} pts) | "
            f"{p.elevated_win_rate:.1%} ({p.elevated_points_count} pts) | "
            f"{p.critical_win_rate:.1%} ({p.critical_points_count} pts) | "
            f"**{p.pressure_shift_delta_p:+.1%}** | {p.resilience_assessment} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Game-Theoretic Serve & Return Execution Audit",
            "",
            "| Server vs Returner | Charted | Realized Mix (W / B / T) | Nash Mix (W / T) | "
            "Returner Bias (W / T) | Gain (+EV) | Data Status |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
    )

    for gt in payload.game_theory_audit:
        real_mix = (
            f"{gt.realized_serve_mix.wide_pct:.0%} / "
            f"{gt.realized_serve_mix.body_pct:.0%} / "
            f"{gt.realized_serve_mix.t_pct:.0%}"
        )
        nash_str = (
            f"{gt.nash_serve_mix.get('wide', 0.5):.0%} / {gt.nash_serve_mix.get('t', 0.5):.0%}"
        )
        bias_str = f"{gt.returner_bias.get('wide', 0.5):.0%} / {gt.returner_bias.get('t', 0.5):.0%}"
        status = "Gated (N < 10)" if gt.sufficiency_gated else "Supported"
        lines.append(
            f"| **{gt.server_id}** vs {gt.returner_id} | {gt.sample_size} | {real_mix} | "
            f"{nash_str} | {bias_str} | **{gt.exploit_gain_delta_ev:+.1%}** | `{status}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 6. Sufficiency Gate & Governance Disclosure",
            "",
            "- **Markov Ground Truth:** All leverage values (ΔL) computed via the exact "
            "closed-form absorbing Markov chain solver.",
            "- **Wilson Uncertainty:** 95% binomial confidence bounds propagate historical "
            "observation volume transparently.",
            "- **Advisory Mandate:** PULSE outputs are strictly advisory tactical signals for "
            "human coaches and analysts.",
            "",
            "_Generated by PULSE Tactical Intelligence Engine v0.6.6_",
        ]
    )

    return "\n".join(lines)
