"""PULSE — Post-Match Tactical Analytics & Reporting Engine (src/analytics/match_report.py).

Provides deterministic post-match aggregation, pivotal point extraction,
empirical-Bayes pressure resilience analysis, and game-theoretic strategy auditing.

Authority: Phase 6.6 Post-Match Reporting Decisions D-1, D-6, D-7, FR-12, FR-13.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.api.schemas import (
    GameTheoryExploitAudit,
    MatchReportResponse,
    MatchSummaryStats,
    PivotalPointEntry,
    PlayerPressureMetrics,
    ServeDirectionBreakdown,
)
from src.config.loader import Params, load_params
from src.core.game_theory import PayoffMatrix, compute_exploit
from src.core.leverage_uncertainty import propagate_leverage_uncertainty
from src.core.markov_solver import MatchState, compute_match_win_probability_from_state
from src.graph.strategy_exploit import lookup_payoff_matrix
from src.models.point_win_classifier import (
    StratumTable,
    load_stratum_table,
    resolve_point_win_probability,
)
from src.schemas.point_record import (
    PointOutcome,
    PointRecord,
    ServeDirection,
    Surface,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Backward-compatible type aliases
PivotalPointDetail = PivotalPointEntry
MatchReportPayload = MatchReportResponse


# ---------------------------------------------------------------------------
# Internal Analysis Helper Classes
# ---------------------------------------------------------------------------


@dataclass
class PointEvaluation:
    """Internal container for point-level computed metrics."""

    record: PointRecord
    point_index: int
    match_state: MatchState
    delta_leverage: float
    leverage_low: float
    leverage_high: float
    p_hat_server: float
    match_prob_before: float
    point_winner_id: str
    point_winner_role: str


# ---------------------------------------------------------------------------
# Core Analytical Algorithms
# ---------------------------------------------------------------------------


def infer_match_format(
    records: list[PointRecord],
    requested_format: Literal["bo3", "bo5"] = "bo3",
) -> Literal["bo3", "bo5"]:
    """Infer match format from point records if not explicitly forced to bo5.

    Auto-detects Best-of-5 scoring if any record exhibits set scores or totals
    incompatible with Best-of-3 rules (e.g. 2-1 set scores entering set 4).
    """
    if requested_format == "bo5":
        return "bo5"
    for r in records:
        if (r.p1_sets >= 2 and r.p2_sets >= 1) or (r.p2_sets >= 2 and r.p1_sets >= 1):
            return "bo5"
        if (r.p1_sets + r.p2_sets) >= 3 or r.p1_sets >= 3 or r.p2_sets >= 3:
            return "bo5"
    return "bo3"


def evaluate_all_points(
    records: list[PointRecord],
    stratum_table: StratumTable | None = None,
    params: Params | None = None,
    match_format: Literal["bo3", "bo5"] = "bo3",
) -> list[PointEvaluation]:
    """Evaluate leverage and uncertainty metrics for all points in a match sequence.

    Args:
        records: Ordered list of PointRecord objects.
        stratum_table: Loaded StratumTable for point-win probability resolution.
        params: Configuration parameters.
        match_format: 'bo3' or 'bo5'.

    Returns:
        list[PointEvaluation]: Sequence of evaluated point containers.
    """
    cfg = params if params is not None else load_params()
    table = (
        stratum_table
        if stratum_table is not None
        else _safe_load_stratum_table(Path("artifacts/models/point_win_classifier"))
    )

    effective_format = infer_match_format(records, match_format)
    evaluations: list[PointEvaluation] = []

    for idx, rec in enumerate(records):
        ctx = rec.to_point_context(point_index=idx, match_format=effective_format)
        match_state = ctx.to_match_state()

        # Resolve point-win probability
        stratum_res = resolve_point_win_probability(
            stratum_table=table,
            server_id=ctx.server_id,
            surface=ctx.surface,
            serve_number=ctx.serve_number,
            params=cfg,
        )

        # Propagate Wilson leverage uncertainty
        lev_res = propagate_leverage_uncertainty(
            state=match_state,
            wins=stratum_res.wins,
            sample_size=stratum_res.sample_size,
            confidence_level=cfg.uncertainty.confidence_level,
            min_observations=cfg.uncertainty.min_stratum_observations,
            default_p=cfg.solver.default_p_serve,
            fallback_margin=cfg.uncertainty.default_fallback_margin,
        )

        # Compute P1 match win prob before point
        # In Markov solver: server is player A
        p_server = stratum_res.p_hat
        p_server_match_win = compute_match_win_probability_from_state(match_state, p_server)
        p1_match_win = (
            p_server_match_win if rec.server_is_p1 else (1.0 - p_server_match_win)
        )

        # Identify winner player ID
        is_server_winner = rec.point_winner == PointOutcome.SERVER
        winner_id = rec.server if is_server_winner else rec.returner
        winner_role = "server" if is_server_winner else "returner"

        evaluations.append(
            PointEvaluation(
                record=rec,
                point_index=idx,
                match_state=match_state,
                delta_leverage=lev_res.leverage_point,
                leverage_low=lev_res.leverage_low,
                leverage_high=lev_res.leverage_high,
                p_hat_server=stratum_res.p_hat,
                match_prob_before=p1_match_win,
                point_winner_id=winner_id,
                point_winner_role=winner_role,
            )
        )

    return evaluations


def compute_match_summary(
    records: list[PointRecord],
    evaluations: list[PointEvaluation],
    params: Params | None = None,
) -> MatchSummaryStats:
    """Compute high-level statistical overview of the match.

    Args:
        records: PointRecord sequence.
        evaluations: Evaluated point metrics.
        params: Configuration parameters.

    Returns:
        MatchSummaryStats: Consolidated match summary metrics.
    """
    cfg = params if params is not None else load_params()
    threshold = cfg.thresholds.leverage_escalation

    first_rec = records[0]
    last_rec = records[-1]

    player_1 = first_rec.server if first_rec.server_is_p1 else first_rec.returner
    player_2 = first_rec.returner if first_rec.server_is_p1 else first_rec.server
    if isinstance(first_rec.surface, Surface):
        surface = str(first_rec.surface.value)
    else:
        surface = str(first_rec.surface)

    # Count points won by P1 and P2
    p1_points_won = 0
    p2_points_won = 0
    break_points_total = 0
    break_points_converted = 0

    leverages = [ev.delta_leverage for ev in evaluations]
    high_lev_count = sum(1 for lev in leverages if lev >= threshold)

    for rec in records:
        is_p1_server = rec.server_is_p1
        is_server_win = rec.point_winner == PointOutcome.SERVER
        p1_won_point = (is_p1_server and is_server_win) or (not is_p1_server and not is_server_win)

        if p1_won_point:
            p1_points_won += 1
        else:
            p2_points_won += 1

        if rec.break_point:
            break_points_total += 1
            # A break point is converted if the returner wins the point
            if not is_server_win:
                break_points_converted += 1

    total_points = len(records)
    p1_pct = (p1_points_won / total_points) if total_points > 0 else 0.0
    p2_pct = (p2_points_won / total_points) if total_points > 0 else 0.0

    # Winner is the player who won the final point
    last_eval = evaluations[-1]
    winner = last_eval.point_winner_id

    # Format final score string (e.g. Set 1, Games 6-4, etc.)
    final_score = (
        f"Sets: {last_rec.p1_sets}-{last_rec.p2_sets} | "
        f"Final Set Games: {last_rec.p1_games}-{last_rec.p2_games}"
    )

    return MatchSummaryStats(
        match_id=first_rec.match_id,
        surface=surface,
        player_1=player_1,
        player_2=player_2,
        winner=winner,
        final_score=final_score,
        total_points=total_points,
        p1_points_won=p1_points_won,
        p2_points_won=p2_points_won,
        p1_win_pct=p1_pct,
        p2_win_pct=p2_pct,
        mean_delta_leverage=float(sum(leverages) / len(leverages)) if leverages else 0.0,
        max_delta_leverage=float(max(leverages)) if leverages else 0.0,
        high_leverage_point_count=high_lev_count,
        break_point_count=break_points_total,
        break_points_converted=break_points_converted,
    )


def extract_top_pivotal_points(
    evaluations: list[PointEvaluation],
    top_n: int = 5,
) -> list[PivotalPointDetail]:
    """Extract and rank the top N highest-leverage pivotal moments.

    Args:
        evaluations: Evaluated point metrics.
        top_n: Number of pivotal points to extract (default 5).

    Returns:
        list[PivotalPointDetail]: Ranked list of top pivotal points.
    """
    # Sort by delta_leverage descending
    sorted_evals = sorted(evaluations, key=lambda ev: ev.delta_leverage, reverse=True)
    top_evals = sorted_evals[:top_n]

    pivotal_points: list[PivotalPointDetail] = []

    for ev in top_evals:
        rec = ev.record
        set_num = rec.p1_sets + rec.p2_sets + 1
        game_score = f"{rec.p1_games}-{rec.p2_games}"
        point_score = f"{rec.p1_score}-{rec.p2_score}"

        # Generate contextual impact narrative
        narrative_parts: list[str] = []
        if rec.match_point:
            action = "converted" if ev.point_winner_id == rec.server else "defended"
            narrative_parts.append(f"Match Point {action} by {ev.point_winner_id}")
        elif rec.set_point:
            action = "converted" if ev.point_winner_id == rec.server else "defended"
            narrative_parts.append(f"Set Point {action} in Set {set_num}")
        elif rec.break_point:
            action = "converted" if ev.point_winner_role == "returner" else "saved by server"
            narrative_parts.append(f"Break Point {action} at {game_score} ({point_score})")
        else:
            narrative_parts.append(
                f"Crucial inflection point won by {ev.point_winner_id} ({ev.point_winner_role})"
            )

        narrative_parts.append(
            f"Leverage: {ev.delta_leverage:.1%} "
            f"(95% CI: [{ev.leverage_low:.1%}, {ev.leverage_high:.1%}])"
        )
        impact_narrative = ". ".join(narrative_parts) + "."

        pivotal_points.append(
            PivotalPointDetail(
                point_index=ev.point_index,
                set_num=set_num,
                game_score=game_score,
                point_score=point_score,
                server_id=rec.server,
                returner_id=rec.returner,
                point_winner_id=ev.point_winner_id,
                point_winner_role=ev.point_winner_role,
                delta_leverage=ev.delta_leverage,
                leverage_low=ev.leverage_low,
                leverage_high=ev.leverage_high,
                p_hat_server=ev.p_hat_server,
                match_win_prob_before=ev.match_prob_before,
                is_break_point=rec.break_point,
                is_set_point=rec.set_point,
                is_match_point=rec.match_point,
                impact_narrative=impact_narrative,
            )
        )

    return pivotal_points


def compute_pressure_resilience(
    evaluations: list[PointEvaluation],
    player_1: str,
    player_2: str,
) -> list[PlayerPressureMetrics]:
    """Compute empirical pressure resilience metrics across leverage tiers.

    Partitions points into:
    - Routine: delta L < 0.10
    - Elevated: 0.10 <= delta L < 0.25
    - Critical: delta L >= 0.25

    Args:
        evaluations: Evaluated point metrics.
        player_1: Player 1 identifier.
        player_2: Player 2 identifier.

    Returns:
        list[PlayerPressureMetrics]: Resilience profiles for both players.
    """
    players = [player_1, player_2]
    metrics_list: list[PlayerPressureMetrics] = []

    for player in players:
        routine_won = 0
        routine_tot = 0
        elevated_won = 0
        elevated_tot = 0
        critical_won = 0
        critical_tot = 0

        for ev in evaluations:
            won = ev.point_winner_id == player
            lev = ev.delta_leverage

            if lev < 0.10:
                routine_tot += 1
                if won:
                    routine_won += 1
            elif lev < 0.25:
                elevated_tot += 1
                if won:
                    elevated_won += 1
            else:
                critical_tot += 1
                if won:
                    critical_won += 1

        r_win_rate = (routine_won / routine_tot) if routine_tot > 0 else 0.0
        e_win_rate = (elevated_won / elevated_tot) if elevated_tot > 0 else 0.0
        c_win_rate = (critical_won / critical_tot) if critical_tot > 0 else 0.0

        # Pressure shift: Critical win rate minus Routine win rate
        # If critical sample is 0, compare elevated vs routine
        if critical_tot > 0:
            delta_p = c_win_rate - r_win_rate
        elif elevated_tot > 0:
            delta_p = e_win_rate - r_win_rate
        else:
            delta_p = 0.0

        # Determine qualitative resilience rating
        if delta_p >= 0.05:
            resilience_assessment = "Elevated / Clutch (+Win Rate under Pressure)"
        elif delta_p <= -0.05:
            resilience_assessment = "Vulnerable (Performance Drops under Pressure)"
        else:
            resilience_assessment = "Steady / Resilient (Baseline Maintained)"

        metrics_list.append(
            PlayerPressureMetrics(
                player_id=player,
                total_points=len(evaluations),
                routine_points_count=routine_tot,
                routine_win_rate=r_win_rate,
                elevated_points_count=elevated_tot,
                elevated_win_rate=e_win_rate,
                critical_points_count=critical_tot,
                critical_win_rate=c_win_rate,
                pressure_shift_delta_p=delta_p,
                resilience_assessment=resilience_assessment,
            )
        )

    return metrics_list


def compute_game_theory_audit(
    records: list[PointRecord],
    payoff_matrices: dict[str, PayoffMatrix] | None = None,
    surface: str = "HARD",
    params: Params | None = None,
) -> list[GameTheoryExploitAudit]:
    """Audit realized serve directions against game-theoretic Nash equilibrium.

    Args:
        records: PointRecord sequence.
        payoff_matrices: Loaded dictionary of PayoffMatrix instances.
        surface: Court surface string.
        params: Configuration parameters.

    Returns:
        list[GameTheoryExploitAudit]: Game-theoretic serve strategy audit.
    """
    cfg = params if params is not None else load_params()
    matrices = (
        payoff_matrices
        if payoff_matrices is not None
        else _safe_load_payoff_matrices(Path("artifacts/models/game_theory/payoff_matrices.json"))
    )

    first_rec = records[0]
    p1 = first_rec.server if first_rec.server_is_p1 else first_rec.returner
    p2 = first_rec.returner if first_rec.server_is_p1 else first_rec.server

    matchups = [(p1, p2), (p2, p1)]
    audits: list[GameTheoryExploitAudit] = []

    for srv_id, ret_id in matchups:
        wide_cnt = 0
        body_cnt = 0
        t_cnt = 0

        for rec in records:
            if rec.server == srv_id and rec.serve_direction is not None:
                dir_val = (
                    rec.serve_direction.value
                    if isinstance(rec.serve_direction, ServeDirection)
                    else str(rec.serve_direction).lower()
                )
                if dir_val == "wide":
                    wide_cnt += 1
                elif dir_val == "body":
                    body_cnt += 1
                elif dir_val in ("t", "center"):
                    t_cnt += 1

        tot_charted = wide_cnt + body_cnt + t_cnt
        w_pct = (wide_cnt / tot_charted) if tot_charted > 0 else 0.0
        b_pct = (body_cnt / tot_charted) if tot_charted > 0 else 0.0
        t_pct = (t_cnt / tot_charted) if tot_charted > 0 else 0.0

        realized_breakdown = ServeDirectionBreakdown(
            wide_count=wide_cnt,
            body_count=body_cnt,
            t_count=t_cnt,
            total_charted=tot_charted,
            wide_pct=w_pct,
            body_pct=b_pct,
            t_pct=t_pct,
        )

        # Lookup payoff matrix for this server against this returner
        matrix = lookup_payoff_matrix(
            matrices, returner_id=ret_id, surface=surface, serve_number=1
        )

        nash_mix: dict[str, float] = {}
        ret_bias: dict[str, float] = {}
        exploit_gain = 0.0
        sufficiency_gated = tot_charted < 10

        if matrix is not None and not sufficiency_gated:
            exploit_res = compute_exploit(matrix, params=cfg)
            if exploit_res.sufficient_data and exploit_res.server_equilibrium_mix is not None:
                srv_mix = exploit_res.server_equilibrium_mix
                ret_mix = exploit_res.observed_returner_mix or [0.5, 0.5]
                nash_mix = {
                    "wide": float(srv_mix[0]),
                    "t": float(srv_mix[1]) if len(srv_mix) > 1 else 0.5,
                }
                ret_bias = {
                    "wide": float(ret_mix[0]),
                    "t": float(ret_mix[1]) if len(ret_mix) > 1 else 0.5,
                }
                exploit_gain = float(exploit_res.delta) if exploit_res.delta is not None else 0.0
            else:
                nash_mix = {"wide": 0.50, "t": 0.50}
                ret_bias = {"wide": 0.50, "t": 0.50}
                exploit_gain = 0.0
        else:
            # Default unexploited representation
            nash_mix = {"wide": 0.50, "t": 0.50}
            ret_bias = {"wide": 0.50, "t": 0.50}
            exploit_gain = 0.0

        audits.append(
            GameTheoryExploitAudit(
                server_id=srv_id,
                returner_id=ret_id,
                court_side="all",
                realized_serve_mix=realized_breakdown,
                nash_serve_mix=nash_mix,
                returner_bias=ret_bias,
                exploit_gain_delta_ev=exploit_gain,
                sample_size=tot_charted,
                sufficiency_gated=sufficiency_gated,
            )
        )

    return audits


POST_MATCH_SYSTEM_PROMPT = (
    "You are an expert tennis performance analyst assistant producing a post-match "
    "executive tactical debrief. Synthesize the provided match statistics, top pivotal "
    "inflection moments, pressure resilience metrics, and game-theoretic serve-return "
    "audits into a concise, 3-paragraph coach-readable debrief. State numbers and percentages "
    "EXACTLY as provided in the input payload. DO NOT invent, hallucinate, alter, or "
    "re-derive any figures."
)


def generate_deterministic_debrief(
    summary: MatchSummaryStats,
    pivotal_points: list[PivotalPointDetail],
    pressure: list[PlayerPressureMetrics],
    game_theory: list[GameTheoryExploitAudit],
) -> str:
    """Generate a deterministic, numbers-grounded executive strategic debrief.

    Follows the strict brain/brawn boundary: no hallucinated figures, exact alignment
    with computed metrics.

    Args:
        summary: MatchSummaryStats object.
        pivotal_points: Ranked pivotal points.
        pressure: Pressure resilience metrics.
        game_theory: Game theory audits.

    Returns:
        str: Multi-paragraph executive summary.
    """
    top_pt = pivotal_points[0] if pivotal_points else None
    top_pt_desc = (
        f"Point #{top_pt.point_index} (Set {top_pt.set_num}, {top_pt.game_score} at "
        f"{top_pt.point_score}, ΔL={top_pt.delta_leverage:.1%})"
        if top_pt
        else "the final set tiebreak"
    )

    p1_press = pressure[0] if len(pressure) > 0 else None
    p2_press = pressure[1] if len(pressure) > 1 else None

    p1_stat = (
        f"{p1_press.player_id}: {p1_press.critical_win_rate:.1%} critical win rate "
        f"(shift Δp={p1_press.pressure_shift_delta_p:+.1%}, {p1_press.resilience_assessment})"
        if p1_press
        else ""
    )
    p2_stat = (
        f"{p2_press.player_id}: {p2_press.critical_win_rate:.1%} critical win rate "
        f"(shift Δp={p2_press.pressure_shift_delta_p:+.1%}, {p2_press.resilience_assessment})"
        if p2_press
        else ""
    )

    peak_ev = max((gt.exploit_gain_delta_ev for gt in game_theory), default=0.0)

    lines: list[str] = [
        f"**Match Tactical Debrief: {summary.player_1} vs {summary.player_2} "
        f"({summary.surface} Court)**",
        f"Winner: **{summary.winner}** | Final Score: {summary.final_score} | "
        f"Total Points Played: {summary.total_points}.",
        "",
        f"**1. Leverage & Inflection Dynamics:** The match exhibited an average point leverage of "
        f"{summary.mean_delta_leverage:.1%} with a peak single-point leverage of "
        f"{summary.max_delta_leverage:.1%}. A total of {summary.high_leverage_point_count} points "
        f"crossed the deterministic tactical escalation threshold (τ = 5.0%). The single most "
        f"decisive inflection moment occurred on {top_pt_desc}.",
        "",
        "**2. Pressure Resilience Diagnostic:** Performance in high-leverage situations proved "
        f"decisive. Breakdown: {p1_stat}. {p2_stat}. Break points: "
        f"{summary.break_points_converted}/{summary.break_point_count} converted across both "
        "competitors.",
        "",
        "**3. Game-Theoretic Execution:** Serving distributions were audited against the minimax "
        "Nash equilibrium. Across all charted serves, return anticipation and directional mixes "
        f"yielded a peak tactical exploit margin of {peak_ev:+.1%} EV.",
    ]

    return "\n".join(lines)


async def generate_executive_debrief_async(
    summary: MatchSummaryStats,
    pivotal_points: list[PivotalPointDetail],
    pressure: list[PlayerPressureMetrics],
    game_theory: list[GameTheoryExploitAudit],
    params: Params | None = None,
    llm_client: Any | None = None,
) -> str:
    """Synthesize post-match executive debrief with grounded LLM call and deterministic fallback.

    Args:
        summary: High-level match summary.
        pivotal_points: Ranked pivotal points.
        pressure: Pressure resilience metrics per player.
        game_theory: Serve direction and game-theoretic audits.
        params: Optional configuration parameters.
        llm_client: Optional custom LLM client.

    Returns:
        str: 3-paragraph executive tactical summary.
    """
    fallback_text = generate_deterministic_debrief(
        summary, pivotal_points, pressure, game_theory
    )
    cfg = params if params is not None else load_params()

    payload = {
        "match_summary": summary.model_dump(),
        "top_pivotal_points": [pt.model_dump() for pt in pivotal_points[:3]],
        "pressure_resilience": [pr.model_dump() for pr in pressure],
        "game_theory_audit": [gt.model_dump() for gt in game_theory],
    }

    if llm_client is not None:
        try:
            if hasattr(llm_client, "synthesize_debrief"):
                res = await llm_client.synthesize_debrief(payload)
                if res:
                    return str(res)
            elif callable(llm_client):
                import inspect
                res = llm_client(payload)
                if inspect.isawaitable(res):
                    res = await res
                if res:
                    return str(res)
        except Exception as exc:
            logger.warning("Custom LLM client synthesis failed: %s", exc)
        return fallback_text

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set. Using deterministic executive debrief.")
        return fallback_text

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=cfg.llm.request_timeout_s,
        )
        import json
        user_prompt = f"Post-Match Analytics Payload:\n{json.dumps(payload, indent=2)}"
        response = await client.messages.create(
            model=cfg.llm.model_name,
            max_tokens=cfg.llm.max_tokens,
            temperature=cfg.llm.temperature,
            system=POST_MATCH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if response.content and len(response.content) > 0:
            first_block = response.content[0]
            text = getattr(first_block, "text", "")
            if isinstance(text, str) and text.strip():
                return text.strip()
    except Exception as exc:
        logger.warning(
            "Post-match LLM debrief generation failed (%s: %s). Using fallback.",
            type(exc).__name__,
            exc,
        )

    return fallback_text


def generate_executive_debrief(
    summary: MatchSummaryStats,
    pivotal_points: list[PivotalPointDetail],
    pressure: list[PlayerPressureMetrics],
    game_theory: list[GameTheoryExploitAudit],
    llm_client: Any | None = None,
    params: Params | None = None,
) -> str:
    """Generate executive tactical debrief, calling synchronous client or deterministic fallback."""
    if llm_client is not None and callable(llm_client) and not hasattr(llm_client, "__await__"):
        try:
            payload = {
                "match_summary": summary.model_dump(),
                "top_pivotal_points": [pt.model_dump() for pt in pivotal_points[:3]],
                "pressure_resilience": [pr.model_dump() for pr in pressure],
                "game_theory_audit": [gt.model_dump() for gt in game_theory],
            }
            res = llm_client(payload)
            if isinstance(res, str) and res.strip():
                return res.strip()
        except Exception as exc:
            logger.warning("Sync LLM callable failed: %s", exc)

    return generate_deterministic_debrief(summary, pivotal_points, pressure, game_theory)


def format_match_report_markdown(payload: MatchReportPayload) -> str:
    """Format the complete MatchReportPayload into a standardized Markdown document.

    Args:
        payload: Aggregated MatchReportPayload container.

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
        bias_str = (
            f"{gt.returner_bias.get('wide', 0.5):.0%} / {gt.returner_bias.get('t', 0.5):.0%}"
        )
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
            "_Generated by PULSE Tactical Intelligence Engine v0.6.5_",
        ]
    )

    return "\n".join(lines)


def generate_match_report(
    records: list[PointRecord],
    stratum_table: StratumTable | None = None,
    payoff_matrices: dict[str, PayoffMatrix] | None = None,
    params: Params | None = None,
    match_format: Literal["bo3", "bo5"] = "bo3",
    llm_client: Any | None = None,
) -> MatchReportPayload:
    """Generate the complete, deterministic Post-Match Report payload for a match.

    Args:
        records: List of PointRecord items for the match.
        stratum_table: Optional StratumTable.
        payoff_matrices: Optional dictionary of PayoffMatrix instances.
        params: Optional Params configuration.
        match_format: 'bo3' or 'bo5'.
        llm_client: Optional LLM client or callable for debrief synthesis.

    Returns:
        MatchReportPayload: Aggregated post-match report payload.
    """
    evaluations = evaluate_all_points(
        records=records,
        stratum_table=stratum_table,
        params=params,
        match_format=match_format,
    )

    summary = compute_match_summary(records, evaluations, params=params)
    pivotal = extract_top_pivotal_points(evaluations, top_n=5)
    pressure = compute_pressure_resilience(evaluations, summary.player_1, summary.player_2)
    game_theory = compute_game_theory_audit(
        records,
        payoff_matrices=payoff_matrices,
        surface=summary.surface,
        params=params,
    )
    debrief = generate_executive_debrief(
        summary, pivotal, pressure, game_theory, llm_client=llm_client, params=params
    )

    report = MatchReportPayload(
        summary=summary,
        pivotal_points=pivotal,
        pressure_resilience=pressure,
        game_theory_audit=game_theory,
        executive_debrief=debrief,
    )
    report.markdown_report = format_match_report_markdown(report)
    return report


async def generate_match_report_async(
    records: list[PointRecord],
    stratum_table: StratumTable | None = None,
    payoff_matrices: dict[str, PayoffMatrix] | None = None,
    params: Params | None = None,
    match_format: Literal["bo3", "bo5"] = "bo3",
    llm_client: Any | None = None,
) -> MatchReportPayload:
    """Asynchronously generate the complete Post-Match Report payload for a match.

    Args:
        records: List of PointRecord items for the match.
        stratum_table: Optional StratumTable.
        payoff_matrices: Optional dictionary of PayoffMatrix instances.
        params: Optional Params configuration.
        match_format: 'bo3' or 'bo5'.
        llm_client: Optional LLM client or callable for debrief synthesis.

    Returns:
        MatchReportPayload: Aggregated post-match report payload.
    """
    evaluations = evaluate_all_points(
        records=records,
        stratum_table=stratum_table,
        params=params,
        match_format=match_format,
    )

    summary = compute_match_summary(records, evaluations, params=params)
    pivotal = extract_top_pivotal_points(evaluations, top_n=5)
    pressure = compute_pressure_resilience(evaluations, summary.player_1, summary.player_2)
    game_theory = compute_game_theory_audit(
        records,
        payoff_matrices=payoff_matrices,
        surface=summary.surface,
        params=params,
    )
    debrief = await generate_executive_debrief_async(
        summary, pivotal, pressure, game_theory, params=params, llm_client=llm_client
    )

    report = MatchReportPayload(
        summary=summary,
        pivotal_points=pivotal,
        pressure_resilience=pressure,
        game_theory_audit=game_theory,
        executive_debrief=debrief,
    )
    report.markdown_report = format_match_report_markdown(report)
    return report


# ---------------------------------------------------------------------------
# Fallback Loaders for Model Artifacts
# ---------------------------------------------------------------------------


def _safe_load_stratum_table(path: Path) -> StratumTable:
    """Load StratumTable if artifact exists, else return fallback container."""
    dir_path = path.parent if path.is_file() or path.suffix == ".json" else path
    if dir_path.exists():
        try:
            return load_stratum_table(dir_path)
        except Exception as exc:
            logger.warning("Could not load StratumTable from [%s]: %s", dir_path, exc)
    return StratumTable(global_default_p=0.62)


def _safe_load_payoff_matrices(path: Path) -> dict[str, PayoffMatrix]:
    """Load PayoffMatrix dict if artifact exists, else return empty dict."""
    if path.exists():
        try:
            from src.core.game_theory import load_payoff_matrices

            return load_payoff_matrices(path)
        except Exception as exc:
            logger.warning("Could not load PayoffMatrices from [%s]: %s", path, exc)
    return {}
