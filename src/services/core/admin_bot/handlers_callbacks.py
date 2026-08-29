import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
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
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()

def register_callback_handlers(self):
        @self.bot_client.on(events.CallbackQuery())
        async def callback_handler(event):
            data = event.data.decode("utf-8")
            try:
                if data.startswith("improve:"):
                    if int(event.sender_id or 0) != self.self_improvement.owner_id:
                        await event.answer("Bu qarorni faqat owner bera oladi.", alert=True)
                        return
                    parts = data.split(":", 2)
                    if len(parts) != 3:
                        await event.answer("Noto'g'ri taklif buyrug'i.", alert=True)
                        return
                    _, action, proposal_id = parts
                    changed, outcome_message, _ = await self.self_improvement.decide(
                        proposal_id,
                        action,
                        actor_id=event.sender_id,
                    )
                    await event.answer(
                        "Qaror saqlandi." if changed else outcome_message[:180],
                        alert=not changed,
                    )
                    if not changed:
                        return

                    badges = {
                        "accept": "✅ AI agent uchun qabul qilindi",
                        "defer": "⏸ 7 kunga kechiktirildi",
                        "reject": "❌ Rad etildi",
                    }
                    try:
                        from telethon.extensions import html

                        current_html = html.unparse(
                            event.message.message,
                            event.message.entities or [],
                        )
                        await event.edit(
                            current_html + f"\n\n<b>{badges[action]}</b>",
                            parse_mode="html",
                            buttons=None,
                        )
                    except Exception:
                        logger.debug(
                            "[SELF-IMPROVEMENT] Decision card edit failed",
                            exc_info=True,
                        )
                    if action == "accept":
                        await event.respond(outcome_message, parse_mode="html")
                    return

                if data.startswith(("mcp:approve:", "mcp:cancel:")):
                    from src.services.core.telegram_mcp.executor import (
                        get_default_executor,
                    )

                    executor = await get_default_executor()
                    if data.startswith("mcp:approve:"):
                        operation_id = data.removeprefix("mcp:approve:")
                        outcome = await executor.approve(operation_id, event.sender_id)
                    else:
                        operation_id = data.removeprefix("mcp:cancel:")
                        outcome = await executor.cancel(operation_id, event.sender_id)
                    await event.answer(
                        outcome.user_message,
                        alert=outcome.status in {"denied", "failed"},
                    )
                    try:
                        from telethon.extensions import html

                        current_html = html.unparse(
                            event.message.message,
                            event.message.entities or [],
                        )
                        await event.edit(
                            current_html + f"\n\n{outcome.badge}",
                            parse_mode="html",
                            buttons=None,
                        )
                    except Exception:
                        logger.debug(
                            "[ADMIN_BOT] MCP approval card edit failed",
                            exc_info=True,
                        )
                    return

                # [SECURITY] Check access for administrative callbacks
                if (
                    not self.access_manager.is_admin(event.sender_id)
                    and data != "get_id"
                ):
                    await event.answer("⚠️ Kirish rad etildi.", alert=True)
                    return

                if data == "dashboard":
                    await self.send_dashboard(event)
                elif data == "weekly_report":
                    await self.send_weekly_report(event)
                elif data == "kpi":
                    await self.send_kpi_report(event)
                elif data == "deadlines":
                    await self.send_deadline_report(event)
                elif data == "settings":
                    await self._show_settings_menu(event, edit=True)
                elif data.startswith("set_dist_mode:"):
                    new_mode = data.split(":")[1]
                    from src.settings import settings

                    settings.LEAD_DISTRIBUTION_MODE = new_mode
                    await self.db.set_state("lead_distribution_mode", new_mode)
                    await event.answer(
                        f"✅ Rejim {new_mode} ga o'zgartirildi!", alert=True
                    )
                    await self._show_settings_menu(event, edit=True)
                elif data == "get_id":
                    await event.respond(
                        f"🆔 Sizning Telegram ID: `{event.sender_id}`\nUni tizimga kiritish uchun Admin-ga bering."
                    )
                elif data == "search":
                    self.active_searches[event.sender_id] = datetime.now()
                    await event.respond(
                        "🔍 **Deep Search rejimiga xush kelibsiz!**\n\n"
                        "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\n"
                        "Oisha butun Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️"
                    )
                elif data.startswith("social_spy:"):
                    user_id = int(data.split(":")[1])
                    await self.analyze_social_history(user_id, event)
                elif data == "vps_status":
                    await self.send_vps_status(event)
                elif data == "junk_audit":
                    # Re-use junk_audit_handler logic but for callback
                    await event.answer("🧹 CRM Audit boshlandi...", alert=True)
                    try:
                        from src.services.core.enterprise_reporter import EnterpriseReporter
                        from src.services.core.crm.crm_service import CRMService

                        crm_service = CRMService()
                        reporter = EnterpriseReporter(self.db, crm_service)
                        report_msg = await reporter.get_junk_leads_report()

                        await event.respond(
                            report_msg, parse_mode="HTML", link_preview=False
                        )
                    except Exception as e:
                        logger.error(f"❌ [JUNK_AUDIT CALLBACK ERROR] {e}")
                        await event.respond(f"❌ Xato: {e}")
                elif data == "logs":
                    await self.send_recent_logs(event)
                elif data.startswith("send_draft:"):
                    # send_draft:draft_id:user_id
                    parts = data.split(":")
                    if len(parts) >= 3:
                        _, draft_id, target_uid = parts[0], parts[1], parts[2]
                        draft_text = self.pending_drafts.pop(draft_id, None)
                        if not draft_text:
                            await event.answer(
                                "⚠️ Draft topilmadi yoki muddati o'tgan.", alert=True
                            )
                            return
                        try:
                            uid = int(target_uid)
                            await self.user_client.send_message(uid, draft_text)
                            await event.answer("✅ Xabar yuborildi.", alert=False)
                            try:
                                await event.edit(
                                    event.message.message + "\n\n✅ Yuborildi"
                                )
                            except Exception as exc:
                                logger.debug("[ADMIN_BOT] send_draft: failed to edit message after send", exc_info=True)
                        except Exception as ex:
                            logger.error(f"[SEND_DRAFT] {ex}", exc_info=True)
                            await event.answer(f"⚠️ Yuborishda xato: {ex}", alert=True)
                    else:
                        await event.answer("⚠️ Noto'g'ri tugma ma'lumoti.", alert=True)
                elif data.startswith("reject_draft:"):
                    draft_id = data.split(":", 1)[1] if ":" in data else ""
                    if self.pending_drafts.pop(draft_id, None) is not None:
                        await event.answer("🗑️ Draft rad etildi.", alert=False)
                        try:
                            await event.edit(
                                event.message.message + "\n\n❌ Rad etildi"
                            )
                        except Exception as exc:
                            logger.debug("[ADMIN_BOT] reject_draft: failed to edit message after reject", exc_info=True)
                    else:
                        await event.answer(
                            "ℹ️ Draft allaqachon qayta ishlangan.", alert=True
                        )
                elif data.startswith("accept_lead:") or data.startswith("claim_lead:"):
                    # accept_lead:lead_id:user_id:manager_id or claim_lead:lead_id:user_id
                    parts = data.split(":")
                    lid_id = parts[1]
                    # Mark as claimed to stop escalation background task
                    await self.db.set_state(f"lead_claimed_{lid_id}", "true")

                    if data.startswith("accept_lead:"):
                        mgr_id = int(parts[3])
                        if event.sender_id != mgr_id:
                            await event.answer(
                                "⚠️ Bu lid sizga biriktirilmagan!", alert=True
                            )
                            return
                        await event.answer("✅ Lid qabul qilindi. Omad!", alert=False)
                    else:
                        # Claim logic
                        await self.db.set_state(
                            f"lead_manager_{lid_id}", event.sender_id
                        )
                        await event.answer("🚀 Lid sizga biriktirildi!", alert=True)

                    # Update message to show who claimed
                    sender = await event.get_sender()
                    name = getattr(sender, "first_name", "Menejer")
                    try:
                        await event.edit(
                            event.message.message + f"\n\n🤝 **Qabul qildi:** {name}"
                        )
                    except Exception as exc:
                        logger.debug("[ADMIN_BOT] accept/claim_lead: failed to edit message with claimer name", exc_info=True)
            except Exception as e:
                logger.error(f"❌ [ADMIN_BOT] CALLBACK ERROR: {str(e)}")
                await event.answer("⚠️ Xatolik yuz berdi.", alert=True)

        @self.bot_client.on(events.NewMessage())
        async def contact_card_handler(event):
            import re
            text = (event.text or "").strip()
            if not text or text.startswith("/"):
                return
            phone_match = re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                text,
            )
            if not phone_match:
                return
            digits = re.sub(r"\D", "", text)
            if not digits.startswith("998"):
                digits = "998" + digits[-9:]
            normalized = "+" + digits

            first_name = digits[-4:]
            last_name = ""
            try:
                user_data = await self._perform_global_lookup(normalized)
                if user_data:
                    first_name = user_data.get("first_name") or first_name
                    last_name = user_data.get("last_name") or ""
            except Exception as exc:
                logger.debug("[ADMIN_BOT] contact_card: global lookup failed for %s", normalized, exc_info=True)

            try:
                await event.respond(
                    file=types.InputMediaContact(
                        phone_number=normalized,
                        first_name=first_name,
                        last_name=last_name,
                        vcard="",
                    )
                )
            except Exception as exc:
                logger.warning("[CONTACT_CARD] send failed: %s", exc)
