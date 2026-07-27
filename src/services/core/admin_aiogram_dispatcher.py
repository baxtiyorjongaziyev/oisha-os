"""Aiogram admin dispatcher skeleton for the bot-account migration.

This module does not start polling or own updates by itself. Boot code can wire
it behind an explicit feature flag once Telethon bot handlers are ready to move.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.time_utils import get_local_now


class AiogramCallbackEventAdapter:
    """Expose the small Telethon callback surface used by Hisobchi."""

    def __init__(self, callback: Any):
        self.callback = callback
        self.data = getattr(callback, "data", None)

    async def answer(self, text: str = "") -> None:
        await self.callback.answer(text)

    async def edit(
        self,
        text: Optional[str] = None,
        *,
        parse_mode: Optional[str] = None,
        buttons: Any = None,
    ) -> None:
        message = getattr(self.callback, "message", None)
        if message is None:
            return
        kwargs: dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode.upper()
        if buttons is not None:
            from src.services.core.telegram.bot_runtime import (
                _coerce_aiogram_inline_keyboard,
            )

            kwargs["reply_markup"] = _coerce_aiogram_inline_keyboard(buttons)
        await message.edit_text(text or getattr(message, "text", "") or "", **kwargs)


def register_hisobchi_aiogram_callbacks(
    dispatcher: Any,
    *,
    engine: Any,
) -> None:
    """Route every Hisobchi inline approval callback through Aiogram."""
    from aiogram import F
    from src.services.core.hisobchi_approval import handle_callback

    prefixes = ("happrove:", "hedit:", "hskip:", "hcat:", "howner:", "hback:")

    @dispatcher.callback_query(F.data.startswith(prefixes))
    async def _hisobchi_callback(callback: Any) -> None:
        data = str(getattr(callback, "data", "") or "")
        event = AiogramCallbackEventAdapter(callback)
        try:
            await handle_callback(data, event, engine)
        except Exception:
            await event.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.")


async def handle_aiogram_chatid(message: Any) -> None:
    chat = getattr(message, "chat", None)
    reply_to = getattr(message, "reply_to_message", None)
    topic_id = (
        getattr(message, "message_thread_id", None)
        or getattr(reply_to, "message_thread_id", None)
        or getattr(reply_to, "message_id", None)
    )
    response = build_chatid_response(
        chat_id=int(getattr(chat, "id", 0) or 0),
        chat_title=(
            getattr(chat, "title", None)
            or getattr(chat, "first_name", None)
            or "shaxsiy"
        ),
        topic_id=topic_id,
    )
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_start(
    message: Any,
    *,
    owner_id: int,
    get_role: Callable[[int], Optional[str]],
    get_role_name: Callable[[str], str],
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    role = resolve_start_role(
        sender_id=sender_id,
        owner_id=owner_id,
        get_role=get_role,
    )
    response = build_start_response(
        role_name=get_role_name(role),
        now_text=get_local_now().strftime("%d.%m.%Y %H:%M"),
    )
    await message.answer(response.text)


async def handle_aiogram_oisha_stats(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_today_stats,
    cached_crm_audit: dict,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    response = build_oisha_stats_response(
        stats=await get_today_stats(),
        health_score=int((cached_crm_audit or {}).get("health_score", 98) or 0),
    )
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_sales_today(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_sales_today_priorities: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    if get_sales_today_priorities is None:
        payload = {
            "status": "source_unavailable",
            "source": "amocrm",
            "items": [],
            "reason": "sales_priority_source_not_wired",
        }
    else:
        payload = await get_sales_today_priorities()
    response = build_sales_priorities_response(payload, max_items=7)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_project_risks(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_project_delivery_risks: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    if get_project_delivery_risks is None:
        payload = {
            "status": "source_unavailable",
            "source": "airtable",
            "items": [],
            "reason": "project_risk_source_not_wired",
        }
    else:
        payload = await get_project_delivery_risks()
    response = build_project_risks_response(payload, max_items=7)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_finance_risks(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_finance_project_risks: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    if get_finance_project_risks is None:
        payload = {
            "status": "source_unavailable",
            "source": "project_finance",
            "items": [],
            "reason": "finance_risk_source_not_wired",
        }
    else:
        payload = await get_finance_project_risks()
    response = build_finance_risks_response(payload, max_items=7)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_team_capacity(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_team_capacity: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    if get_team_capacity is None:
        payload = {
            "status": "source_unavailable",
            "source": "project_assignments",
            "items": [],
            "reason": "team_capacity_source_not_wired",
        }
    else:
        payload = await get_team_capacity()
    response = build_team_capacity_response(payload, max_items=7)
    await message.answer(response.text, parse_mode=response.parse_mode)


async def handle_aiogram_command_center(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_command_center: Optional[Callable[[], Any]] = None,
) -> None:
    sender = getattr(message, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    if not is_admin(sender_id):
        return
    if get_command_center is None:
        payload = {
            "status": "partial",
            "sections": {},
            "summary": {
                "ready_sections": 0,
                "total_sections": 4,
                "attention_items": 0,
                "unavailable_sections": ["command_center"],
            },
        }
    else:
        payload = await get_command_center()
    response = build_command_center_response(payload)
    await message.answer(response.text, parse_mode=response.parse_mode)


def build_admin_aiogram_dispatcher(
    *,
    owner_id: int,
    get_role: Callable[[int], Optional[str]],
    get_role_name: Callable[[str], str],
    is_admin: Callable[[int], bool],
    get_today_stats,
    cached_crm_audit: dict,
    get_sales_today_priorities: Optional[Callable[[], Any]] = None,
    get_project_delivery_risks: Optional[Callable[[], Any]] = None,
    get_finance_project_risks: Optional[Callable[[], Any]] = None,
    get_team_capacity: Optional[Callable[[], Any]] = None,
    get_command_center: Optional[Callable[[], Any]] = None,
) -> Any:
    from aiogram import Dispatcher, F

    dp = Dispatcher()

    @dp.message(F.text.regexp(r"(?i)^/chatid"))
    async def _chatid(message: Any) -> None:
        await handle_aiogram_chatid(message)

    @dp.message(F.text.regexp(r"(?i)^/start"))
    async def _start(message: Any) -> None:
        await handle_aiogram_start(
            message,
            owner_id=owner_id,
            get_role=get_role,
            get_role_name=get_role_name,
        )

    @dp.message(F.text.regexp(r"(?i)^/oisha_stats"))
    async def _stats(message: Any) -> None:
        await handle_aiogram_oisha_stats(
            message,
            is_admin=is_admin,
            get_today_stats=get_today_stats,
            cached_crm_audit=cached_crm_audit,
        )

    @dp.message(F.text.regexp(r"(?i)^/(sales_today|bugun_sotuv|kimga_qongiroq)"))
    async def _sales_today(message: Any) -> None:
        await handle_aiogram_sales_today(
            message,
            is_admin=is_admin,
            get_sales_today_priorities=get_sales_today_priorities,
        )

    @dp.message(F.text.regexp(r"(?i)^/(project_risks|loyiha_risk|deadline_risk)"))
    async def _project_risks(message: Any) -> None:
        await handle_aiogram_project_risks(
            message,
            is_admin=is_admin,
            get_project_delivery_risks=get_project_delivery_risks,
        )

    @dp.message(F.text.regexp(r"(?i)^/(finance_risks|moliya_risk|pul_risk)"))
    async def _finance_risks(message: Any) -> None:
        await handle_aiogram_finance_risks(
            message,
            is_admin=is_admin,
            get_finance_project_risks=get_finance_project_risks,
        )

    @dp.message(F.text.regexp(r"(?i)^/(team_capacity|jamoa_yuklama|bandlik)"))
    async def _team_capacity(message: Any) -> None:
        await handle_aiogram_team_capacity(
            message,
            is_admin=is_admin,
            get_team_capacity=get_team_capacity,
        )

    @dp.message(F.text.regexp(r"(?i)^/(command_center|oisha_center|biznes_markaz)"))
    async def _command_center(message: Any) -> None:
        await handle_aiogram_command_center(
            message,
            is_admin=is_admin,
            get_command_center=get_command_center,
        )

    return dp


def maybe_build_admin_aiogram_dispatcher(
    *,
    enabled: bool,
    owner_id: int,
    get_role: Callable[[int], Optional[str]],
    get_role_name: Callable[[str], str],
    is_admin: Callable[[int], bool],
    get_today_stats,
    cached_crm_audit: dict,
    get_sales_today_priorities: Optional[Callable[[], Any]] = None,
    get_project_delivery_risks: Optional[Callable[[], Any]] = None,
    get_finance_project_risks: Optional[Callable[[], Any]] = None,
    get_team_capacity: Optional[Callable[[], Any]] = None,
    get_command_center: Optional[Callable[[], Any]] = None,
) -> Any:
    if not enabled:
        return None
    return build_admin_aiogram_dispatcher(
        owner_id=owner_id,
        get_role=get_role,
        get_role_name=get_role_name,
        is_admin=is_admin,
        get_today_stats=get_today_stats,
        cached_crm_audit=cached_crm_audit,
        get_sales_today_priorities=get_sales_today_priorities,
        get_project_delivery_risks=get_project_delivery_risks,
        get_finance_project_risks=get_finance_project_risks,
        get_team_capacity=get_team_capacity,
        get_command_center=get_command_center,
    )
