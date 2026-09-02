"""
Aiogram dispatcher builder and factory functions.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from src.services.core.dispatcher.handlers_admin import (
    handle_aiogram_auto_status,
    handle_aiogram_chatid,
    handle_aiogram_command_center,
    handle_aiogram_finance_risks,
    handle_aiogram_oisha_stats,
    handle_aiogram_pause_auto,
    handle_aiogram_project_risks,
    handle_aiogram_resume_auto,
    handle_aiogram_sales_today,
    handle_aiogram_set_mode,
    handle_aiogram_team_capacity,
    handle_aiogram_vps_status,
)
from src.services.core.dispatcher.handlers_crm_coach import (
    handle_aiogram_crm_history,
    handle_aiogram_crm_report,
    handle_aiogram_crm_stats,
    handle_aiogram_fear_message,
    handle_aiogram_psychological_coach,
    handle_aiogram_sparring,
)

logger = logging.getLogger("AdminAiogramDispatcher")

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
    get_amocrm_client: Optional[Callable[[], Any]] = None,
    db: Any = None,
) -> Any:
    from aiogram import Dispatcher, F

    dp = Dispatcher()

    @dp.message(F.text.regexp(r"(?i)^/chatid"))
    async def _chatid(message: Any) -> None:
        await handle_aiogram_chatid(message)


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

    @dp.message(F.text.regexp(r"(?i)^/vps_status"))
    async def _vps_status(message: Any) -> None:
        await handle_aiogram_vps_status(message, is_admin=is_admin)

    @dp.message(F.text.regexp(r"(?i)^/auto_status"))
    async def _auto_status(message: Any) -> None:
        await handle_aiogram_auto_status(message, is_admin=is_admin, db=db)

    @dp.message(F.text.regexp(r"(?i)^/pause_auto"))
    async def _pause_auto(message: Any) -> None:
        await handle_aiogram_pause_auto(message, is_admin=is_admin, db=db)

    @dp.message(F.text.regexp(r"(?i)^/resume_auto"))
    async def _resume_auto(message: Any) -> None:
        await handle_aiogram_resume_auto(message, is_admin=is_admin, db=db)

    @dp.message(F.text.regexp(r"(?i)^/set_mode"))
    async def _set_mode(message: Any) -> None:
        await handle_aiogram_set_mode(message, is_admin=is_admin, db=db)

    @dp.message(F.text.regexp(r"(?i)^/(report|crm_report|kunlik_hisobot)$"))
    async def _crm_report(message: Any) -> None:
        await handle_aiogram_crm_report(
            message,
            is_admin=is_admin,
            get_amocrm_client=get_amocrm_client,
        )

    @dp.message(F.text.regexp(r"(?i)^/(stats|statistika)$"))
    async def _crm_stats(message: Any) -> None:
        await handle_aiogram_crm_stats(
            message,
            is_admin=is_admin,
            get_amocrm_client=get_amocrm_client,
        )

    @dp.message(F.text.regexp(r"(?i)^/(history|tarix)$"))
    async def _crm_history(message: Any) -> None:
        await handle_aiogram_crm_history(
            message,
            is_admin=is_admin,
        )

    @dp.message(F.text.regexp(r"(?i)^/(coach|psixolog|ruhiyat|qorquv|call_prep|pm_coach)"))
    async def _coach_cmd(message: Any) -> None:
        await handle_aiogram_psychological_coach(
            message,
            is_admin=is_admin,
        )

    @dp.message(F.text.regexp(r"(?i)^/sparring"))
    async def _sparring_cmd(message: Any) -> None:
        await handle_aiogram_sparring(
            message,
            is_admin=is_admin,
        )

    @dp.message(F.text.regexp(r"(?i)(telefon qilishga qo.rq|qilsam nima bo.ladi|telefon qilolmay|rad etsa nima|kechikishni qanday ayt|uyalyapman)"))
    async def _fear_trigger(message: Any) -> None:
        await handle_aiogram_fear_message(
            message,
            is_admin=is_admin,
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
    get_amocrm_client: Optional[Callable[[], Any]] = None,
    db: Any = None,
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
        get_amocrm_client=get_amocrm_client,
        db=db,
    )

