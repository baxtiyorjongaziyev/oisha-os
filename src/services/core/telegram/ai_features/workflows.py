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
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.services.core.telegram.ai_features.models import (
    build_input_rich_message,
    extract_write_access_allowed_context,
    rich_expandable_blockquote,
    rich_paragraph,
    rich_section_heading,
)
from src.services.core.telegram.ai_features.rich_builders import (
    build_input_checklist,
    extract_checklist_tasks_done,
    extract_stopped_message_generation,
    rich_table,
)

logger = logging.getLogger(__name__)

OISHA_PRIVATE_TOPICS: Tuple[Tuple[str, str, int], ...] = (
    ("finance", "Moliya va Soliq", 9367192),       # Green
    ("sales", "Sotuv va AmoCRM", 7322096),         # Blue
    ("marketing", "Marketing va CAPI", 16766590),  # Yellow
    ("hr", "HR va Davomat", 13338331),             # Violet
    ("system", "Tizim va Alertlar", 16478047),     # Red
)

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


async def send_oisha_kpi_report(
    client: Any,
    chat_id: int | str,
    *,
    title: str,
    subtitle: str,
    kpis: Sequence[Tuple[str, Any]],
    table_headers: Sequence[str],
    table_rows: Sequence[Sequence[Any]],
    numeric_cols: Sequence[int] = (),
    progress_done: int = 0,
    progress_total: int = 0,
    details_text: Optional[str] = None,
    is_private_chat: bool = True,
    message_thread_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Send interactive HTML Widget (10.4) in private chat or Rich Table (10.1/10.5) in groups."""
    if is_private_chat and isinstance(chat_id, int) and chat_id > 0:
        from src.services.core.telegram.widgets import templates as wt
        from src.services.core.telegram.widgets.client import WidgetClient
        from src.services.core.telegram.widgets.sender import send_widget_or_text

        def _build_html() -> str:
            parts = [wt.header(title, subtitle), wt.kpi_row(kpis)]
            if progress_total > 0:
                parts.append(wt.progress("Progress", progress_done, progress_total))
            if table_headers and table_rows:
                parts.append(wt.table(table_headers, table_rows, numeric=numeric_cols))
            parts.append(wt.action_bar([("Yangilash", "refresh_kpi"), ("Tasdiqlash", "ack")], secondary=(0,)))
            return wt.render_widget(*parts, interactive=True)

        kpi_line = " | ".join(f"{k}: {v}" for k, v in kpis)
        fallback = f"<b>{title}</b>\n{subtitle}\n{kpi_line}"
        res = await send_widget_or_text(
            client=WidgetClient(client),
            chat_id=chat_id,
            module="kpi_report",
            build_html=_build_html,
            fallback_text=fallback,
            send_text=lambda cid, txt: client.finalize_streamed_message(
                int(cid), txt, message_thread_id=message_thread_id
            ),
            caption=f"{title}: {subtitle}"[:200],
            allow_queries=True,
        )
        return {"ok": res.success, "mode": res.metadata.get("mode"), "tool": res.tool_name}

    blocks: List[Dict[str, Any]] = [
        rich_section_heading(title),
        rich_paragraph(subtitle),
    ]
    if kpis:
        blocks.append(rich_paragraph(" • ".join(f"{k}: {v}" for k, v in kpis)))
    if table_headers and table_rows:
        blocks.append(
            rich_table(
                table_headers,
                table_rows,
                numeric_cols=numeric_cols,
                is_bordered=True,
                is_striped=True,
                is_compact=True,
            )
        )
    if details_text:
        blocks.append(
            rich_expandable_blockquote(
                [rich_paragraph(details_text)],
                credit="Oisha-OS",
            )
        )
    rich_msg = build_input_rich_message(blocks=blocks)
    return await client.send_rich_message(
        chat_id,
        rich_msg,
        message_thread_id=message_thread_id,
    )


async def handle_botnews_service_update(
    update: Dict[str, Any],
    *,
    token: str = "",
    db: Any = None,
) -> Optional[Dict[str, Any]]:
    """Handle Bot API 9.1/10.3/10.5 service updates (stopped draft, botinvite greeting, checklist sync)."""
    stopped = extract_stopped_message_generation(update)
    if stopped is not None:
        return {"ok": True, "handled": True, "update_type": "stopped_message_generation", "stopped": stopped}

    wa_ctx = extract_write_access_allowed_context(update)
    if wa_ctx is not None:
        chat_id = (wa_ctx.get("chat") or {}).get("id")
        first_name = (wa_ctx.get("from_user") or {}).get("first_name") or "hamkasb"
        greeted = False
        if token and chat_id:
            try:
                from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client
                await TelegramBotAPI10Client(token).call(
                    "sendMessage",
                    {"chat_id": chat_id, "text": f"Assalomu alaykum, {first_name}! Oisha-OS tizimiga xush kelibsiz."},
                )
                greeted = True
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

