import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from src.services.amocrm_sync import AmoCRMSync
from src.services.airtable_sync import AirtableSync
from src.services.auto_lead_agent import AutoLeadAgent
from src.services.admin_bot import AdminBot
from src.api_server import add_activity

logger = logging.getLogger(__name__)

from src.services.folder_manager import FolderManager

class LeadOrchestrator:
    """
    Oisha-OS v4.6 Lead Orchestrator.
    Unifies Telethon, AI Qualification, amoCRM, Airtable, and AdminBot.
    """
    def __init__(self, amocrm: AmoCRMSync, airtable: AirtableSync, auto_lead: AutoLeadAgent, admin_bot: AdminBot, db: Any = None, folder_manager: FolderManager = None):
        self.amocrm = amocrm
        self.airtable = airtable
        self.auto_lead = auto_lead
        self.admin_bot = admin_bot
        self.db = db
        self.folder_manager = folder_manager

    async def process_new_lead(self, chat_text: str, user_id: int, name: str, username: str = None, phone: str = None, source: str = "Telegram DM"):
        """
        The 'Golden Path' v4.6 for a new lead (amoCRM Only).
        """
        from src.settings import settings
        logger.info(f"👸 [ORCHESTRATOR] Processing lead: {name} (Source: {source})")
        
        # 1. AI Qualification
        add_activity("Lidni Skanerlash", f"{name} murojaati AI orqali tahlil qilinmoqda...", "thinking")
        is_lead, lead_details = await self.auto_lead.qualify_chat(chat_text)
        if not is_lead:
            logger.info(f"👸 [ORCHESTRATOR] Not a qualified lead: {name}")
            add_activity("Lid Rad Etildi", f"{name} murojaati biznes uchun mos emas deb topildi.", "info")
            return False

        add_activity("Lid Tasdiqlandi", f"{name} 'LEAD' deb klasifikatsiya qilindi. Intent: {lead_details.get('intent', 'WARM')}", "success")

        intent = lead_details.get('intent', 'WARM')
        summary = lead_details.get('summary', 'No summary provided')
        extracted_phone = lead_details.get('phone') or phone
        
        # 2. Telegram Chat Link Generation
        # Construct a link that allows direct messaging from amoCRM
        tg_link = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
        
        extra_fields = {}
        if settings.AMOCRM_TG_CHAT_FIELD_ID:
            extra_fields[settings.AMOCRM_TG_CHAT_FIELD_ID] = tg_link

        # 3. amoCRM Integration (Deduplication & Enrichment)
        add_activity("CRM Synching", f"amoCRM'dan {name} uchun mavjud kontakt qidirilmoqda...", "thinking")
        existing_contact = await self.amocrm.get_contact_by_phone(extracted_phone) if extracted_phone and extracted_phone != "Raqam yo'q" else None
        
        note_content = f"👸 Oisha AI Tahlili (v5.0):\n──────────────────────\n🎯 Intent: {intent}\n📝 Xulosa: {summary}\n📲 Chat: {tg_link}\n📅 Manba: {source}"
        
        lead_id = None
        is_repeat = False
        
        if existing_contact:
            contact_id = existing_contact['id']
            is_repeat = True
            add_activity("Takroriy Mijoz", f"{name} tizimda bor. Bitimlar yangilanmoqda.", "info")
            logger.info(f"👸 [ORCHESTRATOR] Existing contact found: {contact_id}. Searching for active leads...")
            
            # Find active leads
            active_leads = await self.amocrm.get_active_leads_for_contact(contact_id)
            
            if active_leads:
                # Use the most recent active lead
                lead_id = active_leads[0]['id']
                logger.info(f"👸 [ORCHESTRATOR] Consolidating into active lead: {lead_id}")
                await self.amocrm.add_lead_note(lead_id, note_content)
                await self.amocrm.add_lead_tag(lead_id, "TAKRORIY_MUROJAAT")
            else:
                # No active lead, create a new one for THIS contact
                logger.info(f"👸 [ORCHESTRATOR] Existing contact but no active leads. Creating new lead for contact {contact_id}")
                lead_id = await self.amocrm.create_lead_for_contact(
                    contact_id=contact_id,
                    name=f"{name} (Yangilangan)",
                    price=0,
                    extra_fields=extra_fields
                )
                if lead_id:
                    await self.amocrm.add_lead_note(lead_id, note_content)
                    await self.amocrm.add_lead_tag(lead_id, "ESKI_MIJOZ_RE_ENGAGEMENT")
        else:
            # New contact, new lead
            logger.info(f"👸 [ORCHESTRATOR] No existing contact for {name}. Creating new lead...")
            add_activity("CRM Creation", f"Yangi kontakt va bitim yaratilmoqda: {name}", "thinking")
            lead_id = await self.amocrm.create_lead(
                name=f"{name} ({intent})",
                price=0,
                phone=extracted_phone or "Raqam yo'q",
                note=note_content,
                extra_fields=extra_fields
            )
            add_activity("CRM Synced", f"{name} amoCRM bilan muvaffaqiyatli sinxronlandi.", "success")
            
        # Create a fallback task if a lead was created or found
        if lead_id and isinstance(lead_id, int):
            import time
            complete_till = int(time.time()) + (15 * 60)
            await self.amocrm.create_task(
                element_id=lead_id, 
                text=f"Yangi {intent} murojaat! {'(Mavjud mijoz)' if is_repeat else ''} Bog'laning: {name}", 
                complete_till=complete_till
            )
        
        # 4. AdminBot Team Notification & Distribution
        from telethon import Button
        if self.admin_bot.team_group_id:
            status_icon = "🔥" if intent == "HOT" else "📋"
            
            # --- Lead Distribution Logic ---
            assigned_manager_id = None
            distribution_text = ""
            
            # Fetch active managers from DB or Settings
            managers = settings.SALES_MANAGER_IDS
            if not managers:
                db_managers = await self.db.get_state("sales_managers", "")
                if db_managers:
                    managers = [int(i) for i in db_managers.split(",") if i]

            dist_mode = await self.db.get_state("lead_distribution_mode", settings.LEAD_DISTRIBUTION_MODE)

            if dist_mode == "ROUND_ROBIN" and managers:
                # Oxirgi menejer indeksini bazadan olamiz
                last_idx = int(await self.db.get_state("last_manager_idx", -1))
                new_idx = (last_idx + 1) % len(managers)
                assigned_manager_id = managers[new_idx]
                await self.db.set_state("last_manager_idx", new_idx)
                
                distribution_text = f"\n🎯 **Mas'ul xodim:** <a href='tg://user?id={assigned_manager_id}'>Menejer</a> (Round-Robin)"
            elif dist_mode == "CLAIM":
                distribution_text = "\n🔓 **Holat:** Ochiq (Claim kutilmoqda)"
            # -------------------------------

            outcome_text = "✅ AmoCRM-da bitim yaratildi."
            if is_repeat:
                outcome_text = "✨ Mavjud mijoz: Ma'lumotlar ochiq bitimga/kontaktga qo'shildi."

            title = "YANGI LID" if not is_repeat else "TAKRORIY MUROJAAT"
            msg = (
                f"👸 **OISHA INTELLIGENCE: {title}**\n"
                f"──────────────────────\n"
                f"👤 **Mijoz:** {name} (@{username or 'yoq'})\n"
                f"🎯 **Intent:** {status_icon} {intent}\n"
                f"📞 **Tel:** `{extracted_phone or 'TOPILMADI'}`\n"
                f"📲 **Chat:** [Telegram-da ochish]({tg_link})\n"
                f"📝 **Xulosa:** _{summary}_\n"
                f"──────────────────────\n"
                f"{outcome_text}{distribution_text}"
            )
            
            # Interactive buttons for the team
            amo_url = f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}" if isinstance(lead_id, int) else f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/contacts/list/?query={extracted_phone}"
            
            buttons = [
                [Button.url("🌐 AmoCRM-da ko'rish", amo_url)]
            ]
            
            if assigned_manager_id:
                # Agar Round-Robin bilan biriktirilgan bo'lsa, "Men shug'ullanaman" tugmasi shart emas yoki boshqacha bo'ladi
                buttons.append([Button.inline("✅ Qabul qildim", f"accept_lead:{lead_id}:{user_id}:{assigned_manager_id}")])
                # Menenjerga shaxsiy xabar ham yuborish mumkin
                try:
                    await self.admin_bot.bot_client.send_message(assigned_manager_id, f"📥 **Sizga yangi lid biriktirildi!**\n\nMijoz: {name}\nAsosiy guruhda ko'ring.")
                except Exception as e:
                    logger.warning(f"Could not notify manager {assigned_manager_id} directly: {e}")
            else:
                buttons.append([Button.inline("🚀 Men shug'ullanaman (Claim)", f"claim_lead:{lead_id}:{user_id}")])
            
            await self.admin_bot.notify_team(
                msg, 
                buttons=buttons, 
                topic_id=settings.CRM_TOPIC_ID, 
                parse_mode='html'
            )
        
        # 5. [GOD MODE] Folder Management
        if self.folder_manager:
            # Shift folder assignment based on intent
            asyncio.create_task(self.folder_manager.assign_to_folder(user_id, intent))
            
        return True
