import structlog
from telethon import events, Button
from src.time_utils import get_local_now
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


def _register_audit_commands(self):
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_audit"))
        async def oisha_audit_handler(event):
            """Tizimning oxirgi 5 ta amalini ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            from src.api_server import system_activities

            if not system_activities:
                await event.respond(
                    "👸 Oisha: Hozircha yangi amallar bajarilmadi. Tizim kutish rejimida. 🛡️"
                )
                return

            report = "🕵️‍♀️ **OISHA: LIVE AUDIT REPORT**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for act in system_activities[-5:]:
                icon = (
                    "⚙️"
                    if act["type"] == "info"
                    else (
                        "✨"
                        if act["type"] == "success"
                        else "🤔" if act["type"] == "thinking" else "⚠️"
                    )
                )
                report += f"{icon} **{act['action']}** ({act['timestamp']})\n┗ _{act['details']}_\n\n"

            report += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 *To'liq tahlil dashboardda mavjud.*"
            )
            await event.respond(report)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_rivoj$"))
        async def oisha_self_diagnosis_handler(event):
            """Owner-triggered read-only self-improvement diagnosis."""
            if int(event.sender_id or 0) != self.self_improvement.owner_id:
                return
            await event.respond("🧬 Oisha o'zini tahlil qilmoqda...")
            try:
                outcome = await self.self_improvement.run_diagnosis(
                    force=True,
                    notify=False,
                )
                from src.services.core.oisha_self_diagnosis import OishaSelfDiagnosis

                await event.respond(
                    OishaSelfDiagnosis.format_telegram_report(outcome.proposals),
                    parse_mode="html",
                    link_preview=False,
                )
            except Exception as exc:
                logger.error("[SELF-IMPROVEMENT] Manual diagnosis failed", exc_info=True)
                await event.respond(f"❌ Diagnostika xatosi: {type(exc).__name__}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_takliflar$"))
        async def oisha_improvements_handler(event):
            """Show owner decision cards for actionable proposals."""
            if int(event.sender_id or 0) != self.self_improvement.owner_id:
                return
            try:
                await self.self_improvement.send_proposal_cards(
                    target=event.sender_id,
                    limit=5,
                )
            except Exception:
                logger.error("[SELF-IMPROVEMENT] Proposal cards failed", exc_info=True)
                await event.respond("❌ Takliflarni ochib bo'lmadi.")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/junk_audit"))
        async def junk_audit_handler(event):
            """CRM tozalik auditini (junk leads) qo'lda ishga tushirish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            await event.respond(
                "👸 **Oisha CRM Audit:** Bekorchi sdelkalar tahlil qilinmoqda... 🧹"
            )

            try:
                from src.services.core.enterprise_reporter import EnterpriseReporter
                from src.services.core.crm.crm_service import CRMService

                crm_service = CRMService()
                reporter = EnterpriseReporter(self.db, crm_service)
                report_msg = await reporter.get_junk_leads_report()

                await event.respond(report_msg, parse_mode="HTML", link_preview=False)
            except Exception as e:
                logger.error(f"❌ [JUNK_AUDIT ERROR] {e}")
                await event.respond(f"❌ Audit davomida xato yuz berdi: {e}")



def _register_plan_commands(self):
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_plan"))
        async def oisha_plan_handler(event):
            """Manual Morning Plan trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            await event.respond(
                "👸 Oisha: Mission Control ishga tushirildi. Bugungi reja tayyorlanmoqda... 🚀"
            )

            try:
                from src.services.core.proactive_worker import distribute_team_tasks

                await distribute_team_tasks(force=True)
                await event.respond(
                    "✅ Bugun uchun barcha vazifalar taqsimlandi va jamoa guruhiga yuborildi."
                )
            except Exception as e:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                await event.respond(f"❌ Xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_fact"))
        async def oisha_fact_handler(event):
            """Manual Evening Fact trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            await event.respond(
                "👸 Oisha: Kunlik Plan-Fakt tahlili boshlandi. AmoCRM raqamlarini tekshiryapman... 🕵️‍♀️"
            )

            try:
                from src.services.core.proactive_worker import send_evening_fact_report

                await send_evening_fact_report()
            except Exception as e:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                await event.respond(f"❌ Tahlil davomida xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_stats"))
        async def oisha_stats_handler(event):
            """Bugungi biznes ko'rsatkichlarni ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            from src.api_server import cached_crm_audit

            health = cached_crm_audit.get("health_score", 98)
            stats = await self.db.get_today_stats()
            msg = (
                f"📊 **OISHA: BUSINESS PERFORMANCE**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Yangi Lidlar:** `{stats.get('leads_found', 0)}` ta\n"
                f"✉️ **Xabarlar:** `{stats.get('messages_synced', 0)}` ta\n"
                f"🧹 **CRM Tozalik:** `{health}%` ({'Optimal' if health > 80 else 'Diqqat kerak' if health > 50 else 'KRITIK HOLAT'})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👸 *Oisha hozirda avtonom rejimda ishlamoqda.*"
            )
            response = build_oisha_stats_response(
                stats=stats,
                health_score=int(health or 0),
            )
            await event.respond(response.text, parse_mode=response.parse_mode)



def _register_command_center_commands(self):
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/(sales_today|bugun_sotuv|kimga_qongiroq)"))
        async def sales_priorities_handler(event):
            """Show today's seller outreach priorities from AmoCRM evidence."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            crm = getattr(self.msg_controller, "crm", None)
            amocrm = getattr(crm, "amocrm", None)
            payload = await collect_sales_today_priorities(amocrm, limit=7)
            response = build_sales_priorities_response(payload, max_items=7)
            await event.respond(response.text, parse_mode=response.parse_mode)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/(project_risks|loyiha_risk|deadline_risk)"))
        async def project_risks_handler(event):
            """Show project/deadline risks from Airtable evidence."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            crm = getattr(self.msg_controller, "crm", None)
            airtable = getattr(crm, "airtable", None)
            payload = await collect_project_delivery_risks(airtable, limit=7)
            response = build_project_risks_response(payload, max_items=7)
            await event.respond(response.text, parse_mode=response.parse_mode)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/(finance_risks|moliya_risk|pul_risk)"))
        async def finance_risks_handler(event):
            """Show project payment risks from real finance/project fields."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            crm = getattr(self.msg_controller, "crm", None)
            source = getattr(crm, "airtable", None)
            payload = await collect_finance_project_risks(source, limit=7)
            response = build_finance_risks_response(payload, max_items=7)
            await event.respond(response.text, parse_mode=response.parse_mode)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/(team_capacity|jamoa_yuklama|bandlik)"))
        async def team_capacity_handler(event):
            """Show team workload from active project assignments."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            crm = getattr(self.msg_controller, "crm", None)
            source = getattr(crm, "airtable", None)
            payload = await collect_team_capacity_snapshot(source, limit=7)
            response = build_team_capacity_response(payload, max_items=7)
            await event.respond(response.text, parse_mode=response.parse_mode)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/(command_center|oisha_center|biznes_markaz)"))
        async def command_center_handler(event):
            """Show one owner-facing Oisha command center snapshot."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            crm = getattr(self.msg_controller, "crm", None)
            project_source = getattr(crm, "airtable", None)
            payload = await collect_business_command_snapshot(
                amocrm=getattr(crm, "amocrm", None),
                project_source=project_source,
                finance_source=project_source,
                limit=3,
            )
            response = build_command_center_response(payload)
            await event.respond(response.text, parse_mode=response.parse_mode)



def _register_basic_commands(self):
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/chatid"))
        async def chatid_handler(event):
            """Guruh yoki chat ID sini qaytaradi (Hisobchi sozlash uchun)."""
            chat = await event.get_chat()
            chat_id = event.chat_id
            chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", "shaxsiy")
            reply_to = getattr(event.message, "reply_to", None)
            topic_id = getattr(reply_to, "reply_to_top_id", None) or getattr(reply_to, "reply_to_msg_id", None)
            response = build_chatid_response(
                chat_id=chat_id,
                chat_title=chat_title,
                topic_id=topic_id,
            )
            await event.respond(response.text, parse_mode=response.parse_mode)

        async def _handle_weblogin(event, sender_id: int, is_owner: bool, force_otp: bool = False) -> bool:
            raw_text = str(getattr(event, "raw_text", "") or "").strip()
            if "weblogin_" not in raw_text and not force_otp:
                return False
            sender = await event.get_sender()
            first_name = getattr(sender, "first_name", None) or "Foydalanuvchi"
            username = getattr(sender, "username", None) or str(sender_id)
            web_role = "owner" if is_owner else ("admin" if self.access_manager.is_admin(sender_id) else "targetolog")
            from src.api.web_auth_store import approve_tg_login_state, issue_tg_otp_code
            next_url = "/api/marketing/capi/console"
            if "weblogin_" in raw_text:
                state_code = raw_text.split("weblogin_", 1)[1].strip().split()[0]
                next_url = approve_tg_login_state(state_code, int(sender_id), username, first_name, role=web_role) or next_url
            otp_code = issue_tg_otp_code(int(sender_id), username, first_name, role=web_role, next_url=next_url)
            from src.api.security import _session_secret
            import jwt as pyjwt, time as _time
            jwt_secret = _session_secret()
            buttons = None
            if jwt_secret:
                m_jwt = pyjwt.encode(
                    {"sub": username, "uid": int(sender_id), "name": first_name, "role": web_role, "purpose": "magic_login", "exp": int(_time.time()) + 86400},
                    jwt_secret, algorithm="HS256",
                )
                m_url = f"https://oisha.jonbranding.uz/api/auth/telegram/login?magic={m_jwt}&next={next_url}"
                buttons = [[Button.url("🚀 Shaxsiy Kabinetni Ochish", m_url)]]
            await event.respond(
                f"🔐 **Salom, {first_name}!**\n\n"
                f"🔢 **6-xonali kirish kodi:** `{otp_code}`\n"
                "*(Agar boshqa kompyuter/brauzerdan kirayotgan bo'lsangiz, ushbu 6 ta raqamni saytga yozing — yoki ochiq brauzeringiz avtomatik kirdi)*",
                buttons=buttons,
            )
            return True

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/start"))
        async def start_handler(event):
            sender_id = event.sender_id
            logger.info(f"🚀 [ADMIN_BOT] POINT A: /start received from {sender_id}")
            try:
                is_owner = int(sender_id or 0) in {int(self.access_manager.owner_id or 0), 150074828}
                if await _handle_weblogin(event, int(sender_id or 0), is_owner):
                    return
                role = resolve_start_role(
                    sender_id=sender_id,
                    owner_id=self.access_manager.owner_id,
                    get_role=self.access_manager.get_role,
                )
                if role == "GUEST":
                    await _handle_weblogin(event, int(sender_id or 0), is_owner=False, force_otp=True)
                    return
                role_name = self.access_manager.get_role_name(role)
                response = build_start_response(
                    role_name=role_name,
                    now_text=get_local_now().strftime("%d.%m.%Y %H:%M"),
                )
                buttons = self._get_buttons_for_role(role)
                buttons.append([Button.url("🌐 AmoCRM-ga o'tish", "https://jonbranding.amocrm.ru")])
                await event.respond(response.text, buttons=buttons)
            except Exception as e:
                logger.error(f"❌ [ADMIN_BOT] START HANDLER ERROR: {str(e)}", exc_info=True)
                await event.respond(f"⚠️ **Tizimda texnik xatolik:**\n`{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/vps_status"))
        async def vps_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_vps_status(event)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/logs"))
        async def logs_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_recent_logs(event)


def register_command_handlers(self):
    _register_audit_commands(self)
    _register_plan_commands(self)
    _register_command_center_commands(self)
    _register_basic_commands(self)
