"""RNP (Ruka Na Pulse) channel research and frog selection helpers."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from src.agents.researcher_agent import ResearcherAgent
from src.services.ai.frog_agent import FrogAgent

logger = logging.getLogger(__name__)


DEFAULT_CHANNELS = [
    "tursunovlar_uz",
    "AlisherIsaev_blogi",
    "Avazovalisher",
    "ibrahimGulyamov",
]


@dataclass
class ChannelPost:
    channel: str
    message_id: int
    date: str
    text: str
    link: Optional[str] = None


def _normalize_channel(value: str) -> str:
    value = (value or "").strip()
    value = value.removeprefix("https://t.me/").removeprefix("http://t.me/")
    value = value.removeprefix("@")
    value = value.split("?")[0].strip("/")
    return value


def _extract_text(message: Any) -> str:
    parts = [
        str(getattr(message, "message", "") or "").strip(),
        str(getattr(message, "text", "") or "").strip(),
        str(getattr(message, "raw_text", "") or "").strip(),
    ]
    for part in parts:
        if part:
            return part
    return ""


def _build_message_link(channel: str, message_id: int, entity: Any = None) -> Optional[str]:
    username = _normalize_channel(channel)
    if username:
        return f"https://t.me/{username}/{message_id}"
    if entity is not None:
        username = getattr(entity, "username", None) or ""
        if username:
            return f"https://t.me/{username}/{message_id}"
    return None


async def collect_channel_posts(
    client: Any,
    channels: Iterable[str] | None = None,
    limit: int = 20,
) -> List[ChannelPost]:
    """Collect recent business-post candidates from public Telegram channels."""
    posts: List[ChannelPost] = []
    for raw_channel in channels or DEFAULT_CHANNELS:
        channel = _normalize_channel(raw_channel)
        if not channel:
            continue
        try:
            entity = await client.get_entity(channel)
            async for message in client.iter_messages(entity, limit=limit):
                text = _extract_text(message)
                if not text or len(text) < 20:
                    continue
                message_id = int(getattr(message, "id", 0) or 0)
                date_obj = getattr(message, "date", None)
                date = date_obj.isoformat() if isinstance(date_obj, datetime) else str(date_obj or "")
                posts.append(
                    ChannelPost(
                        channel=channel,
                        message_id=message_id,
                        date=date,
                        text=text,
                        link=_build_message_link(channel, message_id, entity),
                    )
                )
        except Exception as exc:
            logger.warning("[RNP] Failed to collect %s: %s", channel, exc)
    return posts


def _format_posts_for_prompt(posts: List[ChannelPost], max_posts: int = 40) -> str:
    chunks: List[str] = []
    for idx, post in enumerate(posts[:max_posts], start=1):
        chunks.append(
            f"[{idx}] channel=@{post.channel} date={post.date} link={post.link or ''}\n{post.text}"
        )
    return "\n\n".join(chunks)


async def build_business_research(
    client: Any,
    user_id: int,
    db: Any = None,
    channels: Iterable[str] | None = None,
    limit: int = 20,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze public channel posts and return an RNP brief."""
    posts = await collect_channel_posts(client, channels=channels, limit=limit)
    prompt = (
        "Siz RNP (Ruka Na Pulse) biznes research agentisiz. "
        "Quyidagi Telegram kanal postlarini o'qing va biznes signallarni toping. "
        "Natija o'zbekcha, qisqa va amaliy bo'lsin.\n\n"
        "Kerakli natija:\n"
        "1) Qaysi mavzular takrorlanmoqda.\n"
        "2) Qaysi mavzular sotuv/biznes uchun foydali.\n"
        "3) Qaysi mavzular bizning Oisha uchun signal bo'la oladi.\n"
        "4) Bugun uchun eng katta foyda beradigan 'qurbaqa' nomzodi.\n"
        "5) Mana shu ma'lumotlar asosida 3 ta eng muhim keyingi qadam.\n\n"
    )
    if context:
        prompt += f"[CONTEXT]\n{context}\n\n"
    prompt += "[CHANNEL POSTS]\n" + (_format_posts_for_prompt(posts) or "No posts collected.")

    agent = ResearcherAgent(
        "rnp_researcher",
        "Siz rahbar uchun dalilga tayangan, pragmatik biznes tahlilchisiz.",
        {
            "gemini": os.environ.get("GEMINI_API_KEY", ""),
            "groq": os.environ.get("GROQ_API_KEY", ""),
        },
    )
    summary = await agent.process_task(user_id, prompt)

    frog = None
    frog_tasks: List[Dict[str, Any]] = []
    try:
        if db is None:
            from src.database import Database

            db = Database()
        conn = await db.get_connection()
        async with conn.execute(
            """
            SELECT id, title, description, priority, profit_estimate
            FROM tasks
            WHERE status = 'Pending'
            ORDER BY COALESCE(profit_estimate, 0) DESC, priority DESC, id DESC
            LIMIT 20
            """
        ) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            frog_tasks.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "priority": row[3],
                    "profit_estimate": row[4] or 0,
                }
            )
        if frog_tasks:
            frog_agent = FrogAgent()
            frog = await frog_agent.identify_frog(frog_tasks, context=summary)
    except Exception as exc:
        logger.warning("[RNP] Frog selection skipped: %s", exc)

    result = {
        "channels": [asdict(post) for post in posts],
        "summary": summary,
        "frog": _serialize_frog(frog),
        "frog_candidates": frog_tasks,
    }
    return result


def format_rnp_report(result: Dict[str, Any]) -> str:
    summary = str(result.get("summary") or "").strip()
    frog = result.get("frog") or {}
    frog_id = frog.get("most_important_task_id")
    frog_profit = frog.get("profit_estimate")
    frog_reason = frog.get("reason")
    frog_message = frog.get("motivation_message")
    report = ["<b>RNP Research</b>"]
    if summary:
        report.append(summary[:3000])
    if frog_id:
        report.append("")
        report.append(f"<b>Qurbaqa:</b> #{frog_id}")
        if frog_profit is not None:
            report.append(f"<b>Foyda prognozi:</b> ${frog_profit}")
        if frog_reason:
            report.append(f"<b>Sabab:</b> {frog_reason}")
        if frog_message:
            report.append(f"<b>Xabar:</b> {frog_message}")
    if result.get("channels"):
        report.append("")
        report.append(f"<b>Ko'rilgan postlar:</b> {len(result['channels'])}")
    return "\n".join(report)


def _serialize_frog(frog: Any) -> Optional[Dict[str, Any]]:
    if frog is None:
        return None
    if hasattr(frog, "model_dump"):
        return dict(frog.model_dump())
    if hasattr(frog, "dict"):
        return dict(frog.dict())
    return {
        "most_important_task_id": getattr(frog, "most_important_task_id", None),
        "profit_estimate": getattr(frog, "profit_estimate", None),
        "reason": getattr(frog, "reason", None),
        "motivation_message": getattr(frog, "motivation_message", None),
    }
