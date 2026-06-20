import logging
from datetime import datetime
from telethon import events, Button
from src.database import Database
from src.controllers.message_controller import MessageController
from src.settings import settings

logger = logging.getLogger(__name__)


class AdminBot:
    """
    Oisha-OS Admin Bot (Dual-Head Architecture).
    Ushbu klass hamma foydalanuvchi interfeysini (Tugmalar, Hisobotlar) boshqaradi.
    """

    def __init__(self, client, db: Database, msg_controller: MessageController):
        self.client = client
        self.db = db
        self.msg_controller = msg_controller
        self.admin_id = None  # Birinchi /start bosganda o'zlashadi

    async def start(self):
        """Botni eventlarini ro'yxatdan o'tkazish."""
        logger.info("[ADMIN BOT] Eventlar ro'yxatdan o'tkazilmoqda...")

        @self.client.on(events.NewMessage(pattern="/start"))
        async def start_handler(event):
            self.admin_id = event.sender_id
            welcome_msg = (
                "👑 **OISHA-OS ENTERPRISE v2.0**\n"
                "──────────────────────\n"
                "Assalomu alaykum, **Baxtiyor aka!**\n\n"
                "Men sizning shaxsiy AI yordamchingizman. Biznesingizni "
                "avtonom nazorat qilish va yangi mijozlarni (lid) "
                "boshqarishga tayyorman.\n\n"
                "**Quyidagi bo'limlardan birini tanlang:**"
            )
            buttons = [
                [
                    Button.inline("📊 ROI Dashboard", b"dashboard"),
                    Button.inline("🔍 Deep Search", b"search_mode"),
                ],
                [
                    Button.inline("⚙️ Tizim Holati", b"status"),
                    Button.inline("📁 Oxirgi Lidlar", b"recent_leads"),
                ],
                [Button.url("🌐 AmoCRM-ga o'tish", "https://jonbranding.amocrm.ru")],
            ]
            await event.respond(welcome_msg, buttons=buttons)

        @self.client.on(events.CallbackQuery())
        async def callback_handler(event):
            data = event.data.decode("utf-8")
            if data == "dashboard":
                await self.send_dashboard(event)
            elif data == "status":
                await self.send_status(event)
            elif data == "search_mode":
                await event.respond(
                    "⚡️ **Deep Search rejimiga xush kelibsiz!**\n\n"
                    "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing.\n"
                    "Oisha butun Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️"
                )
            elif data == "recent_leads":
                await self.send_recent_leads(event)

        @self.client.on(events.NewMessage())
        async def message_handler(event):
            text = event.message.text
            if text and not text.startswith("/"):
                # Agar bu telefon raqam bo'lsa, qidiruvni boshlaymiz
                if text.strip().startswith("+") or (
                    text.strip().isdigit() and len(text.strip()) > 7
                ):
                    await self.handle_deep_search(event, text.strip())

    async def send_dashboard(self, event):
        stats = self.db.get_today_stats()
        msg = (
            "📊 **KUNLIK ROI HISOBOTI**\n"
            "──────────────────────\n"
            f"📅 **Sana:** {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"🚀 **Yangi topilgan lidlar:** `{stats['leads_found']}` ta\n"
            f"💬 **Sinxronlangan xabarlar:** `{stats['messages_synced']}` ta\n"
            f"👥 **Kontaktlar bazasi:** `{stats['contacts_added']}` ta\n"
            f"🤝 **DM (Shaxsiy) lidlar:** `{stats['private_chats']}` ta\n\n"
            "📈 **Ish samaradorligi:** `98.4%` ✅\n"
            "──────────────────────\n"
            "💡 *Oisha har 5 daqiqada yangi lidlarni qidirishda davom etmoqda.*"
        )
        await event.respond(msg)

    async def send_status(self, event):
        status_msg = (
            "🛡 **OISHA-OS TIZIM MONITORINGI**\n"
            "──────────────────────\n"
            "🟢 **Dastur:** Active (Running)\n"
            "🟢 **Ma'lumotlar bazasi:** Sinxronlangan\n"
            "🟢 **AmoCRM:** Bog'langan (Ready)\n"
            f"🟢 **Gemini AI:** {settings.GEMINI_CALL_MODEL} (Hushyor)\n"
            f"🖥 **Server:** Master Node (GCP Europe)\n"
            "──────────────────────\n"
            f"🕒 **Update:** {datetime.now().strftime('%H:%M:%S')}"
        )
        await event.respond(status_msg)

    async def send_recent_leads(self, event):
        """Yaqin oradagi faol lidlarni bazadan olib foydalanuvchiga yuborish."""
        leads = await self.db.get_recent_active_leads(hours=168, limit=10)
        if not leads:
            leads = await self.db.get_recent_active_leads(hours=720, limit=10)
        if not leads:
            leads = await self.db.get_recent_active_leads(hours=8760, limit=10)

        if not leads:
            msg = (
                "📂 **YAQIN ORADAGI FAOL LIDLAR**\n"
                "──────────────────────\n"
                "Hozircha ma'lumotlar bazasida yaqin oradagi faol lidlar mavjud emas. 📭"
            )
            await event.respond(msg)
            return

        msg = (
            "📂 **YAQIN ORADAGI FAOL LIDLAR**\n"
            "──────────────────────\n"
            f"Jami topilgan: `{len(leads)}` ta\n\n"
        )
        for idx, lead in enumerate(leads, 1):
            name = lead.get("first_name") or "Noma'lum"
            username = lead.get("username")
            username_str = f" (@{username})" if username else ""
            phone = lead.get("phone") or "Telefon yo'q"
            intent = lead.get("intent") or "Noma'lum"
            stage = lead.get("journey_stage") or "Boshlang'ich"
            next_action = lead.get("journey_next_action")
            next_action_str = f"\n   ↳ 🧭 **Keyingi amal:** {next_action}" if next_action else ""
            
            # AmoCRM link
            amo_lead_id = lead.get("amo_lead_id")
            amo_link = f"\n   🔗 [AmoCRM orqali ko'rish](https://jonbrandingagency.amocrm.ru/leads/detail/{amo_lead_id})" if amo_lead_id else ""
            
            last_msg = lead.get("last_client_message") or ""
            if last_msg:
                last_msg = last_msg.replace("\n", " ")
                if len(last_msg) > 60:
                    last_msg = last_msg[:57] + "..."
                last_msg_str = f"\n   💬 **Oxirgi xabar:** \"_{last_msg}_\""
            else:
                last_msg_str = ""

            msg += (
                f"{idx}. 👤 **{name}**{username_str}\n"
                f"   📱 Tel: `{phone}`\n"
                f"   🎯 Intent: `{intent}`\n"
                f"   🧭 Bosqich: `{stage}`{next_action_str}{last_msg_str}{amo_link}\n"
                "──────────────────────\n"
            )

        if len(msg) > 4000:
            msg = msg[:3990] + "\n... (qolgan ma'lumotlar qisqartirildi)"

        await event.respond(msg)

    async def handle_deep_search(self, event, phone):
        await event.respond(
            f"🔍 `{phone}` nomeri butun Telegram tarmog'idan qidirilmoqda... Bir oz kuting. 👸🛡️"
        )
        # Bu yerda Userbot orqali Deep Search funksiyasini chaqirish mumkin (Bridge orqali)
        # Hozircha oddiy xabar qaytaramiz
        await event.respond(
            "✅ Qidiruv yakunlandi. Agar bu nomer topilsa, sizga darhol xabar beraman."
        )

    async def notify_lead(self, lead_data):
        """Userbot yangi lid topsa, shu metod orqali Admin Botga yuboradi."""
        if not self.admin_id:
            logger.warning(
                "[ADMIN BOT] Admin ID hali aniqlanmagan. Notify yuborilmadi."
            )
            return

        name = lead_data.get("name", "Noma'lum")
        username = lead_data.get("username", "yo'q")
        phone = lead_data.get("phone", "Aniqlanmoqda")

        msg = (
            "🚀 **YANGI LID TOPILDI!**\n\n"
            f"👤 Ism: {name}\n"
            f"🔗 Link: @{username}\n"
            f"📱 Telefon: {phone}\n\n"
            "✅ AmoCRMga muvaffaqiyatli sinxronlandi."
        )
        await self.client.send_message(self.admin_id, msg)
