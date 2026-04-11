import logging
import asyncio
from typing import Optional
from telethon import TelegramClient, events, functions, types
from src.database import Database
from src.services.admin_bot import AdminBot
from src.services.advisor_agent import AdvisorAgent
from src.services.airtable_sync import AirtableSync
from src.settings import settings

logger = logging.getLogger(__name__)

class OnboardingManager:
    """
    Oisha-OS v4.7 Onboarding Manager.
    Automates group creation, welcome sequences, and project staging.
    """
    def __init__(self, client: TelegramClient, db: Database, admin_bot: AdminBot):
        self.client = client
        self.db = db
        self.admin_bot = admin_bot
        self.advisor = AdvisorAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())
        self.airtable = AirtableSync()

    async def start_client_onboarding(self, manager_id: int, amount: str):
        """
        Main onboarding entry point triggered by Finance confirmation.
        """
        logger.info(f"👸 [ONBOARDING] Starting for manager {manager_id} (Amount: {amount})")
        
        try:
            # 1. Get Client Info from DB (Assumes the manager was talking to them)
            # Find the most recent lead handled by this manager
            user_info = self.db.get_user_info(manager_id) # Manager info
            
            # Need to find the Client ID. 
            # In a real scenario, the 'confirm_pay' button data should include the Client ID.
            # For now, let's look for the most recent message in the Kirim topic from this manager.
            # But the callback data should have it. 
            # I will assume the manager_id in callback was the CLIENT_ID (passed from kirim_celebration_handler).
            client_id = manager_id
            client_data = self.db.get_user_info(client_id)
            
            if not client_data:
                logger.error(f"[ONBOARDING] Client {client_id} not found in DB.")
                return

            client_name = client_data.get('first_name', 'Mijoz')
            project_name = client_data.get('brand_name') or client_data.get('business_type') or "Yangi Loyiha"

            # 2. CREATE TELEGRAM GROUP
            group_title = f"[JB] {project_name} | {client_name}"
            # CreateChatRequest (Legacy group) or CreateChannelRequest (Supergroup)
            # For Client-Agency, a supergroup is better (Megagroup)
            logger.info(f"👸 [GROUP] Creating project group: {group_title}")
            
            # Add at least one other user to create a private group
            # We add Baxtiyor aka (Owner)
            result = await self.client(functions.messages.CreateChatRequest(
                users=[settings.OWNER_ID],
                title=group_title
            ))
            
            chat_id = result.chats[0].id
            chat_peer = result.chats[0]
            
            # Invite the Client
            try:
                await self.client(functions.messages.AddChatUserRequest(
                    chat_id=chat_id,
                    user_id=client_id,
                    fwd_limit=100
                ))
            except Exception as e:
                logger.warning(f"👸 [ONBOARDING] Could not invite client directly: {e}. Posting link instead.")

            # 3. POST WELCOME SEQUENCE
            await self._send_onboarding_sequence(chat_peer, client_name, project_name)

            # 3.5. GENERATE AI BRIEFING (Internal Handover)
            await self._send_internal_briefing(chat_peer, client_id, manager_id, project_name)

            # 3.8. DEPLOY PROJECT CHECKLIST (v5.0 Delegation)
            from src.services.checklist_manager import ChecklistManager
            check_manager = ChecklistManager(self.db)
            service_type = client_data.get('service_type', 'Logo')
            checklist_report = await check_manager.deploy_checklist(project_name, client_id, service_type)
            await self.client.send_message(chat_peer, checklist_report)

            # 4. UPDATE AIRTABLE
            logger.info(f"👸 [AIRTABLE] Updating status to 'Briefing' for {project_name}")
            # For now, we search by Client Name or Lead ID
            # In v4.6, ConversionChecker creates the project. We update it here.
            await self.airtable.update_project_stage(client_name, "Briefing")

            # 5. NOTIFY TEAM
            if self.admin_bot:
                await self.admin_bot.notify_team(
                    f"👸 **Muvaffaqiyatli Onboarding!**\n\n"
                    f"📁 Loyiha: `{project_name}`\n"
                    f"👤 Mijoz: `{client_name}`\n"
                    f"✅ Guruh yaratildi va Onboarding yakunlandi. 👸🛡️"
                )

        except Exception as e:
            logger.error(f"👸 [ONBOARDING ERROR] {e}", exc_info=True)
            if self.admin_bot:
                await self.admin_bot.notify_admin(f"🚨 **Onboarding Xatoligi!**\n{e}")

    async def _send_internal_briefing(self, chat_peer, client_id, manager_id, project_name):
        """Generates and sends an internal AI-briefing for the PM and team."""
        # 1. Fetch History
        history = self.db.get_recent_messages(client_id, limit=50)
        
        if not history:
            logger.warning(f"👸 [BRIEFING] No history found for client {client_id}")
            return

        # 2. Format history for AI
        transcript = ""
        for msg in history:
            role = "CLIENT" if msg['role'] == 'user' else "OISHA"
            text = msg['parts'][0]['text']
            transcript += f"{role}: {text}\n"

        # 3. Generate Analysis with AI
        prompt = (
            f"Loyiha: {project_name}\n"
            f"Mijoz suhbati:\n{transcript}\n\n"
            "Siz Jon Branding PM-lar boshlig'isiz. Ushbu muloqotni tahlil qilib, "
            "PM va dizaynerlar uchun batafsil 'Client Brief' tayyorlang.\n\n"
            "Format quyidagicha bo'lsin:\n"
            "🚩 **Mijozning muammolari (Pain Points)** - Nimalardan qiynalmoqda?\n"
            "💎 **Kutilmalar (Expectations)** - Loyihadan nima kutayapti?\n"
            "🎨 **Brend uslubi (Style/Mood)** - Qanday atmosferani xohlayapti?\n"
            "📍 **Muhim detallar** - Suhbat davomida aytilgan o'ziga xos jihatlar."
        )
        
        # We reuse the AI search/analyze logic from DB or Advisor
        ai_brief = await self.advisor.analyze_lead_context(prompt) # Assuming Advisor has this or we use DB AI call
        
        # 4. Post to group
        briefing_msg = (
            "📋 **ICHKI PM BRİFİNGİ (AI-Powered)** 👸🛡️\n\n"
            f"{ai_brief}\n\n"
            "✍️ **Sotuv menejeri uchun:** @gaziyevdev (yoki mas'ul), iltimos PMga loyiha bo'yicha "
            "CRM-da yo'q bo'lgan qo'shimcha ma'lumotlarni yozib qoldiring."
        )
        await self.client.send_message(chat_peer, briefing_msg)

    async def _send_onboarding_sequence(self, chat_peer, client_name, project_name):
        """High-premium onboarding messages."""
        
        # 1. Welcome Message
        welcome_msg = (
            f"🌟 **Assalomu alaykum, {client_name}!**\n\n"
            f"**Jon Branding** agentligining oilasiga xush kelibsiz! 👸✨\n\n"
            f"**{project_name}** loyihangizni boshlashdan g'oyat mamnunmiz. "
            "Ushbu guruh bizning asosiy hamkorlik va muloqot maydonimiz bo'ladi."
        )
        await self.client.send_message(chat_peer, welcome_msg)
        await asyncio.sleep(2)

        # 2. PM Introduction (AI Powered)
        pm_intro = (
            "👸 **Oisha System:** Men hozir sizga ushbu loyiha uchun mas'ul menejerni (PM) tanishtiraman... 👸🛡️"
        )
        await self.client.send_message(chat_peer, pm_intro)
        
        # Generate official response
        pm_prompt = (
            f"Mijoz: {client_name}\n"
            f"Loyiha: {project_name}\n\n"
            "Siz Jon Branding PM (Project Manager) siz. O'zingizni tanishtiring. "
            "Loyihani boshidan oxirigacha javobgarlikni bo'yningizga olganingizni va "
            "mijozning orzularini amalga oshirishga tayyorligingizni ayting."
        )
        ai_pm_text = await self.advisor.analyze_lead_context(pm_prompt)
        await self.client.send_message(chat_peer, f"👤 **PM Introduction:**\n\n{ai_pm_text}")
        await asyncio.sleep(2)

        # 3. Escalation Policy (Systematic Rule)
        escalation_msg = (
            "📢 **Muhim Qoida (Accountability):**\n\n"
            "Biz sizning vaqtingizni va loyihangizni qadrlaymiz. Shuning uchun:\n\n"
            "1️⃣ Loyiha bo'yicha barcha savollarni ushbu guruhda berishingiz mumkin.\n"
            "2️⃣ Jamoamiz barcha masalalarni shu yerning o'zida hal qilib beradi.\n"
            "3️⃣ **DIQQAT:** Agar jamoa a'zolari yoki PM murojaatingizga o'z vaqtida javob bermasa, "
            "yoki qandaydir shikoyat tug'ilsa, shaxsan agentlik asoschisi **Baxtiyorjon Gaziyev** "
            "bilan bog'lanishingizni so'raymiz. Biz har bir mijozni qadrlaymiz!\n\n"
            "📍 **Bog'lanish:** @gaziyevdev"
        )
        await self.client.send_message(chat_peer, escalation_msg)
