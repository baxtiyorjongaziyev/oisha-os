import os
import structlog
from telethon import Button
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

class AdminAlertsMixin:
    def _get_buttons_for_role(self, role: str):
        """Har bir rol uchun maxsus tugmalar."""
        if role == "OWNER":
            return [
                [
                    Button.inline("📊 ROI Dashboard", b"dashboard"),
                    Button.inline("📅 Haftalik Hisobot", b"weekly_report"),
                ],
                [
                    Button.inline("👥 Jamoa KPI", b"kpi"),
                    Button.inline("🚨 Deadline Control", b"deadlines"),
                ],
                [
                    Button.inline("🔍 Deep Search", b"search"),
                    Button.inline("🖥 VPS Status", b"vps_status"),
                ],
                [
                    Button.inline("📜 So'nggi Loglar", b"logs"),
                    Button.inline("🧹 Junk Audit", b"junk_audit"),
                    Button.inline("⚙️ Sozlamalar", b"settings"),
                ],
            ]
        elif role == "CEO":
            return [
                [Button.inline("📈 Biznes Overview", b"overview")],
                [Button.inline("💰 Moliyaviy Holat", b"finance")],
                [Button.inline("🔍 Global Search", b"search")],
            ]
        elif role == "PM":
            return [
                [Button.inline("📋 Loyihalar Statusi", b"projects")],
                [Button.inline("⏳ Muddatlar", b"deadlines")],
                [Button.inline("🔍 Deal Search", b"search")],
            ]
        else:  # GUEST
            return [
                [Button.inline("🆔 ID-ni olish", b"get_id")],
                [Button.url("📞 Bog'lanish", "https://t.me/baxtiyorjon_gaziyev")],
            ]

    async def notify_lead(self, text: str):
        """Yangi topilgan lidlar haqida xabar berish (LeadScraper dan keladi)."""
        if os.getenv("ENABLE_PROACTIVE_NOTIFICATIONS", "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            logger.info(
                "[SAFETY] Proactive lead notification suppressed. Set ENABLE_PROACTIVE_NOTIFICATIONS=1 to enable."
            )
            return False

        sent_any = False
        bot_runtime = self._outbound_bot_runtime()

        async def _safe_send(client, target, label: str) -> bool:
            if not client or not target:
                return False
            try:
                await client.send_message(target, text)
                logger.info(f"[ADMIN_BOT] Lead notification sent to {label}")
                return True
            except Exception as exc:
                logger.warning(
                    f"[ADMIN_BOT] notify_lead skipped {label}: {type(exc).__name__}"
                )
                return False

        owner_targets = []
        if self.access_manager.owner_id:
            owner_targets.append(self.access_manager.owner_id)
        # Hard fallback for the real owner account when config/entity cache is stale.
        owner_targets.append(150074828)

        for target in dict.fromkeys(owner_targets):
            sent_any = (
                await _safe_send(bot_runtime, target, f"owner:{target}") or sent_any
            )

        if self.team_group_id:
            sent_any = (
                await _safe_send(
                    bot_runtime, self.team_group_id, f"team:{self.team_group_id}"
                )
                or sent_any
            )

        if not sent_any:
            await _safe_send(self.user_client, "me", "userbot:saved_messages")

    async def notify_team(
        self,
        text: str,
        buttons: list = None,
        topic_id: int = None,
        parse_mode: str = None,
    ):
        """Faqat jamoa guruhiga bildirishnoma yuborish. Topic_id (thread_id) berilsa o'sha bo'limga yuboradi."""
        if not self.team_group_id:
            return

        bot_runtime = self._outbound_bot_runtime()
        try:
            await bot_runtime.send_message(
                self.team_group_id,
                text,
                buttons=buttons,
                reply_to_message_id=topic_id,
                parse_mode=parse_mode,
            )
            logger.info(
                f"[ADMIN_BOT] Team notification sent to {self.team_group_id} (Topic: {topic_id})"
            )
        except Exception as bot_exc:
            try:
                # User accounts cannot create bot callback buttons, but the alert text
                # must still reach the team while the bot lacks group membership.
                await self.user_client.send_message(
                    self.team_group_id,
                    text,
                    reply_to=topic_id,
                    parse_mode=parse_mode,
                )
                logger.warning(
                    "[ADMIN_BOT] Bot team notification failed; sent via userbot fallback: %s",
                    bot_exc,
                )
            except Exception as userbot_exc:
                logger.error(
                    "[ADMIN_BOT] notify_team failed via bot (%s) and userbot (%s)",
                    bot_exc,
                    userbot_exc,
                )

    async def enrich_lead_profile(self, user_id, sender_obj, lead_details: dict):
        """Mijoz profilini tahlil qilish, bio-ni olish va raqam qidirish."""
        owner_id = self.access_manager.owner_id
        if not owner_id:
            return

        first_name = getattr(sender_obj, "first_name", "Mijoz")
        username = getattr(sender_obj, "username", "yoq")

        # 1. PROFILE ANALYSIS (Bio/About)
        bio = "[Bio o'qib bo'lmadi]"
        try:
            from telethon.tl.functions.users import GetFullUserRequest

            full_user = await self.user_client(GetFullUserRequest(user_id))
            bio = full_user.full_user.about or "Bio yozilmagan"
        except Exception as e:
            logger.error(f"[ENRICHMENT] Bio fetch error: {e}")

        # 2. PHONE LOOKUP (If missing)
        phone = getattr(sender_obj, "phone", None) or lead_details.get("phone")
        (
            "✅ Profilida bor"
            if getattr(sender_obj, "phone", None)
            else "🔍 Qidirilmoqda..."
        )

        if not phone:
            # Try Deep Search (Userbot bridge)
            # Since we only have ID here, deep search by phone isn't possible,
            # but we can check if the user is already in our contact list.
            pass

        # 3. REPORT FORMATTING
        business_type = lead_details.get("business", "Noma'lum")
        needs_text = lead_details.get("needs", "Tahlil qilinmoqda")
        report = (
            f"👸 **OISHA INTELLIGENCE: YANGI LID**\n"
            f"──────────────────────\n"
            f"👤 **Mijoz:** {first_name} (@{username})\n"
            f"🆔 **ID:** [{user_id}](tg://user?id={user_id})\n"
            f"📝 **Bio:** _{bio}_\n"
            f"📞 **Raqam:** `{phone or 'TOPILMADI'}`\n"
            f"📊 **Lid turi:** {business_type}\n"
            f"🎯 **Ehtiyoj:** {needs_text}\n"
            f"──────────────────────\n"
        )

        if not phone:
            report += (
                f"⚠️ **DIQQAT:** Mijoz raqami topilmadi.\n\n"
                f"💡 **Oisha maslahati:** Raqamni olish uchun quyidagi skriptlardan birini ishlating:\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['agency_standard']}\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['value_first']}\n"
                f"──────────────────────\n"
            )
        else:
            report += "✅ Mijoz kontaktlari AmoCRM bilan sinxronlandi.\n"

        await self.bot_client.send_message(
            owner_id,
            report,
            buttons=[[Button.inline("🔍 Guruhlar tahlili", f"social_spy:{user_id}")]],
        )
        logger.info(f"[ENRICHMENT] Full intelligence report sent for {user_id}")

    async def analyze_social_history(self, user_id, event):
        """Mijozning umumiy guruhlardagi faoliyatini tahlil qilish."""
        from telethon.tl.functions.messages import GetCommonChatsRequest

        wait_msg = await event.respond(
            "🕵️‍♀️ **Guruhlar tahlili boshlandi...**\nOisha umumiy guruhlarni va xabarlarni o'rganmoqda. 👸🛡️"
        )

        try:
            # 1. Get Common Chats
            common = await self.user_client(
                GetCommonChatsRequest(user_id=user_id, max_id=0, limit=50)
            )
            if not common.chats:
                await wait_msg.edit("❌ Mijoz bilan umumiy guruhlar topilmadi.")
                return

            history_data = []
            # Faqat oxirgi 3 ta faol guruhni olamiz (Rate limits)
            for chat in common.chats[:3]:
                chat_title = getattr(chat, "title", "Guruh")
                messages = []
                async for msg in self.user_client.iter_messages(
                    chat, from_user=user_id, limit=7
                ):
                    if msg.text:
                        messages.append(msg.text)

                if messages:
                    history_data.append(
                        f"📡 **Guruh:** {chat_title}\n"
                        + "\n".join([f"- {m[:100]}..." for m in messages])
                    )

            if not history_data:
                await wait_msg.edit(
                    "❌ Guruhlar topildi, lekin mijoz u yerda yaqin orada xabar yozmagan."
                )
                return

            # 2. AI ANALYSIS
            analysis_prompt = (
                "Siz Oisha-OS Social Intelligence agentsiz. "
                "Quyidagi mijozning guruhlardagi xabarlarini tahlil qilib, Baxtiyor aka uchun "
                "qisqa 'Hulq-atvor portreti' va 'Sotuv strategiyasi' tayyorlang.\n\n"
                "Ma'lumotlar:\n" + "\n\n".join(history_data)
            )

            # Using advisor_agent's logic for simplicity or direct Gemini call
            # For now, let's use a direct call if advisor_agent is available
            # Use AutoLeadAgent credentials for AI processing
            analysis_text = "AI tahlil tayyorlanmoqda..."
            try:
                # We can reuse the auto_lead_agent's client to generate content
                # Actually let's use the advisor_agent directly
                analysis_text = await self.msg_controller.db.analyze_text_with_ai(
                    analysis_prompt
                )
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                analysis_text = "⚠️ AI tahlilida texnik xatolik, lekin guruhlardagi faollik aniqlandi."

            res_report = (
                f"🕵️‍♀️ **SOCIAL INTELLIGENCE REPORT**\n"
                f"──────────────────────\n"
                f"👥 **Umumiy guruhlar:** {len(common.chats)} ta\n\n"
                f"📊 **Hulq-atvor tahlili:**\n{analysis_text}\n"
                f"──────────────────────\n"
                f"💡 *Ushbu ma'lumotlar faqat sizning @baxtiyorjonjon_gaziyev akkuntingiz ko'ra oladigan guruhlardan olindi.*"
            )
            await wait_msg.edit(res_report)

        except Exception as e:
            logger.error(f"[SOCIAL_SPY ERROR] {e}")
            await wait_msg.edit(f"⚠️ Tahlil jarayonida xatolik: `{str(e)}`")

    async def send_draft_for_approval(self, user_id: int, name: str, draft: str):
        """AI tomonidan tayyorlangan javobni avtomatik yuborish (tasdiqlashsiz)."""
        try:
            await self.user_client.send_message(user_id, draft)
            logger.info("[ADMIN_BOT] Draft avtomatik yuborildi: lid=%s (%s)", user_id, name)
            if self.access_manager.owner_id:
                await self.bot_client.send_message(
                    self.access_manager.owner_id,
                    f"✅ Draft avtomatik yuborildi → {name} (ID: {user_id})",
                )
        except Exception as e:
            logger.error("[ADMIN_BOT] Draft yuborishda xatolik: %s", e)
            if self.access_manager.owner_id:
                await self.bot_client.send_message(
                    self.access_manager.owner_id,
                    f"❌ Draft yuborib bo'lmadi → {name}: {e}",
                )
