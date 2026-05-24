"""
Streaming Telegram responses via Telethon.

Sends a placeholder message, then edits it progressively as the LLM
generates text. Gives users a ChatGPT-style typing experience.

Usage:
    from src.services.core.streaming import stream_gemini_response

    async for _ in stream_gemini_response(client, chat_id, gemini_client, prompt):
        pass  # editing happens internally
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

_CURSOR = " ▌"
_FLUSH_CHARS = 30        # edit every N new characters to limit API rate
_FLUSH_INTERVAL = 0.8    # also edit every N seconds minimum
_MAX_MESSAGE_LEN = 4000  # Telegram hard limit ~4096


async def stream_gemini_response(
    client,
    chat_id: int,
    gemini_client,
    prompt: str,
    model: str = "gemini-2.0-flash",
    placeholder: str = "⌛",
    reply_to: Optional[int] = None,
) -> str:
    """
    Streams a Gemini response to a Telegram chat by progressively editing
    a placeholder message.

    Returns the final full text.
    """
    msg = await client.send_message(
        chat_id,
        placeholder,
        reply_to=reply_to,
    )

    full_text = ""
    buffer = ""
    last_flush = asyncio.get_event_loop().time()

    try:
        response = gemini_client.models.generate_content_stream(
            model=model,
            contents=prompt,
        )

        for chunk in response:
            piece = chunk.text or ""
            if not piece:
                continue

            full_text += piece
            buffer += piece
            now = asyncio.get_event_loop().time()

            should_flush = (
                len(buffer) >= _FLUSH_CHARS
                or (now - last_flush) >= _FLUSH_INTERVAL
            )

            if should_flush:
                display = full_text[-_MAX_MESSAGE_LEN:] + _CURSOR
                try:
                    await client.edit_message(chat_id, msg.id, display)
                except Exception as e:
                    logger.debug(f"[stream] edit skipped: {e}")
                buffer = ""
                last_flush = now
                await asyncio.sleep(0)  # yield to event loop

        # Final edit — remove cursor, show complete text
        final = full_text[-_MAX_MESSAGE_LEN:]
        await client.edit_message(chat_id, msg.id, final)

    except Exception as e:
        logger.error(f"[stream] Error during streaming: {e}")
        fallback = full_text or f"❌ Xatolik: {e}"
        try:
            await client.edit_message(chat_id, msg.id, fallback[-_MAX_MESSAGE_LEN:])
        except Exception:
            pass

    return full_text


async def stream_text_chunks(
    client,
    chat_id: int,
    chunks: AsyncIterator[str],
    placeholder: str = "⌛",
    reply_to: Optional[int] = None,
) -> str:
    """
    Generic streaming: accepts any async iterator of text chunks.
    Useful when wrapping non-Gemini LLMs.
    """
    msg = await client.send_message(chat_id, placeholder, reply_to=reply_to)
    full_text = ""
    buffer = ""
    last_flush = asyncio.get_event_loop().time()

    async for piece in chunks:
        if not piece:
            continue
        full_text += piece
        buffer += piece
        now = asyncio.get_event_loop().time()

        if len(buffer) >= _FLUSH_CHARS or (now - last_flush) >= _FLUSH_INTERVAL:
            display = full_text[-_MAX_MESSAGE_LEN:] + _CURSOR
            try:
                await client.edit_message(chat_id, msg.id, display)
            except Exception as e:
                logger.debug(f"[stream] edit skipped: {e}")
            buffer = ""
            last_flush = now
            await asyncio.sleep(0)

    final = full_text[-_MAX_MESSAGE_LEN:]
    await client.edit_message(chat_id, msg.id, final)
    return full_text
