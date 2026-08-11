"""PULSE — LLM Client Wrapper for Tactical Narrative Synthesis.

Thin async wrapper calling Anthropic SDK for instruction-following Haiku-class model calls.
Implements deterministic raw-payload passthrough on any exception
(timeout, network error, missing API key).

Authority: Phase 4 Decision D-7, D-7a, §2 System Design Guidelines.
"""

import json
import os
from typing import Any

import anthropic

from src.config.loader import Params, load_params
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert tennis performance analyst assistant. Phrase the pre-computed match "
    "state and leverage signals into a short, coach-readable tactical note (1-2 sentences). "
    "State numbers and statistics EXACTLY as provided in the input payload. DO NOT invent, "
    "hallucinate, alter, or re-derive any probabilities, leverage numbers, or player metrics."
)


async def call_narrative_llm(payload: dict[str, Any], params: Params | None = None) -> str | None:
    """Invoke Anthropic LLM API to synthesize narrative text for pre-computed signals.

    On any exception (timeout, network error, missing ANTHROPIC_API_KEY, rate limit),
    returns None to trigger raw-payload deterministic passthrough fallback (D-7).

    Args:
        payload: Pre-computed signal dictionary assembled from state results.
        params: Optional Params configuration object.

    Returns:
        str | None: Generated narrative string if successful, or None on failure/missing key.
    """
    cfg = params if params is not None else load_params()
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

        logger.debug(f"Calling LLM ({cfg.llm.model_name}) for narrative synthesis...")
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
                logger.debug(f"LLM narrative generated successfully ({len(text)} chars)")
                return text

        return None

    except Exception as e:
        logger.warning(
            f"LLM narrative synthesis failed ({type(e).__name__}: {e}). "
            f"Falling back to raw-payload passthrough."
        )
        return None
