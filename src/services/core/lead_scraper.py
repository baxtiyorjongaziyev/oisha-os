import asyncio
import logging
import json
import os
import random
from typing import Dict, Any, Optional
from telethon import TelegramClient, functions, types
from src.services.google_service import GoogleService
from src.settings import settings
from google import genai

logger = logging.getLogger(__name__)

class LeadScraper:
    """Enriched & Safe Lead Scraping from Telegram Forum Topics."""

    def __init__(self, google_service, db, client=None, amocrm=None, notify_callback=None):
        self.google = google_service
        self.db = db
        self.client = client
        self.amocrm = amocrm
        self.notify_callback = notify_callback
        
        # Configure Gemini with modern SDK
        self.genai_client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())
        self.model_name = 'gemini-2.0-flash'

    async def _is_processed(self, message_id):
        """Xabar oldin qayta ishlanganini tekshirish."""
        return await self.db.is_message_processed(message_id)

    async def _mark_processed(self, message_id, group_id, status='synced', reason=None):
        """Xabarni qayta ishlangan deb belgilash."""
        await self.db.mark_message_processed(message_id, group_id, status, reason)

    async def sync_topic_to_contacts(self, client: TelegramClient, group_id: int, topic_id: int, limit: int = 50):
        """Muayyan topickdagi barcha xabarlardan lidlarni qidirib topish va saqlash."""
        logger.info(f"[SCRAPER] {group_id}:{topic_id} topigini tahlili boshlandi... 👸🛡️")
        
        saved_count = 0
        async for message in client.iter_messages(group_id, reply_to=topic_id, limit=limit):
            if not message.text or await self._is_processed(message.id):
                continue

            # 1. AI yordamida intro tahlili (Phone, Name, Work)
            lead_data = await self.parse_intro_with_ai(message.text)
            
            if lead_data and lead_data.get('phone'):
                # Lid topildi!
                full_name = f"{lead_data.get('name', 'Client')} TN5"
                phones = [lead_data.get('phone')]
                
                try:
                    logger.info(f"[SCRAPER] Yangi lid topildi: {full_name} ({phones[0]})")
                    
                    # 2. Google Contacts-ga
                    await self.google.save_contact(
                        name=full_name, 
                        phones=phones, 
                        notes=f"Lid from TG Topic: {topic_id}\nOriginal Msg: {message.text[:100]}...",
                        group_name="TEZ NATIJA 5"
                    )
                    
                    # 3. Telegram Contacts-ga
                    user_entity = await client.get_entity(message.from_id)
                    await client(functions.contacts.AddContactRequest(
                        id=user_entity.id,
                        first_name=lead_data.get('name', 'Client'),
                        last_name="TN5",
                        phone=phones[0],
                        add_phone_privacy_exception=True
                    ))
                    
                    # 4. AmoCRM-da yangi bitim yaratish
                    if self.amocrm:
                        self.amocrm.create_lead(
                            name=f"Potential: {full_name}",
                            price=0,
                            phone=phones[0],
                            note=f"TG Topic: {topic_id}\nIntro: {message.text[:200]}"
                        )

                    if self.notify_callback:
                        await self.notify_callback(f"👸 **Yangi Mijoz Topildi!**\n\n👤 Ism: {lead_data.get('name')}\n📞 Tel: {phones[0]}\n📁 AmoCRM-ga saqlandi.")

                    saved_count += 1
                    await self._mark_processed(message.id, group_id, status='synced')
                    
                    # ULTRA SAFE DELAY: 60 - 120 seconds
                    wait_time = random.uniform(60, 120)
                    logger.info(f"[SCRAPER] Xavfsiz tanaffus: {wait_time:.1f} soniya... 🐢🛡️")
                    await asyncio.sleep(wait_time)
                    
                except Exception as ex:
                    logger.error(f"[SCRAPER] Sync error: {ex}")
                    # Don't mark as processed if there was a major sync error, to retry later
            else:
                # No phone found
                self._mark_processed(message.id, group_id, status='skipped', reason='No phone matched')
    async def sync_all_group_members(self, client: TelegramClient, group_id: int, limit: int = 50, no_phone_only: bool = False, group_label: str = "TEZ NATIJA 5", prefix: str = "TN5"):
        """Ommaiy tarzda guruhdagi barcha a'zolarni to'g'ridan-to'g'ri (AI filtrlashsiz) saqlash."""
        logger.info(f"[MASS SYNC] {group_label} ({group_id}) guruhining barcha a'zolarini skanerlash boshlandi... 👸🛡️")
        
        saved_count = 0
        try:
            async for user in client.iter_participants(group_id):
                if user.bot or user.deleted:
                    continue
                
                if saved_count >= limit:
                    logger.info(f"[MASS SYNC] Batch limitga ({limit}) yetildi. 🛑")
                    break

                # Biz message_id xotirasiga mass sync odamlarini kiritamiz
                dummy_msg_id = user.id * -1
                if await self._is_processed(dummy_msg_id):
                    continue
                
                phone = getattr(user, 'phone', None)
                if no_phone_only and phone:
                    # Skip if we only want those without phones
                    continue

                name = getattr(user, 'first_name', '') or ''
                surname = getattr(user, 'last_name', '') or ''
                username = getattr(user, 'username', '') or ''
                
                if not name and not surname:
                    name = username or f"User {user.id}"

                full_name = f"{name} {surname}".strip()
                
                # Kirilchani lotinchaga ogirish lug'ati
                cyrillic_to_latin_map = {
                    'А':'A', 'Б':'B', 'В':'V', 'Г':'G', 'Д':'D', 'Е':'E', 'Ё':'Yo', 'Ж':'J', 'З':'Z',
                    'И':'I', 'Й':'Y', 'К':'K', 'Л':'L', 'М':'M', 'Н':'N', 'О':'O', 'П':'P', 'Р':'R',
                    'С':'S', 'Т':'T', 'У':'U', 'Ф':'F', 'Х':'X', 'Ц':'Ts', 'Ч':'Ch', 'Ш':'Sh', 'Щ':'Sh',
                    'Ъ':'', 'Ы':'I', 'Ь':'', 'Э':'E', 'Ю':'Yu', 'Я':'Ya',
                    'а':'a', 'б':'b', 'в':'v', 'г':'g', 'д':'d', 'е':'e', 'ё':'yo', 'ж':'j', 'з':'z',
                    'и':'i', 'й':'y', 'к':'k', 'л':'l', 'м':'m', 'н':'n', 'о':'o', 'п':'p', 'р':'r',
                    'с':'s', 'т':'t', 'у':'u', 'ф':'f', 'х':'x', 'ц':'ts', 'ч':'ch', 'ш':'sh', 'щ':'sh',
                    'ъ':'', 'ы':'i', 'ь':'', 'э':'e', 'ю':'yu', 'я':'ya', 'ў':'o\'', 'қ':'q', 'ғ':'g\'', 'ҳ':'h',
                    'Ў':'O\'', 'Қ':'Q', 'Ғ':'G\'', 'Ҳ':'H'
                }
                
                for cyr, lat in cyrillic_to_latin_map.items():
                    full_name = full_name.replace(cyr, lat)
                    name = name.replace(cyr, lat)
                    surname = surname.replace(cyr, lat)
                
                # Refined Name Splitting
                name_parts = full_name.split(maxsplit=1)
                first_name = name_parts[0] if name_parts else "Unknown"
                last_name_orig = name_parts[1] if len(name_parts) > 1 else ""
                
                # Append Prefix for identification
                # If prefix is 'TN5', result is 'First Last TN5'
                display_last_name = f"{last_name_orig} {prefix}".strip()
                
                if not phone:
                    phones = []
                else:
                    phones = [phone if phone.startswith('+') else f"+{phone}"]

                try:
                    logger.info(f"[MASS SYNC] Tahlil: {first_name} {display_last_name} ({phone or 'No phone'})")
                    
                    # Deduplication Check (Dastlabki tekshiruv)
                    if await self.db.get_user_info(user.id):
                        logger.info(f"[MASS SYNC] {first_name} allaqachon DBda bor. O'tkazib yuborildi. ⏩")
                        continue

                    # Aggressive recursive cleaning to prevent duplicate 'TN' markings
                    import re
                    
                    # USE UNIFIED NAMING LOGIC
                    is_tn5_group = "TN5" in group_label or "Tez Natija 5" in group_label
                    contact_full_name = self.format_contact_name(first_name, last_name_orig, is_tn5=is_tn5_group)

                    # 1. Google Contacts (Only if phone exists)
                    if phone:
                        try:
                            await self.google.save_contact(
                                name=contact_full_name, 
                                phones=phones, 
                                notes=f"TG Username: @{username}\nTG ID: {user.id}\nGroup: {group_label}", 
                                group_name=group_label
                            )
                        except Exception as g_ex:
                            logger.warning(f"[MASS SYNC] Google xatosi: {g_ex}")
                    else:
                        logger.info(f"[MASS SYNC] No phone, skipping Google for {first_name}")
                    
                    # 2. Telegram Contacts (High-Reliability Force Sync)
                    tg_status = "skipped"
                    try:
                        from telethon import types
                        contact = types.InputPhoneContact(
                            client_id=random.randrange(-2**63, 2**63),
                            phone=phones[0] if phones else "",
                            first_name=contact_full_name, # Suffix is part of the first name for better visibility
                            last_name=""
                        )
                        await client(functions.contacts.ImportContactsRequest(contacts=[contact]))
                        logger.info(f"[MASS SYNC] Telegramga majburiy qo'shildi: {contact_full_name}")
                        tg_status = "success"
                    except Exception as tg_ex:
                        logger.warning(f"[MASS SYNC] TG xatosi: {tg_ex}")
                        tg_status = f"error: {str(tg_ex)[:50]}"

                    # 3. AmoCRM Lead
                    if self.amocrm:
                        try:
                            self.amocrm.create_lead(
                                name=f"Potential: {first_name} {display_last_name}",
                                price=0,
                                phone=phones[0] if phones else "Raqam yo'q",
                                note=f"TG Username: @{username}\nTG ID: {user.id}\nGroup: {group_label}"
                            )
                        except Exception as amo_ex:
                            logger.warning(f"[MASS SYNC] AmoCRM xatosi: {amo_ex}")

                    # 4. Database Persistence (CRITICAL FIX)
                    await self.db.upsert_user(
                        user_id=user.id,
                        first_name=first_name,
                        last_name=display_last_name,
                        username=username,
                        phone=phones[0] if phones else None,
                        role='lead_potential'
                    )
                    await self._mark_processed(dummy_msg_id, group_id, status='synced_mass')
                    saved_count += 1
                    
                    # Banning prevention! 60-120 seconds
                    wait_time = random.uniform(60.0, 120.0)
                    logger.info(f"[MASS SYNC] Kutish: {wait_time:.1f} soniya... 🐢🛡️")
                    await asyncio.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"[MASS SYNC] Saqlashda xato: {e}")
                    
            logger.info(f"[MASS SYNC] Yakunlandi! Jami ommaviy saqlanganlar: {saved_count}")
        except Exception as ex:
            logger.error(f"[MASS SYNC ERROR] {ex}")
        return saved_count

    async def sync_private_dialogs(self, client: TelegramClient, limit: int = 100):
        """Oxirgi shaxsiy suhbatlardan (DM) lidlarni qidirib topish va AmoCRMga qo'shish."""
        logger.info(f"[SCRAPER] Shaxsiy suhbatlar (DM) tahlili boshlandi (Limit: {limit})... 👸🛡️")
        
        sync_count = 0
        from src.services.auto_lead_agent import AutoLeadAgent
        from src.settings import settings
        auto_lead_agent = AutoLeadAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())

        async for dialog in client.iter_dialogs(limit=limit):
            if not dialog.is_user or dialog.entity.bot:
                continue

            user_id = dialog.id
            if await self.db.is_crm_synced(user_id):
                continue
            
            # 1. Get last messages
            messages = await client.get_messages(dialog.entity, limit=20)
            chat_text = "\n".join([f"{'Bot' if m.out else 'User'}: {m.text}" for m in messages if m.text])
            
            if not chat_text:
                continue

            # 2. AI Lead Qualification
            is_lead, lead_details = await auto_lead_agent.qualify_chat(chat_text)
            
            if is_lead:
                logger.info(f"[DM SYNC] Lid topildi: {dialog.name}")
                phone = lead_details.get('phone') or getattr(dialog.entity, 'phone', 'Unknown')
                
                # 3. Save to CRM
                if self.amocrm:
                    try:
                        self.amocrm.create_lead(
                            name=f"DM Lead: {dialog.name}",
                            price=0,
                            phone=phone,
                            note=f"AI Summary: {lead_details.get('summary')}\nUser: @{getattr(dialog.entity, 'username', 'N/A')}"
                        )
                        await self.db.set_crm_synced(user_id)
                        sync_count += 1
                        logger.info(f"[DM SYNC] AmoCRMga qo'shildi: {dialog.name}")
                        
                        # 4. Notify Team in Telegram Group (CRM Topic)
                        if self.notify_callback:
                            try:
                                msg = (
                                    f"👸 **Yangi Shaxsiy Lead Topildi!**\n\n"
                                    f"👤 **Ism:** {dialog.name}\n"
                                    f"📞 **Tel:** {phone}\n"
                                    f"📝 **Tahlil:** {lead_details.get('summary')}\n\n"
                                    f"📁 AmoCRM-ga muvaffaqiyatli saqlandi. 👸🛡️"
                                )
                                await self.notify_callback(msg)
                            except Exception as n_ex:
                                logger.error(f"[DM SYNC] Notification error: {n_ex}")
                    except Exception as e:
                        logger.error(f"[DM SYNC ERROR] AmoCRM save: {e}")

        logger.info(f"[DM SYNC] Yakunlandi. Jami: {sync_count}")
        return sync_count

    def format_contact_name(self, first_name: str, last_name: str = "", lead_data: Dict[str, Any] = None, is_tn5: bool = False) -> str:
        """
        Guruh a'zosi yoki DM-murojaati uchun chiroyli ism formatini yaratish.
        Agar TN5 guruhidab bo'lsa: 'Ism Familiya TN5 Gr'
        Aks holda: 'Ism Familiya Shahar Sohasi Brand' (mavjudligiga qarab)
        """
        # 1. TN5 logic (Primary override)
        if is_tn5:
            full = f"{first_name} {last_name}".strip()
            return f"{full} TN5 Gr".strip()
        
        # 2. Detailed logic (Enterprise standard)
        parts = [first_name, last_name]
        
        if lead_data:
            # We check for keys from AutoLeadAgent extraction
            for key in ['city', 'activity', 'brand_name']:
                val = lead_data.get(key)
                if val and str(val).lower() not in ["noma'lum", "unknown", "none", "", "null", "no'malum"]:
                    # Clean up common AI filler
                    val_clean = str(val).strip()
                    if val_clean.lower() != "nomsiz":
                        parts.append(val_clean)
        
        # Join and remove redundant spaces
        final_name = " ".join([p for p in parts if p]).strip()
        
        # Limit length if necessary for contact sync (Optional, but good for stability)
        return final_name[:64]

    async def parse_intro_with_ai(self, text: str) -> Optional[Dict[str, Any]]:
        """Introductsiyani Gemini orqali tahlil qilish."""
        prompt = (
            "Quyidagi xabar Telegram guruhidagi 'Intro' xabari. "
            "Undan foydalanuvchining ismi, telefon raqami va faoliyat sohasini ajratib oling. "
            "Faqat JSON formatida javob bering.\n\n"
            f"Xabar: {text}\n\n"
            "Format: {\"name\": \"...\", \"phone\": \"...\", \"work\": \"...\"}"
        )
        
        system_instruction = "Siz tajribali ma'lumot tahlilchisisiz. Telegram xabarlaridan lidlar ma'lumotlarini ajratib olishga ixtisoslashgansiz."
        
        try:
            from src.main import safe_ai_call
            response = await safe_ai_call(
                client=self.genai_client,
                prompt=prompt,
                system_instruction=system_instruction,
                model=self.model_name,
                mime_type="application/json"
            )
            
            if response and response.text:
                return json.loads(response.text)
        except Exception as e:
            logger.error(f"[LEAD_SCRAPER] AI Parsing Error: {e}")
            return None
