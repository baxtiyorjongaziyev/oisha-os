import logging

from src.settings import settings
from src.services.utils.gemini_fallback import (
    generate_content_with_fallback,
    is_transient_error,
)

logger = logging.getLogger(__name__)


async def safe_ai_call(
    client,
    prompt,
    system_instruction=None,
    model=None,
    mime_type=None,
    retries=3,
):
    """Global utility with shared Gemini model failover and quota cooldown."""
    from google.genai import types

    model = model or settings.GEMINI_CALL_MODEL
    config = types.GenerateContentConfig(
        system_instruction=system_instruction, response_mime_type=mime_type
    )

    del retries
    try:
        response, _ = await generate_content_with_fallback(
            client,
            primary_model=model,
            contents=prompt,
            config=config,
            env_name="GEMINI_GLOBAL_FALLBACK_MODELS",
            log_prefix="[GLOBAL AI]",
        )
        return response
    except Exception as exc:
        if not is_transient_error(exc):
            raise
        logger.warning("[GLOBAL AI] Gemini temporarily unavailable; local fallback active.")
        return None
