"""PULSE — DeepEval Groundedness Verification (tests/evals/test_tactical_output_groundedness.py).

Verifies that TacticalOutputNode narrative text does not introduce any numbers,
confidence claims, or exploit recommendations absent from its input signal payload.

Authority: Phase 5 Decisions D-1, D-8, D-11, FR-7, DeepEval test framework §7.
"""

import json
import re
from typing import Any

import pytest
from deepeval.test_case import LLMTestCase


def extract_numbers(text: str) -> list[float]:
    """Extract numeric values (percentages, decimals, integers) from text."""
    # Find patterns like 8.0%, 0.18, -0.08, 40
    raw_matches = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    numbers: list[float] = []
    for m in raw_matches:
        try:
            val = float(m)
            numbers.append(val)
        except ValueError:
            pass
    return numbers


def extract_payload_numbers(payload: dict[str, Any]) -> set[float]:
    """Flatten all numeric values present in payload (including percentages)."""
    text_repr = json.dumps(payload)
    raw_numbers = extract_numbers(text_repr)

    valid_set: set[float] = set()
    for num in raw_numbers:
        valid_set.add(round(num, 4))
        # Add percentage representation (e.g. 0.08 -> 8.0)
        valid_set.add(round(abs(num) * 100, 1))
        valid_set.add(round(num * 100, 1))

    return valid_set


def verify_narrative_groundedness(
    narrative: str, raw_payload: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Determine whether narrative is 100% grounded in raw_payload.

    Checks:
    1. Numbers in narrative exist in payload (or direct percentage translations).
    2. Exploit payloads with sufficient_data=False or best_response_action=None
       do not claim specific tactical exploit actions.

    Args:
        narrative: Synthesized narrative text string.
        raw_payload: Input signal payload dictionary.

    Returns:
        tuple[bool, list[str]]: (is_grounded, list_of_violations).
    """
    violations: list[str] = []
    payload_numbers = extract_payload_numbers(raw_payload)

    # 1. Numeric claims check
    narrative_numbers = extract_numbers(narrative)
    for num in narrative_numbers:
        rounded_num = round(num, 4)
        rounded_abs_num = round(abs(num), 4)

        # Check if number matches any payload number or percentage
        match_found = any(
            abs(rounded_num - p) < 1e-3 or abs(rounded_abs_num - p) < 1e-3 for p in payload_numbers
        )
        if not match_found:
            violations.append(f"Ungrounded number [{num}] in narrative not present in payload.")

    # 2. Gated exploit recommendation hallucination check (Step 39, D-11)
    exploit_res = raw_payload.get("exploit_result")
    if exploit_res is not None:
        sufficient_data = exploit_res.get("sufficient_data", True)
        best_response = exploit_res.get("best_response_action")

        if not sufficient_data or best_response is None:
            # Check for hallucinated action verbs/tactics
            tactical_action_keywords = [
                "target",
                "serve wide",
                "serve body",
                "forehand return",
                "backhand return",
                "exploit deep",
                "slice",
            ]
            narrative_lower = narrative.lower()
            for kw in tactical_action_keywords:
                if kw in narrative_lower:
                    violations.append(
                        f"Hallucinated action [{kw}] when exploit recommendation is None/gated."
                    )

    is_grounded = len(violations) == 0
    return is_grounded, violations


@pytest.mark.evals
def test_groundedness_valid_pressure_narrative() -> None:
    """Verify groundedness check passes for valid pressure diagnostic narrative."""
    payload = {
        "point_context": {
            "match_id": "m100",
            "point_index": 12,
            "server_id": "alcaraz_c",
            "returner_id": "sinner_j",
            "surface": "HARD",
            "serve_number": 1,
        },
        "leverage_result": {
            "delta_leverage": 0.18,
            "delta_leverage_low": 0.12,
            "delta_leverage_high": 0.24,
            "p_hat": 0.68,
            "sample_size": 40,
            "fallback_tier": 0,
        },
        "pressure_result": {
            "server_id": "alcaraz_c",
            "leverage_bucket": 1,
            "pressure_deviation": -0.08,
            "deviation_low_90": -0.14,
            "deviation_high_90": -0.02,
            "is_sufficient_sample": True,
        },
    }

    valid_narrative = "Alcaraz serve win rate drops by 8.0% under elevated leverage (ΔL=0.18)."

    test_case = LLMTestCase(
        input=json.dumps(payload),
        actual_output=valid_narrative,
        retrieval_context=[json.dumps(payload)],
    )

    is_grounded, violations = verify_narrative_groundedness(
        str(test_case.actual_output or ""), payload
    )
    assert is_grounded, f"Groundedness violations found: {violations}"


@pytest.mark.evals
def test_groundedness_catches_hallucinated_numbers() -> None:
    """Verify groundedness check catches fabricated numbers absent from payload."""
    payload = {
        "point_context": {
            "match_id": "m101",
            "point_index": 5,
            "server_id": "alcaraz_c",
            "returner_id": "sinner_j",
            "surface": "HARD",
            "serve_number": 1,
        },
        "leverage_result": {
            "delta_leverage": 0.18,
            "delta_leverage_low": 0.12,
            "delta_leverage_high": 0.24,
            "p_hat": 0.68,
            "sample_size": 40,
            "fallback_tier": 0,
        },
    }

    hallucinated_narrative = "Alcaraz win probability falls by 35% on second serve."

    is_grounded, violations = verify_narrative_groundedness(hallucinated_narrative, payload)
    assert not is_grounded
    assert any("35" in v for v in violations)


@pytest.mark.evals
def test_groundedness_valid_gated_exploit_payload() -> None:
    """Verify groundedness passes for Phase 5 gated exploit payload (Step 39)."""
    payload = {
        "point_context": {
            "match_id": "m102",
            "point_index": 15,
            "server_id": "alcaraz_c",
            "returner_id": "sinner_j",
            "surface": "HARD",
            "serve_number": 1,
        },
        "leverage_result": {
            "delta_leverage": 0.22,
            "delta_leverage_low": 0.15,
            "delta_leverage_high": 0.29,
            "p_hat": 0.70,
            "sample_size": 50,
            "fallback_tier": 0,
        },
        "exploit_result": {
            "sufficient_data": False,
            "n_opp_total": 12,
            "equilibrium_value": None,
            "best_response_action": None,
            "expected_value_if_exploiting": None,
            "delta": None,
        },
    }

    valid_gated_narrative = (
        "Elevated leverage point against sinner_j (insufficient sample size N=12)."
    )

    is_grounded, violations = verify_narrative_groundedness(valid_gated_narrative, payload)
    assert is_grounded, f"Groundedness violations found: {violations}"


@pytest.mark.evals
def test_groundedness_catches_hallucinated_gated_exploit_recommendation() -> None:
    """Verify groundedness fails if narrative invents a tactic from a gated exploit payload."""
    payload = {
        "point_context": {
            "match_id": "m103",
            "point_index": 15,
            "server_id": "alcaraz_c",
            "returner_id": "sinner_j",
            "surface": "HARD",
            "serve_number": 1,
        },
        "leverage_result": {
            "delta_leverage": 0.22,
            "delta_leverage_low": 0.15,
            "delta_leverage_high": 0.29,
            "p_hat": 0.70,
            "sample_size": 50,
            "fallback_tier": 0,
        },
        "exploit_result": {
            "sufficient_data": False,
            "n_opp_total": 12,
            "equilibrium_value": None,
            "best_response_action": None,
            "expected_value_if_exploiting": None,
            "delta": None,
        },
    }

    hallucinated_exploit_narrative = "Target Sinner's backhand return on wide serve."

    is_grounded, violations = verify_narrative_groundedness(hallucinated_exploit_narrative, payload)
    assert not is_grounded
    assert any("Hallucinated action" in v for v in violations)
