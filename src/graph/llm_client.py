"""PULSE — LLM Client Wrapper for Tactical Narrative Synthesis.

Thin async wrapper calling LLM providers (Groq Cloud default free-tier, Anthropic)
for instruction-following tactical narrative synthesis.
Implements deterministic raw-payload passthrough on any exception
(timeout, network error, missing API key).

Authority: Phase 4 Decision D-7, D-7a, Phase 6.6 Free-Tier LLM Decision.
"""

import json
import os
from typing import Any

import anthropic
import groq
from dotenv import load_dotenv

from src.config.loader import Params, load_params
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert tennis performance analyst assistant. Phrase the pre-computed match "
    "state and leverage signals into a short, coach-readable tactical note (1-2 sentences). "
    "State numbers and statistics EXACTLY as provided in the input payload. DO NOT invent, "
    "hallucinate, alter, or re-derive any probabilities, leverage numbers, or player metrics."
)


async def _call_groq(cfg: Params, payload: dict[str, Any]) -> str | None:
    """Invoke Groq Cloud API for ultra-fast LPU narrative synthesis."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.warning(
            "GROQ_API_KEY not found in environment. Falling back to raw-payload passthrough."
        )
        return None

    try:
        client = groq.AsyncGroq(
            api_key=api_key,
            timeout=cfg.llm.request_timeout_s,
        )
        user_content = f"Input Signal Payload:\n{json.dumps(payload, indent=2)}"
        logger.debug("Calling Groq LLM (%s) for narrative synthesis...", cfg.llm.model_name)

        response = await client.chat.completions.create(
            model=cfg.llm.model_name,
            max_tokens=cfg.llm.max_tokens,
            temperature=cfg.llm.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        if response.choices and len(response.choices) > 0:
            text = response.choices[0].message.content
            if text:
                text = text.strip()
                logger.debug("Groq LLM narrative generated successfully (%d chars)", len(text))
                return text
        return None

    except Exception as e:
        logger.warning(
            "Groq LLM narrative synthesis failed (%s: %s). "
            "Falling back to raw-payload passthrough.",
            type(e).__name__,
            e,
        )
        return None


async def _call_anthropic(cfg: Params, payload: dict[str, Any]) -> str | None:
    """Invoke Anthropic API for Claude-based narrative synthesis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not found in environment. Falling back to raw-payload passthrough."
        )
        return None

    try:
        client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=cfg.llm.request_timeout_s,
        )
        user_content = f"Input Signal Payload:\n{json.dumps(payload, indent=2)}"
        logger.debug("Calling Anthropic LLM (%s) for narrative synthesis...", cfg.llm.model_name)

        response = await client.messages.create(
            model=cfg.llm.model_name,
            max_tokens=cfg.llm.max_tokens,
            temperature=cfg.llm.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        if response.content and len(response.content) > 0:
            first_block = response.content[0]
            if isinstance(first_block, anthropic.types.TextBlock):
                text = first_block.text.strip()
                logger.debug(
                    "Anthropic LLM narrative generated successfully (%d chars)", len(text)
                )
                return text
        return None

    except Exception as e:
        logger.warning(
            "Anthropic LLM narrative synthesis failed (%s: %s). "
            "Falling back to raw-payload passthrough.",
            type(e).__name__,
            e,
        )
        return None


async def call_narrative_llm(payload: dict[str, Any], params: Params | None = None) -> str | None:
    """Invoke configured LLM provider to synthesize narrative text for pre-computed signals.

    On any exception (timeout, network error, missing API key, rate limit),
    returns None to trigger raw-payload deterministic passthrough fallback (D-7).

    Args:
        payload: Pre-computed signal dictionary assembled from state results.
        params: Optional Params configuration object.

    Returns:
        str | None: Generated narrative string if successful, or None on failure/missing key.
    """
    cfg = params if params is not None else load_params()
    provider = cfg.llm.provider.lower().strip()

    if provider == "groq":
        return await _call_groq(cfg, payload)
    elif provider == "anthropic":
        return await _call_anthropic(cfg, payload)
    else:
        logger.warning(
            "Unsupported LLM provider [%s]. Falling back to raw-payload passthrough.",
            provider,
        )
        return None
