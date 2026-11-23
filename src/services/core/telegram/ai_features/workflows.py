"""
High-ROI Oisha-OS business workflows powered by Telegram Bot API 9.0–10.5:
1. Owner Private Topics + Sidebar bootstrap (Bot API 9.3 + 9.4 + 10.5)
2. Lead Profile Auto-Enrichment from personal channel & user_rating (Bot API 9.3 + 10.0)
3. Native Telegram Checklists for ClientChecklist (Bot API 9.1/9.2)
4. Team Member Role Tagging in workgroups (Bot API 9.5)
5. Adaptive KPI Report: HTML Widget in 1-on-1 chat (10.4) or Rich Table in groups (10.1/10.3/10.5)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.services.core.telegram.ai_features.kpi_reports import (  # noqa: F401
    send_oisha_kpi_report,
)
from src.services.core.telegram.ai_features.models import (
    extract_write_access_allowed_context,
)
from src.services.core.telegram.ai_features.rich_builders import (
    build_input_checklist,
    extract_checklist_tasks_done,
    extract_stopped_message_generation,
)

logger = logging.getLogger(__name__)

OISHA_PRIVATE_TOPICS: Tuple[Tuple[str, str, int], ...] = (
    ("finance", "Moliya va Soliq", 9367192),       # Green
    ("sales", "Sotuv va AmoCRM", 7322096),         # Blue
    ("marketing", "Marketing va CAPI", 16766590),  # Yellow
    ("hr", "HR va Davomat", 13338331),             # Violet
    ("system", "Tizim va Alertlar", 16478047),     # Red
)


def get_owner_topic_id(section: str) -> Optional[int]:
    """Resolve OWNER_TOPIC_<SECTION> thread ID from environment (None if unset)."""
    raw = os.getenv(f"OWNER_TOPIC_{section.strip().upper()}", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return None

INDUSTRY_KEYWORDS: Mapping[str, Tuple[str, ...]] = {
    "education": ("kurs", "akademiya", "taʼlim", "talim", "school", "ustoz", "ielts"),
    "medical": ("klinika", "shifoxona", "stomatologiya", "med", "doktor", "salomatlik"),
    "retail": ("doʻkon", "dokon", "savdo", "market", "kiyim", "mebel", "optom"),
    "construction": ("qurilish", "building", "uy-joy", "kvartira", "remont", "developer"),
    "food": ("restoran", "kafe", "oshxona", "food", "yetkazib berish", "bakery"),
    "it_services": ("it", "dasturlash", "crm", "ai", "agentlik", "marketing", "smm"),
}


async def bootstrap_owner_private_topics(
    client: Any,
    owner_chat_id: int,
    *,
    bot_username: Optional[str] = None,
) -> Dict[str, Any]:
    """Enable Bot API 10.5 Topic Sidebar and create the 5 Oisha-OS private topics."""
    await client.set_my_settings(
        has_topics_enabled=True,
        has_topic_sidebar=True,
        allows_users_to_create_topics=True,
        callback_query_mode="auto",
        supports_guest_queries=True,
        can_communicate_with_bots=True,
    )
    clean_bot = (bot_username or "").strip().lstrip("@")
    created: Dict[str, Dict[str, Any]] = {}
    for key, title, icon_color in OISHA_PRIVATE_TOPICS:
        topic = await client.create_forum_topic(
            owner_chat_id,
            title,
            icon_color=icon_color,
        )
        thread_id = topic.get("message_thread_id")
        deep_link = (
            f"https://t.me/{clean_bot}/{thread_id}"
            if clean_bot and thread_id
            else None
        )
        created[key] = {
            "name": title,
            "message_thread_id": thread_id,
            "icon_color": icon_color,
            "deep_link": deep_link,
        }
    return {"owner_chat_id": owner_chat_id, "topics": created}


async def enrich_lead_from_personal_channel(
    client: Any,
    user_id: int,
    *,
    user_info: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Fetch a lead's personal channel posts (Bot API 10.0) and detect business context."""
    messages = await client.get_user_personal_chat_messages(user_id, limit=limit)
    texts: List[str] = []
    channel_title: Optional[str] = None
    channel_username: Optional[str] = None
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        chat = msg.get("chat") or msg.get("sender_chat") or {}
        if isinstance(chat, dict):
            channel_title = channel_title or chat.get("title")
            channel_username = channel_username or chat.get("username")
        txt = str(msg.get("text") or msg.get("caption") or "").strip()
        if txt:
            texts.append(txt)

    combined_lower = " ".join(texts).lower()
    detected_industries = [
        industry
        for industry, words in INDUSTRY_KEYWORDS.items()
        if any(w in combined_lower for w in words)
    ]
    info = user_info or {}
    return {
        "user_id": user_id,
        "channel_title": channel_title,
        "channel_username": channel_username,
        "message_count": len(texts),
        "detected_industries": detected_industries,
        "recent_snippets": [t[:160] for t in texts[:3]],
        "user_rating": info.get("user_rating"),
        "birthdate": info.get("birthdate"),
    }


async def send_client_native_checklist(
    client: Any,
    *,
    business_connection_id: str,
    chat_id: int | str,
    client_name: str,
    items: Sequence[Dict[str, Any]],
    stage_title: str = "Loyiha cheklisti",
) -> Dict[str, Any]:
    """Convert Oisha-OS ClientChecklist rows into a Bot API 9.1 native checklist."""
    tasks: List[Tuple[int, str]] = []
    for idx, row in enumerate(items[:30], start=1):
        task_id = int(row.get("id") or idx)
        label = str(row.get("label") or row.get("item_key") or f"Qadam {idx}").strip()
        tasks.append((task_id, label[:100]))
    checklist = build_input_checklist(
        f"{client_name} — {stage_title}",
        tasks,
        others_can_add_tasks=False,
        others_can_mark_tasks_as_done=True,
    )
    return await client.send_checklist(
        business_connection_id,
        chat_id,
        checklist,
    )


async def sync_team_member_tags(
    client: Any,
    chat_id: int | str,
    role_mapping: Mapping[int, str],
) -> Dict[str, Any]:
    """Assign custom role tags (Hunter, Setter, Farmer, Moliyachi) via Bot API 9.5."""
    applied: Dict[int, str] = {}
    failed: Dict[int, str] = {}
    for uid, tag in role_mapping.items():
        clean_tag = (tag or "").strip()[:16]
        try:
            ok = await client.set_chat_member_tag(chat_id, int(uid), tag=clean_tag)
            if ok:
                applied[int(uid)] = clean_tag
            else:
                failed[int(uid)] = "returned_false"
        except Exception as exc:
            failed[int(uid)] = str(exc)
    return {"chat_id": chat_id, "applied": applied, "failed": failed}


_STOPPED_DRAFTS: set[Tuple[int, int]] = set()


def mark_draft_stopped(chat_id: int, draft_id: int) -> None:
    """Record that the user pressed Stop on a streamed draft (Bot API 10.3)."""
    if len(_STOPPED_DRAFTS) > 1000:
        _STOPPED_DRAFTS.clear()
    _STOPPED_DRAFTS.add((int(chat_id), int(draft_id)))


def consume_draft_stopped(chat_id: int, draft_id: int) -> bool:
    """Return True and clear if the user stopped generation for (chat_id, draft_id)."""
    key = (int(chat_id), int(draft_id))
    if key in _STOPPED_DRAFTS:
        _STOPPED_DRAFTS.discard(key)
        return True
    return False


async def handle_botnews_service_update(
    update: Dict[str, Any],
    *,
    token: str = "",
    db: Any = None,
) -> Optional[Dict[str, Any]]:
    """Handle Bot API 9.1/10.3/10.5 service updates (stopped draft, botinvite greeting, checklist sync)."""
    stopped = extract_stopped_message_generation(update)
    if stopped is not None:
        cid = (stopped.get("chat") or {}).get("id")
        did = stopped.get("draft_id")
        if cid is not None and did is not None:
            mark_draft_stopped(int(cid), int(did))
        return {"ok": True, "handled": True, "update_type": "stopped_message_generation", "stopped": stopped}

    wa_ctx = extract_write_access_allowed_context(update)
    if wa_ctx is not None:
        from src.services.core.dispatcher.handlers_welcome import (
            build_owner_notice_from_dict,
            build_welcome_text,
            owner_id_from_env,
        )
        chat_id = (wa_ctx.get("chat") or {}).get("id")
        user = wa_ctx.get("from_user") or {}
        invited = bool(wa_ctx.get("inviter"))
        greeted = False
        if token and chat_id:
            try:
                from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client
                client = TelegramBotAPI10Client(token)
                await client.call(
                    "sendMessage",
                    {"chat_id": chat_id, "text": build_welcome_text(user.get("first_name"), invited=invited),
                     "parse_mode": "HTML"},
                )
                greeted = True
                owner_id = owner_id_from_env()
                if invited and owner_id and user.get("id") != owner_id:
                    try:
                        await client.call("sendMessage", {"chat_id": owner_id, "text": build_owner_notice_from_dict(user)})
                    except Exception as exc:
                        logger.debug("[TG-AI] owner invite notice failed: %s", exc)
            except Exception as exc:
                logger.debug("[TG-AI] write_access_allowed greeting failed: %s", exc)
        return {"ok": True, "handled": True, "update_type": "write_access_allowed", "greeted": greeted, "context": wa_ctx}

    chk_ctx = extract_checklist_tasks_done(update)
    if chk_ctx is not None:
        synced_count = 0
        if db is not None:
            try:
                from src.services.core.client_checklist import ClientChecklist
                actor_id = (chk_ctx.get("from_user") or {}).get("id")
                synced_count = await ClientChecklist(db).sync_from_telegram_tasks_done(
                    chk_ctx.get("marked_as_done_task_ids") or [],
                    chk_ctx.get("marked_as_not_done_task_ids") or [],
                    completed_by=actor_id,
                )
            except Exception as exc:
                logger.debug("[TG-AI] checklist DB sync skipped: %s", exc)
        return {"ok": True, "handled": True, "update_type": "checklist_tasks_done", "synced_count": synced_count, "checklist": chk_ctx}

    return None

