from telethon import events
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

class AdminHandlersMixin:
    def register_all_handlers(self):
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

        # [AUDIT: UI/UX] Case-insensitive and robust command matching
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/start"))
        async def start_handler(event):
            sender_id = event.sender_id
            # [CRITICAL LOG]
            logger.info("🚀" * 10)
            logger.info(f"🚀 [ADMIN_BOT] POINT A: /start received from {sender_id}")

            try:
                # [AUDIT: ARCHITECT] Identity Check (Fail-safe)
                is_owner = int(sender_id or 0) in {
                    int(self.access_manager.owner_id or 0),
                    150074828,
                }
                logger.info(
                    f"🚀 [ADMIN_BOT] POINT B: is_owner={is_owner} (Config Owner: {self.access_manager.owner_id})"
                )

                role = resolve_start_role(
                    sender_id=sender_id,
                    owner_id=self.access_manager.owner_id,
                    get_role=self.access_manager.get_role,
                )
                role_name = self.access_manager.get_role_name(role)
                logger.info(
                    f"🚀 [ADMIN_BOT] POINT C: role={role}, role_name={role_name}"
                )

                welcome_msg = (
                    f"🌟 **Oisha-OS Enterprise v2.1**\n\n"
                    f"Assalomu alaykum, **{role_name}**!\n"
                    f"Tizimga muvaffaqiyatli kirdingiz. Boshqaruv pulti tayyor.\n\n"
                    f"📅 Bugun: `{get_local_now().strftime('%d.%m.%Y %H:%M')}`"
                )

                response = build_start_response(
                    role_name=role_name,
                    now_text=get_local_now().strftime("%d.%m.%Y %H:%M"),
                )

                # Rollarga ko'ra tugmalar
                buttons = self._get_buttons_for_role(role)

                # AmoCRM link har doim pastda bo'lsin
                if role != "GUEST":
                    buttons.append(
                        [
                            Button.url(
                                "🌐 AmoCRM-ga o'tish", "https://jonbranding.amocrm.ru"
                            )
                        ]
                    )

                logger.info(
                    f"🚀 [ADMIN_BOT] POINT D: Responding to {sender_id} with {len(buttons)} buttons"
                )
                await event.respond(response.text, buttons=buttons)
                logger.info(f"✅ [ADMIN_BOT] POINT E: Response SENT to {sender_id}")

            except Exception as e:
                logger.error(
                    f"❌ [ADMIN_BOT] START HANDLER ERROR: {str(e)}", exc_info=True
                )
                await event.respond(f"⚠️ **Tizimda texnik xatolik:**\n`{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/vps_status"))
        async def vps_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_vps_status(event)

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

        # Telefon raqam yuborilsa — kontakt kartochkasi qaytaradi (НАПИСАТЬ + ДОБАВИТЬ)
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

        # [ENTERPRISE: SEARCH] Phone number listener for Deep Search and Direct Admin lookup
        @self.bot_client.on(events.NewMessage())
        async def phone_handler(event):
            sender_id = event.sender_id

            # Check if user is in active searches mode
            is_active = sender_id in self.active_searches
            if is_active:
                if (datetime.now() - self.active_searches[sender_id]).total_seconds() > 300:
                    del self.active_searches[sender_id]
                    is_active = False

            # If not in active searches, only allow direct lookup in private chat for admins
            if not is_active:
                if event.is_private and self.access_manager.is_admin(sender_id):
                    pass
                else:
                    return

            import re

            text = (event.text or "").strip()
            # Bare phone number — contact_card_handler handles it, skip here
            if re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                text,
            ):
                return

            phone_match = re.search(
                r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}", text
            )
            if phone_match:
                phone = phone_match.group(0)
                if sender_id in self.active_searches:
                    del self.active_searches[sender_id]

                wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
                try:
                    data = await self._perform_global_lookup(phone)
                    if data:
                        res_msg = (
                            f"✅ **Mijoz topildi!**\n\n"
                            f"👤 **Ism:** {data['first_name']} {data.get('last_name', '') or ''}\n"
                            f"🆔 **ID:** [{data['user_id']}](tg://user?id={data['user_id']})\n"
                            f"🔗 **Profil:** [Link](tg://user?id={data['user_id']})\n"
                        )
                        if data.get("username"):
                            res_msg += f"📱 **Username:** @{data['username']}\n"
                        await wait_msg.edit(res_msg)
                    else:
                        await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.")
                except Exception as e:
                    logger.error(f"❌ [SEARCH ERROR] {e}")
                    await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/search(?:\s+(.+))?"))
        async def manual_search_command_handler(event):
            sender_id = event.sender_id
            if not self.access_manager.is_admin(sender_id):
                return

            import re
            match_arg = event.pattern_match.group(1)
            if not match_arg:
                # If they just type /search, activate active_searches mode
                self.active_searches[sender_id] = datetime.now()
                await event.respond(
                    "🔍 **Qidiruv rejimiga xush kelibsiz!**\n\n"
                    "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\n"
                    "Oisha Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️"
                )
                return

            phone = match_arg.strip()
            wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
            try:
                data = await self._perform_global_lookup(phone)
                if data:
                    res_msg = (
                        f"✅ **Mijoz topildi!**\n\n"
                        f"👤 **Ism:** {data['first_name']} {data.get('last_name', '') or ''}\n"
                        f"🆔 **ID:** [{data['user_id']}](tg://user?id={data['user_id']})\n"
                        f"🔗 **Profil:** [Link](tg://user?id={data['user_id']})\n"
                    )
                    if data.get("username"):
                        res_msg += f"📱 **Username:** @{data['username']}\n"
                    await wait_msg.edit(res_msg)
                else:
                    await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.")
            except Exception as e:
                logger.error(f"❌ [SEARCH ERROR] {e}")
                await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/logs"))
        async def logs_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_recent_logs(event)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_stats"))
        async def sync_stats_handler(event):
            if not self.access_manager.is_admin(event.sender_id):
                return

            wait_msg = await event.respond(
                "📊 **Sinxronizatsiya hisoboti tayyorlanmoqda...**\nIltimos, kuting. 👸🛡️"
            )

            try:
                # 1. Telegram kontaktlar sonini olish
                tg_contacts = await self.user_client(
                    functions.contacts.GetContactsRequest(hash=0)
                )
                tg_count = len(tg_contacts.users)

                # 2. Google (Bazadagi) kontaktlar sonini olish
                google_count = await self.db.get_synced_contacts_count()

                res_msg = (
                    f"📊 **Oisha Sync Hisoboti**\n\n"
                    f"🔹 **Telegram Kontaktlar:** `{tg_count}` ta\n"
                    f"🔸 **Google Contacts (Synced):** `{google_count}` ta\n\n"
                    f"💡 *Ma'lumot:* Google Contacts'ga faqat telefon raqami bor mijozlar sinxronlanadi. 🤴🛡️"
                )
                await wait_msg.edit(res_msg)
            except Exception as e:
                logger.error(f"❌ [SYNC STATS ERROR] {e}")
                await wait_msg.edit(
                    f"⚠️ **Xatolik:** Hisobot tayyorlashda xato yuz berdi: `{e}`"
                )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_contacts_tg"))
        async def sync_contacts_tg_handler(event):
            sender_id = event.sender_id
            if not self.access_manager.is_admin(sender_id):
                return

            wait_msg = await event.respond(
                "🔍 **Google Contacts sinxronizatsiyasi boshlandi...**\n"
                "Iltimos, kuting. Oisha barcha kontaktlarni yuklamoqda va Telegram akkauntlari bilan taqqoslamoqda. 👸🛡️"
            )

            # Run as a background task to prevent blocking the main Telegram thread
            asyncio.create_task(self._run_gcontacts_telegram_sync(event, wait_msg))

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_position"))
        async def set_position_handler(event):
            """Xodimga rasmiy pozitsiya biriktirish: /set_position @username PM"""
            if not self.access_manager.is_admin(event.sender_id):
                return

            args = event.message.text.split()
            target_user = None
            position = None

            # 1. Reply orqali bo'lsa
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_user = await reply_msg.get_sender()
                position = " ".join(args[1:]) if len(args) > 1 else None
            # 2. Argumentlar orqali bo'lsa (@username position)
            elif len(args) >= 3:
                # Username orqali qidirish (Userbot orqali)
                target_username = args[1].replace("@", "")
                try:
                    target_user = await self.user_client.get_entity(target_username)
                    position = " ".join(args[2:])
                except Exception as e:
                    await event.respond(f"❌ User topilmadi: {e}")
                    return

            if not target_user or not position:
                await event.respond(
                    "⚠️ **Xato qo'llanildi!**\n\nTo'g'ri ko'rinishi:\n1. Reply qilib: `/set_position PM`\n2. Mention bilan: `/set_position @username PM`"
                )
                return

            from src.services.utils.team_hub import TeamHub

            TeamHub.set_position(target_user.id, position)

            # Username-ni ham DB-da yangilab qo'yamiz (Accountability uchun kerak)
            await self.db.upsert_user(
                target_user.id,
                first_name=target_user.first_name,
                username=target_user.username,
                position=position,
            )

            await event.respond(
                f"✅ **Muvaffaqiyatli!**\n👤 {target_user.first_name} endi rasman **{position}** pozitsiyasida.\nOisha uni har kuni 9:00 va 18:00da nazorat qiladi. 👸🛡️"
            )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/topic_info"))
        async def topic_info_handler(event):
            """Guruhdagi Topic ID raqamini aniqlash uchun."""
            chat_id = event.chat_id
            thread_id = event.message.reply_to_msg_id

            msg = (
                f"👸 **Mavzu ma'lumotlari:**\n\n"
                f"🔹 **Group ID:** `{chat_id}`\n"
                f"🔸 **Topic ID (Thread):** `{thread_id or 'General (Asosiy)'}`\n\n"
                f"💡 Ushbu Topic ID-ni `.env` faylida sozlash uchun foydalaning."
            )
            await event.respond(msg)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_distribution"))
        async def set_distribution_handler(event):
            """Lidlarni taqsimlash rejimini o'zgartirish: /set_distribution CLAIM yoki ROUND_ROBIN"""
            if not self.access_manager.is_admin(event.sender_id):
                return

            args = event.message.text.split()
            if len(args) < 2:
                await event.respond(
                    "⚠️ **Rejimni tanlang:** `/set_distribution CLAIM` yoki `ROUND_ROBIN`"
                )
                return

            mode = args[1].upper()
            if mode not in ["CLAIM", "ROUND_ROBIN"]:
                await event.respond(
                    "❌ Noto'g'ri rejim. Faqat `CLAIM` yoki `ROUND_ROBIN` mumkin."
                )
                return

            from src.settings import settings

            settings.LEAD_DISTRIBUTION_MODE = mode
            await self.db.set_state("lead_distribution_mode", mode)

            await event.respond(
                f"✅ **Muvaffaqiyatli!**\nLidlarni taqsimlash rejimi **{mode}** ga o'zgartirildi."
            )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/add_manager"))
        async def add_manager_handler(event):
            """Yangi menejer qo'shish: /add_manager 12345678 yoki reply orqali"""
            if not self.access_manager.is_admin(event.sender_id):
                return

            target_id = None
            args = event.message.text.split()

            # 1. Reply orqali bo'lsa
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
            # 2. ID orqali bo'lsa
            elif len(args) >= 2:
                try:
                    target_id = int(args[1])
                except ValueError:
                    await event.respond("❌ ID raqam bo'lishi kerak.")
                    return

            if not target_id:
                await event.respond(
                    "⚠️ **Qo'llanma:**\n1. Menejer xabariga reply qilib `/add_manager` deb yozing.\n2. Yoki ID-sini yozing: `/add_manager 12345678`"
                )
                return

            from src.settings import settings

            if target_id not in settings.SALES_MANAGER_IDS:
                settings.SALES_MANAGER_IDS.append(target_id)
                # DB-da ham saqlaymiz
                current_managers = await self.db.get_state("sales_managers", "")
                manager_list = (
                    [int(i) for i in current_managers.split(",") if i]
                    if current_managers
                    else []
                )
                if target_id not in manager_list:
                    manager_list.append(target_id)
                    await self.db.set_state(
                        "sales_managers", ",".join(map(str, manager_list))
                    )

                await event.respond(f"✅ **Menejer qo'shildi!** (ID: `{target_id}`)")
            else:
                await event.respond("ℹ️ Bu menejer allaqachon ro'yxatda bor.")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/managers"))
        async def managers_list_handler(event):
            """Menejerlar ro'yxatini ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            from src.settings import settings

            if not settings.SALES_MANAGER_IDS:
                await event.respond("📋 **Menejerlar ro'yxati bo'sh.**")
                return

            msg = "📋 **Menejerlar ro'yxati:**\n\n"
            for i, mid in enumerate(settings.SALES_MANAGER_IDS, 1):
                msg += f"{i}. `ID: {mid}`\n"

            await event.respond(msg)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/night_shift"))
        async def night_shift_handler(event):
            """CRM tozalash rejimini qo'lda ishga tushirish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            await event.respond(
                "👸 **Night Shift ishga tushirildi...**\nAmoCRM'dagi dublikatlar va qotib qolgan lidlar tozalanmoqda. 🧹"
            )

            if self.night_shift:
                success = await self.night_shift.run_cleanup()
                if success:
                    await event.respond(
                        "✅ **Night Shift yakunlandi!**\nBarcha lidlar audit qilindi va keraksizlari belgilandi. 👸🛡️"
                    )
                else:
                    await event.respond("❌ Night Shift jarayonida xatolik yuz berdi.")
            else:
                await event.respond("⚠️ Night Shift xizmati faollashtirilmagan.")

        # ─── AUTO-REPLY KILL SWITCH & MODE CONTROL (Phase 2.1) ────────────
        from src.services.core import auto_reply_gate as _arg

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/pause_auto"))
        async def pause_auto_handler(event):
            """Auto-reply kill-switch YOQADI (bot darhol jim bo'ladi)."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                await self.db.set_state(_arg.FLAG_KILL_SWITCH, "false")
                await event.respond(
                    "🛑 **Auto-reply PAUSED**\n"
                    "Kill-switch faollashtirildi — bot avtomatik javob bermaydi.\n"
                    "Qayta yoqish uchun: `/resume_auto`"
                )
                logger.warning(
                    f"[ADMIN_BOT] Auto-reply PAUSED by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/resume_auto"))
        async def resume_auto_handler(event):
            """Auto-reply kill-switch'ni o'chiradi — rejim qaytadan faollashadi."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                await self.db.set_state(_arg.FLAG_KILL_SWITCH, "true")
                mode = await self.db.get_state(_arg.FLAG_MODE) or os.environ.get(
                    "AUTO_REPLY_MODE", "off"
                )
                await event.respond(
                    "▶️ **Auto-reply RESUMED**\n"
                    f"Joriy rejim: `{mode}`\n"
                    "Status: `/auto_status`"
                )
                logger.info(
                    f"[ADMIN_BOT] Auto-reply RESUMED by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/auto_status"))
        async def auto_status_handler(event):
            """Auto-reply rejimi, kill-switch va VIP threshold ko'rsatish."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                mode_db = await self.db.get_state(_arg.FLAG_MODE)
                mode_env = os.environ.get("AUTO_REPLY_MODE", "off")
                mode = (mode_db or mode_env).lower()
                kill_raw = await self.db.get_state(_arg.FLAG_KILL_SWITCH)
                if kill_raw is None:
                    kill_active = False  # default: allowed (True in gate => not killed)
                else:
                    kill_active = str(kill_raw).lower() in ("0", "false", "off", "no")
                vip = os.environ.get("VIP_LEAD_SCORE_THRESHOLD", "80")
                triggers = ", ".join(_arg.ESCALATION_TRIGGERS)
                status_icon = "🛑" if kill_active else "✅"
                await event.respond(
                    f"{status_icon} **AUTO-REPLY STATUS**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Rejim (DB): `{mode_db or '—'}`\n"
                    f"Rejim (env default): `{mode_env}`\n"
                    f"Faol rejim: `{mode}`\n"
                    f"Kill-switch: `{'ON (bot jim)' if kill_active else 'OFF (bot faol)'}`\n"
                    f"VIP lead threshold: `{vip}`\n"
                    f"Escalation triggers: {triggers}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Rejim o'zgartirish: `/set_mode off|shadow|vip_only|live`"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_mode(\s+\S+)?"))
        async def set_mode_handler(event):
            """Auto-reply rejimini o'zgartirish: off | shadow | vip_only | live."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            text = (event.message.text or "").strip()
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await event.respond(
                    "ℹ️ **Foydalanish:** `/set_mode <rejim>`\n"
                    f"Ruxsat etilgan rejimlar: {', '.join(_arg.VALID_MODES)}"
                )
                return
            new_mode = parts[1].strip().lower()
            if new_mode not in _arg.VALID_MODES:
                await event.respond(
                    f"❌ Notanish rejim: `{new_mode}`\n"
                    f"Ruxsat etilganlar: {', '.join(_arg.VALID_MODES)}"
                )
                return
            try:
                await self.db.set_state(_arg.FLAG_MODE, new_mode)
                await event.respond(
                    f"🔁 **Rejim yangilandi:** `{new_mode}`\n"
                    f"Tekshirish: `/auto_status`"
                )
                logger.warning(
                    f"[ADMIN_BOT] Auto-reply mode set to '{new_mode}' by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/juma_send"))
        async def juma_send_handler(event):
            """Manual Juma Mubarak outreach trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            if not self.juma_notifier:
                await event.respond("❌ JumaNotifier sozlanmagan!")
                return

            await event.respond(
                "🕌 **Juma Mubarak outreach boshlanmoqda...**\nFonda barcha kursdoshlarga tabriklar yuboriladi. 👸🛡️"
            )

            # Start in background
            asyncio.create_task(self.juma_notifier.check_and_send())
            logger.info(
                f"🕌 [ADMIN_BOT] Juma outreach triggered manually by {event.sender_id}"
            )

        # [GOD MODE] Inline Search Handler — works in any group without bot membership
        @self.bot_client.on(events.InlineQuery())
        async def inline_search_handler(event):
            import re, uuid
            from telethon.tl.types import (
                InputBotInlineResult,
                InputBotInlineMessageMediaContact,
            )

            query = event.text.strip()
            if not query:
                return

            # Telefon raqam bo'lsa — kontakt kartochkasi qaytaramiz
            phone_match = re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                query,
            )
            if phone_match:
                digits = re.sub(r"\D", "", query)
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
                    logger.debug("[ADMIN_BOT] inline_search: global lookup failed for %s", normalized, exc_info=True)

                contact_result = InputBotInlineResult(
                    id=str(uuid.uuid4()),
                    type="contact",
                    title=f"{first_name} {last_name}".strip(),
                    description=normalized,
                    send_message=InputBotInlineMessageMediaContact(
                        phone_number=normalized,
                        first_name=first_name,
                        last_name=last_name,
                        vcard="",
                    ),
                )
                await event.answer([contact_result])
                return

            # DB dan qidirish
            results = []
            async with await self.db.get_connection() as conn:
                async with conn.execute(
                    """
                    SELECT user_id, first_name, username, phone, intent
                    FROM users
                    WHERE first_name LIKE ? OR username LIKE ? OR phone LIKE ?
                    LIMIT 10
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%"),
                ) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                uid, name, uname, phone, intent = row
                intent_icon = "🔥" if intent == "HOT_LEAD" else "📋"
                text = (
                    f"👸 **Oisha-OS Lead Profile**\n"
                    f"──────────────────────\n"
                    f"👤 **Ism:** {name}\n"
                    f"📱 **Username:** @{uname or 'yoq'}\n"
                    f"📞 **Tel:** `{phone or 'Nomaʼlum'}`\n"
                    f"🎯 **Intent:** {intent_icon} {intent or 'Aniqlanyapti'}\n"
                    f"──────────────────────\n"
                    f"🔗 [ID: {uid} Profiliga o'tish](tg://user?id={uid})"
                )
                results.append(
                    event.builder.article(
                        title=f"{name} (@{uname or '?'})",
                        description=f"Status: {intent or 'Lead'} | Tel: {phone or '?'}",
                        text=text,
                        buttons=[Button.url("💬 Chatni ochish", f"tg://user?id={uid}")],
                    )
                )

            await event.answer(results)

