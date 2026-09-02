"""
Admin Bot Callback Query handlers for interactive buttons.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from telethon import events
import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


async def _handle_improvement_callback(self, event: Any, data: str) -> None:
    if int(event.sender_id or 0) != self.self_improvement.owner_id:
        await event.answer("Bu qarorni faqat owner bera oladi.", alert=True)
        return
    parts = data.split(":", 2)
    if len(parts) != 3:
        await event.answer("Noto'g'ri taklif buyrug'i.", alert=True)
        return
    _, action, proposal_id = parts
    changed, outcome_message, _ = await self.self_improvement.decide(
        proposal_id, action, actor_id=event.sender_id
    )
    await event.answer("Qaror saqlandi." if changed else outcome_message[:180], alert=not changed)
    if not changed:
        return

    badges = {"accept": "✅ AI agent uchun qabul qilindi", "defer": "⏸ 7 kunga kechiktirildi", "reject": "❌ Rad etildi"}
    try:
        from telethon.extensions import html
        current_html = html.unparse(event.message.message, event.message.entities or [])
        await event.edit(current_html + f"\n\n<b>{badges[action]}</b>", parse_mode="html", buttons=None)
    except Exception:
        logger.debug("[SELF-IMPROVEMENT] Decision card edit failed", exc_info=True)
    if action == "accept":
        await event.respond(outcome_message, parse_mode="html")


async def _handle_mcp_callback(self, event: Any, data: str) -> None:
    from src.services.core.telegram_mcp.executor import get_default_executor
    executor = await get_default_executor()
    if data.startswith("mcp:approve:"):
        outcome = await executor.approve(data.removeprefix("mcp:approve:"), event.sender_id)
    else:
        outcome = await executor.cancel(data.removeprefix("mcp:cancel:"), event.sender_id)
    await event.answer(outcome.user_message, alert=outcome.status in {"denied", "failed"})
    try:
        from telethon.extensions import html
        current_html = html.unparse(event.message.message, event.message.entities or [])
        await event.edit(current_html + f"\n\n{outcome.badge}", parse_mode="html", buttons=None)
    except Exception:
        logger.debug("[ADMIN_BOT] MCP approval card edit failed", exc_info=True)


async def _handle_draft_callbacks(self, event: Any, data: str) -> None:
    if data.startswith("send_draft:"):
        parts = data.split(":")
        if len(parts) >= 3:
            draft_text = self.pending_drafts.pop(parts[1], None)
            if not draft_text:
                await event.answer("⚠️ Draft topilmadi yoki muddati o'tgan.", alert=True)
                return
            try:
                await self.user_client.send_message(int(parts[2]), draft_text)
                await event.answer("✅ Xabar yuborildi.", alert=False)
                await event.edit(event.message.message + "\n\n✅ Yuborildi")
            except Exception as ex:
                logger.error(f"[SEND_DRAFT] {ex}", exc_info=True)
                await event.answer(f"⚠️ Yuborishda xato: {ex}", alert=True)
    elif data.startswith("reject_draft:"):
        draft_id = data.split(":", 1)[1] if ":" in data else ""
        if self.pending_drafts.pop(draft_id, None) is not None:
            await event.answer("🗑️ Draft rad etildi.", alert=False)
            await event.edit(event.message.message + "\n\n❌ Rad etildi")
        else:
            await event.answer("ℹ️ Draft allaqachon qayta ishlangan.", alert=True)


async def _handle_lead_claim_callbacks(self, event: Any, data: str) -> None:
    parts = data.split(":")
    lid_id = parts[1]
    await self.db.set_state(f"lead_claimed_{lid_id}", "true")

    if data.startswith("accept_lead:"):
        mgr_id = int(parts[3])
        if event.sender_id != mgr_id:
            await event.answer("⚠️ Bu lid sizga biriktirilmagan!", alert=True)
            return
        await event.answer("✅ Lid qabul qilindi. Omad!", alert=False)
    else:
        await self.db.set_state(f"lead_manager_{lid_id}", event.sender_id)
        await event.answer("🚀 Lid sizga biriktirildi!", alert=True)

    sender = await event.get_sender()
    name = getattr(sender, "first_name", "Menejer")
    try:
        await event.edit(event.message.message + f"\n\n🤝 **Qabul qildi:** {name}")
    except Exception:
        pass


async def _handle_admin_menu_callbacks(self, event: Any, data: str) -> None:
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
    elif data == "vps_status":
        await self.send_vps_status(event)
    elif data == "logs":
        await self.send_recent_logs(event)
    elif data.startswith("social_spy:"):
        await self.analyze_social_history(int(data.split(":")[1]), event)
    elif data.startswith("set_dist_mode:"):
        mode = data.split(":")[1]
        from src.settings import settings
        settings.LEAD_DISTRIBUTION_MODE = mode
        await self.db.set_state("lead_distribution_mode", mode)
        await event.answer(f"✅ Rejim {mode} ga o'zgartirildi!", alert=True)
        await self._show_settings_menu(event, edit=True)


def register_callback_handlers(self):
    @self.bot_client.on(events.CallbackQuery())
    async def callback_handler(event):
        data = event.data.decode("utf-8")
        try:
            if data.startswith("improve:"):
                await _handle_improvement_callback(self, event, data)
            elif data.startswith(("mcp:approve:", "mcp:cancel:")):
                await _handle_mcp_callback(self, event, data)
            elif not self.access_manager.is_admin(event.sender_id) and data != "get_id":
                await event.answer("⚠️ Kirish rad etildi.", alert=True)
            elif data == "get_id":
                await event.respond(f"🆔 Sizning Telegram ID: `{event.sender_id}`\nUni tizimga kiritish uchun Admin-ga bering.")
            elif data.startswith(("send_draft:", "reject_draft:")):
                await _handle_draft_callbacks(self, event, data)
            elif data.startswith(("accept_lead:", "claim_lead:")):
                await _handle_lead_claim_callbacks(self, event, data)
            else:
                await _handle_admin_menu_callbacks(self, event, data)
        except Exception as e:
            logger.error(f"[CALLBACK ERROR] {e}", exc_info=True)
            await event.answer("❌ Xatolik yuz berdi.", alert=True)
