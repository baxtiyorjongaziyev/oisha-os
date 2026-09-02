import os
import logging
import asyncio
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

class TeamActionsMixin:
    async def _send_stars_invoice(
        self, user_id: int, product_id: str
    ) -> Dict[str, Any]:
        """Telegram Stars invoice yuborish (bot.send_invoice)."""
        # Bu amal userbot.py dagi context.bot ga muhtoj.
        # Shuning uchun bu tool faqat "pending" ni qaytaradi,
        # va userbot.py o'zi invoice yuboradi.
        products = getattr(self.config, "DIGITAL_PRODUCTS", {})
        p_info = products.get(product_id, {})
        if not p_info:
            return {"success": False, "error": f"Mahsulot topilmadi: {product_id}"}

        # DB ga log
        try:
            if hasattr(self.db, "log_purchase"):
                await self._db_call(
                    "log_purchase", user_id, product_id, p_info.get("price", 0)
                )
        except Exception as e:
            logger.warning(f"[TOOL] Stars purchase log xato: {e}")

        await self._log_action(
            user_id,
            "send_stars_invoice",
            {"product_id": product_id, "price": p_info.get("price")},
            success=True,
        )

        return {
            "success": True,
            "pending_action": "send_invoice",
            "user_id": user_id,
            "product_id": product_id,
            "product_title": p_info.get("title", "Mahsulot"),
            "price": p_info.get("price", 0),
            "message": f"Invoice tayyor: {p_info.get('title')} — {p_info.get('price')} Stars",
        }

    async def _forward_to_crm_group(
        self, user_id: int, quality: str, summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """CRM Telegram guruhiga lead yuborish."""
        crm_group_id = getattr(self.config, "CRM_GROUP_ID", None)
        crm_topic_id = getattr(self.config, "CRM_TOPIC_ID", None)

        if not crm_group_id:
            return {"success": False, "error": "CRM_GROUP_ID sozlanmagan"}

        # Bazadan mijoz ma'lumotlarini olish
        user_data = await self._db_call("get_user_info", user_id) or {}
        name = user_data.get("first_name", "Noma'lum")
        phone = user_data.get("phone", "—")
        username = user_data.get("username", "")
        business = user_data.get("business_type", "—")
        service = user_data.get("service_type", "—")

        quality_emoji = {
            "Sifatli": "🔥",
            "Oddiy": "✅",
            "Unknown": "🔸",
            "Sifatsiz": "❌",
        }.get(quality, "🔸")

        crm_msg = (
            f"{quality_emoji} <b>{quality.upper()} LEAD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mijoz:</b> {name}"
            f"{(' (@' + username + ')') if username else ''}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📞 <b>Telefon:</b> {phone}\n"
            f"💼 <b>Biznes:</b> {business}\n"
            f"🎯 <b>Xizmat:</b> {service}\n"
        )
        if summary:
            crm_msg += f"━━━━━━━━━━━━━━━━━━━━\n💬 <b>Qisqacha:</b> <i>{summary}</i>"

        try:
            # Topic ID mantiqi: Agar lead uchun maxsus topic bo'lsa, o'shanga yuborish
            # Hozircha default topic_id config dan olinadi
            topic_id = crm_topic_id
            from src.services.core.tool_adapters import (
                send_group_message_with_fallback,
            )

            await send_group_message_with_fallback(
                self.bot_app.bot,
                chat_id=crm_group_id,
                text=crm_msg,
                parse_mode="HTML",
                thread_id=topic_id,
            )
            # Mark as forwarded
            if hasattr(self.db, "mark_lead_forwarded"):
                await self._db_call("mark_lead_forwarded", user_id)
            await self._log_action(
                user_id, "forward_to_crm_group", {"quality": quality}, success=True
            )
            return {"success": True, "message": f"CRM guruhiga yuborildi ({quality})"}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Bazadan mijoz profilini olish."""
        try:
            data = await self._db_call("get_user_info", user_id)
            if data:
                return {"success": True, "profile": data}
            else:
                return {
                    "success": True,
                    "profile": None,
                    "message": "Yangi foydalanuvchi — bazada yo'q",
                }
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_team_members(self) -> Dict[str, Any]:
        """Jamoa a'zolarini bazadan olish."""
        try:
            members = await self._db_call("get_team_roles")
            return {"success": True, "members": members}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _assign_task_to_human(
        self,
        assigned_to: int,
        title: str,
        description: str,
        deadline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inson xodimga vazifa biriktirish."""
        try:
            # 1. Vazifani bazaga qo'shish
            if hasattr(self.db, "add_task"):
                task_id = await self._db_call(
                    "add_task",
                    assigned_to=assigned_to,
                    description=f"{title}: {description}",
                    deadline=deadline or "Belgilanmagan",
                )
            else:
                task_id = None

            # 2. Xodimga xabar yuborish
            member_info = await self._db_call("get_user_info", assigned_to)
            member_name = (
                member_info.get("first_name", "Xodim") if member_info else "Xodim"
            )

            notification = (
                f"📌 <b>Yangi Vazifa Biriktirildi!</b>\n\n"
                f"👤 <b>Xodim:</b> {member_name}\n"
                f"📝 <b>Vazifa:</b> {title}\n"
                f"📖 <b>Tafsilot:</b> {description}\n"
                f"📅 <b>Muddat:</b> {deadline or 'Tezda'}\n\n"
                f"<i>Bot tomonidan avtomatik yaratildi.</i>"
            )

            await self.bot_app.bot.send_message(
                chat_id=assigned_to, text=notification, parse_mode="HTML"
            )

            await self._log_action(
                assigned_to, "assign_task_to_human", {"title": title}, success=True
            )
            return {
                "success": True,
                "message": f"Vazifa {member_name}ga biriktirildi va xabar berildi.",
                "task_id": task_id,
            }
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _sherlock_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Mijozning profilini Scouter orqali tahlil qilish."""
        from src.services.utils.scouter import Scouter

        if not self._scouter:
            # Session path logic
            session_path = os.path.join("data", "userbot_session")

            self._scouter = Scouter(session_path=session_path)

        try:
            dosye = await self._scouter.get_user_dosye(user_id)
            if dosye:
                await self._log_action(
                    user_id, "sherlock_user_profile", {"found": True}, success=True
                )
                return {"success": True, "dosye": dosye}
            else:
                return {
                    "success": False,
                    "error": "Profil ma'lumotlarini olib bo'lmadi (ehtimol maxfiylik sozalamalari tufayli).",
                }
        except Exception as e:
            logger.error(f"[TOOL] Sherlock error: {e}")
            return {"success": False, "error": str(e)}

    async def _log_action(
        self,
        user_id: Optional[int],
        action_type: str,
        action_data: dict,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Agent amalini DB ga yozish."""
        try:
            payload = (
                action_data if not error else {"data": action_data, "error": error}
            )
            # Database logging can be async
            await self.db.log_agent_action(user_id, action_type, payload, success)
        except Exception as e:
            logger.warning(f"[AGENT LOG] Xato: {e}")

    async def _get_airtable_projects(
        self,
        stage_filter: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Airtable dan loyihalar ro'yxatini olish."""
        try:
            from src.services.core.airtable_sync import AirtableSync
            sync = AirtableSync()
            records = await asyncio.to_thread(sync.get_projects)
            projects = []
            for r in records:
                fields = r.get("fields", {})
                stage = str(
                    fields.get("Bosqich")
                    or fields.get("Stage")
                    or fields.get("Status")
                    or ""
                )
                if stage_filter and stage_filter.lower() not in stage.lower():
                    continue
                projects.append({
                    "name": fields.get("Loyiha nomi") or fields.get("Name") or r.get("id"),
                    "stage": stage,
                    "deadline": fields.get("Deadline") or fields.get("Muddat") or "",
                    "manager": fields.get("PM") or fields.get("Mas'ul") or "",
                    "client": fields.get("Mijoz") or fields.get("Client") or "",
                })
            return {"success": True, "projects": projects[:limit], "count": len(projects[:limit])}
        except Exception as e:
            logger.error(f"[TOOL] get_airtable_projects error: {e}")
            return {"success": False, "error": str(e)}

    async def _get_today_stats(self) -> Dict[str, Any]:
        """Bugungi statistika: yangi lidlar, muddati o'tgan loyihalar."""
        import datetime
        stats: Dict[str, Any] = {}
        today = datetime.date.today().isoformat()
        try:
            fetch_fn = (
                self.amocrm.get_leads_detailed
                if hasattr(self.amocrm, "get_leads_detailed")
                else self.amocrm.get_leads
            )
            leads = await asyncio.to_thread(fetch_fn, limit=50)
            today_start = int(
                datetime.datetime.combine(datetime.date.today(), datetime.time.min).timestamp()
            )
            stats["new_leads_today"] = sum(
                1 for l in leads if (l.get("created_at") or 0) >= today_start
            )
            stats["total_active_leads"] = len(leads)
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            stats["crm_error"] = str(e)
        try:
            from src.services.core.airtable_sync import AirtableSync
            sync = AirtableSync()
            overdue = await asyncio.to_thread(sync.get_overdue_projects)
            stats["overdue_projects"] = len(overdue)
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            stats["airtable_error"] = str(e)
        stats["date"] = today
        return {"success": True, **stats}
