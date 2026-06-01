import asyncio
import logging
import random

from src.settings import settings

logger = logging.getLogger(__name__)


async def safe_ai_call(
    client,
    prompt,
    system_instruction=None,
    model=None,
    mime_type=None,
    retries=3,
):
    """Global utility to handle 429 RESOURCE_EXHAUSTED with exponential backoff."""
    from google.genai import types

    model = model or settings.GEMINI_CALL_MODEL
    config = types.GenerateContentConfig(
        system_instruction=system_instruction, response_mime_type=mime_type
    )

    for i in range(retries):
        try:
            return await client.aio.models.generate_content(
                model=model, contents=prompt, config=config
            )
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait_time = (2**i) + random.random()
                logger.warning(
                    f"[GLOBAL AI] Rate limit hit (429). Retrying in {wait_time:.2f}s... ({i+1}/{retries})"
                )
                await asyncio.sleep(wait_time)
            elif "500" in err_str or "503" in err_str:
                wait_time = (i + 1) * 2
                logger.warning(
                    f"[GLOBAL AI] Server error ({err_str[:3]}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                raise e
    return None
