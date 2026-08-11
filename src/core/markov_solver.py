"""PULSE — Deterministic Closed-Form Markov Solver.

Ground-truth engine computing exact point-by-point win probabilities and point
leverage (Delta L) for hierarchical tennis match structures (Point -> Game -> Set -> Match).

Authority: ADR-002, markov_solver_spec.md v1.0.1
"""

from functools import cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.utils.exceptions import SolverException


class MatchState(BaseModel):
    """Fully described current match state for Markov solver input.

    Attributes:
        point_score_server: Server's point score (0="0", 1="15", 2="30", 3="40", 4="AD").
        point_score_returner: Returner's point score (same encoding).
        game_score_server: Server's game count in current set (0-6; 7 = tiebreak).
        game_score_returner: Returner's game count in current set (0-6; 7 = tiebreak).
        set_score_server: Server's set count (0-2 for BO3, 0-3 for BO5).
        set_score_returner: Returner's set count.
        server_id: Identifier of the current server. Used for logging only.
        match_format: "bo3" or "bo5".
        deciding_set_tiebreak: If True, the final set is a 10-point match tiebreak.
    """

    point_score_server: int = Field(..., ge=0, le=4)
    point_score_returner: int = Field(..., ge=0, le=4)
    game_score_server: int = Field(..., ge=0, le=7)
    game_score_returner: int = Field(..., ge=0, le=7)
    set_score_server: int = Field(..., ge=0, le=3)
    set_score_returner: int = Field(..., ge=0, le=3)
    server_id: str = Field(default="server")
    match_format: Literal["bo3", "bo5"] = Field(default="bo3")
    deciding_set_tiebreak: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_joint_point_score(self) -> "MatchState":
        """Reject point-score combinations that cannot occur in valid tennis play.

        Per-field bounds (0-4) alone permit unreachable joint states -- most
        importantly both players simultaneously at "AD" (4), or one player at
        "AD" while the other is not at exactly "40" (3). Only one player can
        hold advantage at a time, and the opponent must be at 40 when they do.
        Left unchecked, such a state would bypass the explicit deuce/advantage
        handling in `game_prob_from_state` and fall into the general recursive
        fallback in a region where deep, unbounded-feeling recursion is possible
        -- the same class of risk closed for the tiebreak in spec v1.0.1.

        Raises:
            ValueError: If the joint point score is not a reachable tennis state.
                Pydantic wraps this as a `ValidationError` at construction time,
                per spec section 6's input-validation contract.
        """
        srv, ret = self.point_score_server, self.point_score_returner
        if srv == 4 and ret != 3:
            raise ValueError(
                f"Invalid joint point score: server at AD (4) requires returner "
                f"at 40 (3), got point_score_returner={ret}"
            )
        if ret == 4 and srv != 3:
            raise ValueError(
                f"Invalid joint point score: returner at AD (4) requires server "
                f"at 40 (3), got point_score_server={srv}"
            )
        return self


class SolverResult(BaseModel):
    """Solver output for a single score state and serve probability.

    Attributes:
        match_win_prob: P(server wins match | current state, p_serve).
        match_win_prob_if_won: P(server wins match | server wins this point).
        match_win_prob_if_lost: P(server wins match | server loses this point).
        leverage: delta_L = match_win_prob_if_won - match_win_prob_if_lost.
        p_serve: The serve-win probability used as input.
        state: The MatchState used as input.
    """

    match_win_prob: float = Field(..., ge=0.0, le=1.0)
    match_win_prob_if_won: float = Field(..., ge=0.0, le=1.0)
    match_win_prob_if_lost: float = Field(..., ge=0.0, le=1.0)
    leverage: float = Field(..., ge=0.0, le=1.0)
    p_serve: float = Field(..., ge=0.0, le=1.0)
    state: MatchState


def game_win_probability(p: float) -> float:
    """Compute the probability of winning a game given point win probability p.

    Formulas (§3.1 of spec):
        d(p) = p^2 / (p^2 + (1-p)^2)
        g(p) = p^4 * (15 - 34*p + 28*p^2 - 8*p^3) / (1 - 2*p*(1-p))

    Args:
        p: Probability server wins an individual point (0 < p < 1).

    Returns:
        float: Closed-form probability of winning the game.

    Raises:
        SolverException: If p is not strictly in the open interval (0, 1).
    """
    if p <= 0.0 or p >= 1.0:
        raise SolverException(f"p_serve must be strictly in open interval (0, 1), got {p}")

    denom = 1.0 - 2.0 * p * (1.0 - p)
    if abs(denom) < 1e-12:
        raise SolverException(f"Degenerate denominator in game_win_probability for p={p}")

    numer = (p**4) * (15.0 - 34.0 * p + 28.0 * (p**2) - 8.0 * (p**3))
    return float(numer / denom)


def next_server(n: int) -> Literal["A", "B"]:
    """Determine server for the nth point (1-indexed) in a standard tiebreak.

    Pattern: Point 1 -> A, Points 2-3 -> B, Points 4-5 -> A...
    """
    if n <= 1:
        return "A"
    block = (n - 2) // 2
    return "B" if block % 2 == 0 else "A"


def t_tail(p_A: float, p_B: float) -> float:
    """Compute exact closed-form deuce tail probability for tiebreaks tied at N-N (N >= 6).

    Formula (§3.2 of spec v1.0.1):
        t_tail(p_A, p_B) = (p_A * p_B) / (1 - p_A - p_B + 2 * p_A * p_B)
    """
    denom = 1.0 - p_A - p_B + 2.0 * p_A * p_B
    if abs(denom) < 1e-12:
        return 0.5
    return float((p_A * p_B) / denom)


def tiebreak_win_probability(p_A: float, p_B: float, match_tiebreak: bool = False) -> float:
    """Compute tiebreak win probability for Player A serving point 1.

    Args:
        p_A: Probability A wins a point on A's serve.
        p_B: Probability A wins a point on B's serve (1 - q_B).
        match_tiebreak: If True, 10-point Champions Tiebreak; else 7-point tiebreak.

    Returns:
        float: Exact tiebreak win probability for Player A.
    """
    target = 10 if match_tiebreak else 7

    @cache
    def _tb(i: int, j: int) -> float:
        # Base cases
        if i >= target and (i - j) >= 2:
            return 1.0
        if j >= target and (j - i) >= 2:
            return 0.0
        if i >= target - 1 and j >= target - 1 and i == j:
            return t_tail(p_A, p_B)

        n = i + j + 1
        srv = next_server(n)
        if srv == "A":
            return p_A * _tb(i + 1, j) + (1.0 - p_A) * _tb(i, j + 1)
        else:
            return p_B * _tb(i + 1, j) + (1.0 - p_B) * _tb(i, j + 1)

    return _tb(0, 0)


def game_prob_from_state(p: float, s_server: int, s_returner: int) -> float:
    """Compute win probability for current game from intermediate score (s_server, s_returner).

    Encoding: 0="0", 1="15", 2="30", 3="40", 4="AD".
    """
    if p <= 0.0 or p >= 1.0:
        raise SolverException(f"p_serve must be in open interval (0, 1), got {p}")

    q = 1.0 - p

    @cache
    def _game(i: int, j: int) -> float:
        if i >= 4 and (i - j) >= 2:
            return 1.0
        if j >= 4 and (j - i) >= 2:
            return 0.0
        if i == 3 and j == 3:  # Deuce
            d_p = (p**2) / (p**2 + q**2)
            return d_p
        if i == 4 and j == 3:  # Advantage Server
            d_p = (p**2) / (p**2 + q**2)
            return p + q * d_p
        if i == 3 and j == 4:  # Advantage Returner
            d_p = (p**2) / (p**2 + q**2)
            return p * d_p

        return p * _game(i + 1, j) + q * _game(i, j + 1)

    return _game(s_server, s_returner)


def set_win_probability(p_A: float, p_B: float, a_serves_first: bool = True) -> float:
    """Compute set win probability for Player A from 0-0 in games.

    Args:
        p_A: A's serve-win rate.
        p_B: A's return-point win rate.
        a_serves_first: True if A serves the first game.
    """
    g_A = game_win_probability(p_A)
    g_B = 1.0 - game_win_probability(1.0 - p_B)

    @cache
    def _set(i: int, j: int, a_serves: bool) -> float:
        if i >= 6 and (i - j) >= 2:
            return 1.0
        if j >= 6 and (j - i) >= 2:
            return 0.0
        if i == 6 and j == 6:
            return tiebreak_win_probability(p_A, p_B, match_tiebreak=False)

        if a_serves:
            return g_A * _set(i + 1, j, False) + (1.0 - g_A) * _set(i, j + 1, False)
        else:
            return g_B * _set(i + 1, j, True) + (1.0 - g_B) * _set(i, j + 1, True)

    return _set(0, 0, a_serves_first)


def set_prob_from_state(
    p_A: float,
    p_B: float,
    g_server: int,
    g_returner: int,
    pt_server: int,
    pt_returner: int,
    server_is_A: bool = True,
) -> float:
    """Compute set win probability for A from arbitrary game and point score within current set."""
    g_A = game_win_probability(p_A)
    g_B = 1.0 - game_win_probability(1.0 - p_B)

    # If tiebreak is in progress (games 6-6)
    if g_server == 6 and g_returner == 6:
        target = 7

        @cache
        def _tb_in_progress(i: int, j: int) -> float:
            if i >= target and (i - j) >= 2:
                return 1.0 if server_is_A else 0.0
            if j >= target and (j - i) >= 2:
                return 0.0 if server_is_A else 1.0
            if i >= target - 1 and j >= target - 1 and i == j:
                t_val = t_tail(p_A, p_B)
                return t_val if server_is_A else (1.0 - t_val)

            n = i + j + 1
            srv = next_server(n)
            if srv == "A":
                return p_A * _tb_in_progress(i + 1, j) + (1.0 - p_A) * _tb_in_progress(i, j + 1)
            else:
                return p_B * _tb_in_progress(i + 1, j) + (1.0 - p_B) * _tb_in_progress(i, j + 1)

        pts_A = pt_server if server_is_A else pt_returner
        pts_B = pt_returner if server_is_A else pt_server
        return _tb_in_progress(pts_A, pts_B)

    # In standard game: compute current game win prob for server
    p_srv = p_A if server_is_A else (1.0 - p_B)
    cur_game_win_prob_srv = game_prob_from_state(p_srv, pt_server, pt_returner)

    # Convert current game win prob to probability A wins current game
    p_game_A_wins = cur_game_win_prob_srv if server_is_A else (1.0 - cur_game_win_prob_srv)

    @cache
    def _set_rest(i: int, j: int, a_serves: bool) -> float:
        if i >= 6 and (i - j) >= 2:
            return 1.0
        if j >= 6 and (j - i) >= 2:
            return 0.0
        if i == 6 and j == 6:
            return tiebreak_win_probability(p_A, p_B, match_tiebreak=False)

        if a_serves:
            return g_A * _set_rest(i + 1, j, False) + (1.0 - g_A) * _set_rest(i, j + 1, False)
        else:
            return g_B * _set_rest(i + 1, j, True) + (1.0 - g_B) * _set_rest(i, j + 1, True)

    games_A = g_server if server_is_A else g_returner
    games_B = g_returner if server_is_A else g_server

    next_server_is_A = not server_is_A
    return p_game_A_wins * _set_rest(games_A + 1, games_B, next_server_is_A) + (
        1.0 - p_game_A_wins
    ) * _set_rest(games_A, games_B + 1, next_server_is_A)


def compute_match_win_probability_from_state(state: MatchState, p_serve: float) -> float:
    """Compute match win probability for the current server from any MatchState.

    Args:
        state: Fully described current match state.
        p_serve: Server's point-win probability (0 < p_serve < 1).

    Returns:
        float: Match-win probability for current server (0.0 to 1.0).

    Raises:
        SolverException: If p_serve <= 0 or >= 1, or match is already decided.
    """
    if p_serve <= 0.0 or p_serve >= 1.0:
        raise SolverException(f"p_serve must be strictly in open interval (0, 1), got {p_serve}")

    target_sets = 2 if state.match_format == "bo3" else 3

    if state.set_score_server >= target_sets:
        raise SolverException(f"Match decided: server set score is {state.set_score_server}")
    if state.set_score_returner >= target_sets:
        raise SolverException(f"Match decided: returner set score is {state.set_score_returner}")

    p_A = p_serve
    p_B = p_serve

    cur_set_win_prob_A = set_prob_from_state(
        p_A=p_A,
        p_B=p_B,
        g_server=state.game_score_server,
        g_returner=state.game_score_returner,
        pt_server=state.point_score_server,
        pt_returner=state.point_score_returner,
        server_is_A=True,
    )

    std_set_win_prob_A = set_win_probability(p_A, p_B, a_serves_first=True)

    @cache
    def _match_rest(s_A: int, s_B: int) -> float:
        if s_A >= target_sets:
            return 1.0
        if s_B >= target_sets:
            return 0.0

        is_deciding = (s_A == target_sets - 1) and (s_B == target_sets - 1)
        s_prob = (
            tiebreak_win_probability(p_A, p_B, match_tiebreak=True)
            if (is_deciding and state.deciding_set_tiebreak)
            else std_set_win_prob_A
        )

        return s_prob * _match_rest(s_A + 1, s_B) + (1.0 - s_prob) * _match_rest(s_A, s_B + 1)

    return cur_set_win_prob_A * _match_rest(
        state.set_score_server + 1, state.set_score_returner
    ) + (1.0 - cur_set_win_prob_A) * _match_rest(
        state.set_score_server, state.set_score_returner + 1
    )


def advance_point_state(state: MatchState, server_won: bool) -> MatchState:
    """Advance a MatchState by one point (won or lost by server)."""
    pt_srv = state.point_score_server
    pt_ret = state.point_score_returner
    gm_srv = state.game_score_server
    gm_ret = state.game_score_returner
    st_srv = state.set_score_server
    st_ret = state.set_score_returner

    # Case 1: In tiebreak (games 6-6)
    if gm_srv == 6 and gm_ret == 6:
        new_pt_srv = pt_srv + (1 if server_won else 0)
        new_pt_ret = pt_ret + (1 if not server_won else 0)
        is_final_set = st_srv + st_ret == (2 if state.match_format == "bo3" else 4)
        target = 10 if (state.deciding_set_tiebreak and is_final_set) else 7

        if new_pt_srv >= target and (new_pt_srv - new_pt_ret) >= 2:
            return MatchState(
                point_score_server=0,
                point_score_returner=0,
                game_score_server=0,
                game_score_returner=0,
                set_score_server=st_srv + 1,
                set_score_returner=st_ret,
                server_id=state.server_id,
                match_format=state.match_format,
                deciding_set_tiebreak=state.deciding_set_tiebreak,
            )
        elif new_pt_ret >= target and (new_pt_ret - new_pt_srv) >= 2:
            return MatchState(
                point_score_server=0,
                point_score_returner=0,
                game_score_server=0,
                game_score_returner=0,
                set_score_server=st_srv,
                set_score_returner=st_ret + 1,
                server_id=state.server_id,
                match_format=state.match_format,
                deciding_set_tiebreak=state.deciding_set_tiebreak,
            )
        else:
            return MatchState(
                point_score_server=new_pt_srv,
                point_score_returner=new_pt_ret,
                game_score_server=6,
                game_score_returner=6,
                set_score_server=st_srv,
                set_score_returner=st_ret,
                server_id=state.server_id,
                match_format=state.match_format,
                deciding_set_tiebreak=state.deciding_set_tiebreak,
            )

    # Case 2: Standard Game
    server_won_game = False
    returner_won_game = False

    if server_won:
        if pt_srv == 3 and pt_ret < 3:
            server_won_game = True
            new_pt_srv, new_pt_ret = 0, 0
        elif pt_srv == 3 and pt_ret == 3:
            new_pt_srv, new_pt_ret = 4, 3
        elif pt_srv == 3 and pt_ret == 4:
            new_pt_srv, new_pt_ret = 3, 3
        elif pt_srv == 4:
            server_won_game = True
            new_pt_srv, new_pt_ret = 0, 0
        else:
            new_pt_srv, new_pt_ret = pt_srv + 1, pt_ret
    else:
        if pt_ret == 3 and pt_srv < 3:
            returner_won_game = True
            new_pt_srv, new_pt_ret = 0, 0
        elif pt_srv == 3 and pt_ret == 3:
            new_pt_srv, new_pt_ret = 3, 4
        elif pt_srv == 4 and pt_ret == 3:
            new_pt_srv, new_pt_ret = 3, 3
        elif pt_ret == 4:
            returner_won_game = True
            new_pt_srv, new_pt_ret = 0, 0
        else:
            new_pt_srv, new_pt_ret = pt_srv, pt_ret + 1

    if server_won_game:
        new_gm_srv = gm_srv + 1
        new_gm_ret = gm_ret
    elif returner_won_game:
        new_gm_srv = gm_srv
        new_gm_ret = gm_ret + 1
    else:
        return MatchState(
            point_score_server=new_pt_srv,
            point_score_returner=new_pt_ret,
            game_score_server=gm_srv,
            game_score_returner=gm_ret,
            set_score_server=st_srv,
            set_score_returner=st_ret,
            server_id=state.server_id,
            match_format=state.match_format,
            deciding_set_tiebreak=state.deciding_set_tiebreak,
        )

    if new_gm_srv >= 6 and (new_gm_srv - new_gm_ret) >= 2:
        return MatchState(
            point_score_server=0,
            point_score_returner=0,
            game_score_server=0,
            game_score_returner=0,
            set_score_server=st_srv + 1,
            set_score_returner=st_ret,
            server_id=state.server_id,
            match_format=state.match_format,
            deciding_set_tiebreak=state.deciding_set_tiebreak,
        )
    elif new_gm_ret >= 6 and (new_gm_ret - new_gm_srv) >= 2:
        return MatchState(
            point_score_server=0,
            point_score_returner=0,
            game_score_server=0,
            game_score_returner=0,
            set_score_server=st_srv,
            set_score_returner=st_ret + 1,
            server_id=state.server_id,
            match_format=state.match_format,
            deciding_set_tiebreak=state.deciding_set_tiebreak,
        )

    return MatchState(
        point_score_server=0,
        point_score_returner=0,
        game_score_server=new_gm_srv,
        game_score_returner=new_gm_ret,
        set_score_server=st_srv,
        set_score_returner=st_ret,
        server_id=state.server_id,
        match_format=state.match_format,
        deciding_set_tiebreak=state.deciding_set_tiebreak,
    )


def compute_leverage(state: MatchState, p_serve: float) -> SolverResult:
    """Compute match-win probability and point leverage for a given state.

    Primary public entry point of the Markov solver engine (spec §5.3).

    Args:
        state: Fully described current match state.
        p_serve: Server's point-win probability (0 < p_serve < 1).

    Returns:
        SolverResult containing match_win_prob, leverage, and conditional probabilities.

    Raises:
        SolverException: If p_serve is invalid or match is already decided.
    """
    p_current = compute_match_win_probability_from_state(state, p_serve)

    state_won = advance_point_state(state, server_won=True)
    target_sets = 2 if state.match_format == "bo3" else 3
    if state_won.set_score_server >= target_sets:
        p_won = 1.0
    else:
        p_won = compute_match_win_probability_from_state(state_won, p_serve)

    state_lost = advance_point_state(state, server_won=False)
    if state_lost.set_score_returner >= target_sets:
        p_lost = 0.0
    else:
        p_lost = compute_match_win_probability_from_state(state_lost, p_serve)

    leverage = max(0.0, min(1.0, p_won - p_lost))

    return SolverResult(
        match_win_prob=p_current,
        match_win_prob_if_won=p_won,
        match_win_prob_if_lost=p_lost,
        leverage=leverage,
        p_serve=p_serve,
        state=state,
    )
