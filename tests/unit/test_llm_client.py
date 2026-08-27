"""Unit tests for PULSE direct SDK LLM client wrapper and fallback resilience.

Tests direct SDK async wrappers (groq.AsyncGroq, anthropic.AsyncAnthropic),
deterministic raw-payload passthrough fallback on network/timeout/missing keys,
malformed responses, and unsupported provider configurations.

Authority: Phase 7 Decision D-8, ADR-015, Workflow Stage 1.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import groq
import pytest

from src.config.loader import LLMParams, Params, load_params
from src.graph.llm_client import (
    _call_anthropic,
    _call_groq,
    call_narrative_llm,
)


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    """Sample input signal payload for narrative synthesis."""
    return {
        "point_id": "pt_42",
        "leverage": 0.185,
        "delta_leverage": 0.082,
        "pressure_deviation": -0.045,
        "exploit": {
            "exploit_found": True,
            "recommended_direction": "wide",
            "expected_gain": 0.052,
        },
    }


@pytest.fixture
def mock_params_groq() -> Params:
    """Mock Params configured for Groq."""
    params = load_params().model_copy(deep=True)
    params.llm = LLMParams(
        provider="groq",
        model_name="groq/compound-mini",
        temperature=0.2,
        max_tokens=256,
        request_timeout_s=5.0,
    )
    return params


@pytest.fixture
def mock_params_anthropic() -> Params:
    """Mock Params configured for Anthropic."""
    params = load_params().model_copy(deep=True)
    params.llm = LLMParams(
        provider="anthropic",
        model_name="claude-3-5-haiku-20241022",
        temperature=0.2,
        max_tokens=256,
        request_timeout_s=5.0,
    )
    return params


# =============================================================================
# Groq SDK Tests
# =============================================================================


@pytest.mark.asyncio
async def test_call_groq_missing_api_key(
    mock_params_groq: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_groq returns None when GROQ_API_KEY is not set in environment."""
    with patch.dict("os.environ", {}, clear=True):
        result = await _call_groq(mock_params_groq, sample_payload)
        assert result is None


@pytest.mark.asyncio
async def test_call_groq_success(mock_params_groq: Params, sample_payload: dict[str, Any]) -> None:
    """Assert _call_groq invokes client and returns valid text on successful completion."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Target wide serve to exploit returner positioning."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test_mock_key"}):
        with patch("groq.AsyncGroq", return_value=mock_client):
            result = await _call_groq(mock_params_groq, sample_payload)
            assert result == "Target wide serve to exploit returner positioning."
            mock_client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_groq_empty_response(
    mock_params_groq: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_groq returns None when API returns empty choices or empty text."""
    mock_response = MagicMock()
    mock_response.choices = []

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test_mock_key"}):
        with patch("groq.AsyncGroq", return_value=mock_client):
            result = await _call_groq(mock_params_groq, sample_payload)
            assert result is None


@pytest.mark.asyncio
async def test_call_groq_api_exception_fallback(
    mock_params_groq: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_groq handles API exceptions and returns None without raising."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=groq.APIConnectionError(request=MagicMock())
    )

    with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test_mock_key"}):
        with patch("groq.AsyncGroq", return_value=mock_client):
            result = await _call_groq(mock_params_groq, sample_payload)
            assert result is None


# =============================================================================
# Anthropic SDK Tests
# =============================================================================


@pytest.mark.asyncio
async def test_call_anthropic_missing_api_key(
    mock_params_anthropic: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_anthropic returns None when ANTHROPIC_API_KEY is not set."""
    with patch.dict("os.environ", {}, clear=True):
        result = await _call_anthropic(mock_params_anthropic, sample_payload)
        assert result is None


@pytest.mark.asyncio
async def test_call_anthropic_success(
    mock_params_anthropic: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_anthropic invokes client and returns valid text on completion."""
    mock_block = anthropic.types.TextBlock(
        text="High pressure point. Exploit opponent wide weakness.",
        type="text",
    )
    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test-mock-key"}):
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_anthropic(mock_params_anthropic, sample_payload)
            assert result == "High pressure point. Exploit opponent wide weakness."
            mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_anthropic_empty_response(
    mock_params_anthropic: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_anthropic returns None when API returns empty content."""
    mock_response = MagicMock()
    mock_response.content = []

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test-mock-key"}):
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_anthropic(mock_params_anthropic, sample_payload)
            assert result is None


@pytest.mark.asyncio
async def test_call_anthropic_api_exception_fallback(
    mock_params_anthropic: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert _call_anthropic handles API exceptions and returns None without crashing."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test-mock-key"}):
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_anthropic(mock_params_anthropic, sample_payload)
            assert result is None


# =============================================================================
# Multi-Provider Dispatcher Tests
# =============================================================================


@pytest.mark.asyncio
async def test_call_narrative_llm_groq_dispatch(
    mock_params_groq: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert call_narrative_llm dispatches to _call_groq when configured."""
    with patch("src.graph.llm_client._call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = "Groq output"
        res = await call_narrative_llm(sample_payload, params=mock_params_groq)
        assert res == "Groq output"
        mock_groq.assert_awaited_once_with(mock_params_groq, sample_payload)


@pytest.mark.asyncio
async def test_call_narrative_llm_anthropic_dispatch(
    mock_params_anthropic: Params, sample_payload: dict[str, Any]
) -> None:
    """Assert call_narrative_llm dispatches to _call_anthropic when configured."""
    with patch("src.graph.llm_client._call_anthropic", new_callable=AsyncMock) as mock_anthropic:
        mock_anthropic.return_value = "Anthropic output"
        res = await call_narrative_llm(sample_payload, params=mock_params_anthropic)
        assert res == "Anthropic output"
        mock_anthropic.assert_awaited_once_with(mock_params_anthropic, sample_payload)


@pytest.mark.asyncio
async def test_call_narrative_llm_unsupported_provider(sample_payload: dict[str, Any]) -> None:
    """Assert call_narrative_llm returns None on unsupported provider."""
    params = load_params().model_copy(deep=True)
    params.llm = LLMParams(
        provider="openai_mock",
        model_name="gpt-4o",
        temperature=0.2,
        max_tokens=256,
        request_timeout_s=5.0,
    )
    result = await call_narrative_llm(sample_payload, params=params)
    assert result is None


@pytest.mark.asyncio
async def test_call_narrative_llm_default_params_load(sample_payload: dict[str, Any]) -> None:
    """Assert call_narrative_llm loads default params when none is provided."""
    with patch("src.graph.llm_client._call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = "Default groq response"
        res = await call_narrative_llm(sample_payload, params=None)
        assert res == "Default groq response"
