"""Suggest existing public business/networking sources without joining chats."""
from __future__ import annotations

import asyncio
import re

from telethon import utils
from telethon.tl.types import Channel

SOURCE_WORDS = re.compile(
    r"tanishuv|tanishtiruv|networking|biznes|business|tadbirkor|hamkor|бизнес|предприним", re.I
)


async def suggest_sources(client):
    if client is None or not client.is_connected():
        return {"status": "source_unavailable", "sources": []}
    sources = []
    async with asyncio.timeout(60):
        async for dialog in client.iter_dialogs(limit=250):
            entity = dialog.entity
            if not isinstance(entity, Channel) or not entity.username:
                continue
            if not SOURCE_WORDS.search(entity.title or ""):
                continue
            sources.append({
                "chat_id": utils.get_peer_id(entity),
                "title": entity.title,
                "url": f"https://t.me/{entity.username}",
                "status": "needs_review",
            })
    return {"status": "ok", "sources": sources[:20]}
