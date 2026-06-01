import os
import sys
import json
import logging
import asyncio
import datetime
from typing import List, Dict, Any, Optional, Set

import requests
import src.config as config
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger("crm_archiver")

class CRMArchiver:
    def __init__(self, amocrm: Optional[AmoCRMSync] = None, db: Optional[Database] = None):
        self.amocrm = amocrm or AmoCRMSync(
            config.AMOCRM_SUBDOMAIN,
            config.AMOCRM_CLIENT_ID,
            config.AMOCRM_CLIENT_SECRET,
            config.AMOCRM_REDIRECT_URL,
        )
        self.db = db or Database()

    async def init_tables(self):
        """Turso yoki SQLite ma'lumotlar bazasida jadvallarni yaratish."""
        logger.info("[ARCHIVER] Archive jadvallarini tekshirish/yaratish...")
        async with await self.db.get_connection() as conn:
            # Create amocrm_archived_leads
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS amocrm_archived_leads (
                    lead_id INTEGER PRIMARY KEY,
                    name TEXT,
                    price INTEGER,
                    status_id INTEGER,
                    pipeline_id INTEGER,
                    responsible_user_id INTEGER,
                    created_at INTEGER,
                    updated_at INTEGER,
                    phone TEXT,
                    contact_id INTEGER,
                    contact_name TEXT,
                    notes TEXT,
                    custom_fields TEXT,
                    archived_at TEXT
                )
            """)
            # Create amocrm_archived_campaigns
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS amocrm_archived_campaigns (
                    lead_id INTEGER PRIMARY KEY,
                    campaign_step1 TEXT,
                    campaign_step2 TEXT,
                    campaign_step3 TEXT,
                    generated_at TEXT,
                    status TEXT,
                    FOREIGN KEY(lead_id) REFERENCES amocrm_archived_leads(lead_id)
                )
            """)
            await conn.commit()
        logger.info("[ARCHIVER] Archive jadvallari tayyor.")

    async def fetch_all_active_leads(self) -> List[Dict[str, Any]]:
        """AmoCRM dan barcha aktiv bitimlarni paginatsiya bilan yuklab olish."""
        logger.info("[ARCHIVER] AmoCRM dan barcha aktiv bitimlarni yuklash boshlandi...")
        active_leads = []
        limit = 250
        page = 1

        # Access token authorization check
        if not self.amocrm.access_token:
            self.amocrm._load_token()

        loop = asyncio.get_event_loop()

        while True:
            url = f"{self.amocrm.base_url}/api/v4/leads"
            params = {
                "limit": limit,
                "page": page,
                "with": "contacts"
            }
            logger.info(f"[ARCHIVER] Leads sahifasi yuklanmoqda: {page}...")
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        url,
                        headers=self.amocrm._get_headers(),
                        params=params,
                        timeout=30
                    )
                )

                if response.status_code == 401:
                    logger.info("[ARCHIVER] Token eskirgan. Yangilanmoqda...")
                    refreshed = await loop.run_in_executor(None, self.amocrm.refresh_token)
                    if refreshed:
                        response = await loop.run_in_executor(
                            None,
                            lambda: requests.get(
                                url,
                                headers=self.amocrm._get_headers(),
                                params=params,
                                timeout=30
                            )
                        )
                    else:
                        logger.error("[ARCHIVER] Tokenni yangilash muvaffaqiyatsiz bo'ldi.")
                        break

                if response.status_code != 200:
                    logger.warning(f"[ARCHIVER] Leads HTTP xato: {response.status_code}")
                    break

                data = response.json()
                leads = data.get("_embedded", {}).get("leads", [])
                if not leads:
                    break

                for lead in leads:
                    status_id = lead.get("status_id")
                    # Exclude Closed Won (142) va Closed Lost (143)
                    if status_id not in (142, 143):
                        active_leads.append(lead)

                if len(leads) < limit:
                    break

                page += 1
            except Exception as e:
                logger.error(f"[ARCHIVER ERROR] Leads yuklashda xato (sahifa {page}): {e}")
                break

        logger.info(f"[ARCHIVER] Jami active bitimlar soni: {len(active_leads)}")
        return active_leads

    async def fetch_open_task_lead_ids(self) -> Set[int]:
        """AmoCRM dan barcha yopilmagan vazifalarni yuklab, ularga bog'langan lead ID-larini qaytaradi."""
        logger.info("[ARCHIVER] Vazifalarni tekshirish boshlandi...")
        open_lead_ids = set()
        limit = 250
        page = 1
        loop = asyncio.get_event_loop()

        while True:
            url = f"{self.amocrm.base_url}/api/v4/tasks"
            params = {
                "limit": limit,
                "page": page,
                "filter[is_completed]": 0
            }
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(
                        url,
                        headers=self.amocrm._get_headers(),
                        params=params,
                        timeout=30
                    )
                )

                if response.status_code == 401:
                    refreshed = await loop.run_in_executor(None, self.amocrm.refresh_token)
                    if refreshed:
                        response = await loop.run_in_executor(
                            None,
                            lambda: requests.get(
                                url,
                                headers=self.amocrm._get_headers(),
                                params=params,
                                timeout=30
                            )
                        )
                    else:
                        break

                if response.status_code != 200:
                    break

                data = response.json()
                tasks = data.get("_embedded", {}).get("tasks", [])
                if not tasks:
                    break

                for task in tasks:
                    entity_type = task.get("entity_type")
                    entity_id = task.get("entity_id")
                    if entity_type == "leads" and entity_id:
                        open_lead_ids.add(int(entity_id))

                if len(tasks) < limit:
                    break

                page += 1
            except Exception as e:
                logger.error(f"[ARCHIVER ERROR] Vazifalarni yuklashda xato (sahifa {page}): {e}")
                break

        logger.info(f"[ARCHIVER] Yopilmagan vazifaga ega bitimlar soni: {len(open_lead_ids)}")
        return open_lead_ids

    async def get_stagnant_leads(self, max_stagnant_days: int = 21) -> List[Dict[str, Any]]:
        """Aktiv, lekin stagnatsiyadagi (yangilanmagan va vazifasi yo'q) bitimlarni aniqlash."""
        active_leads = await self.fetch_all_active_leads()
        open_task_lead_ids = await self.fetch_open_task_lead_ids()

        stagnant_threshold = int(datetime.datetime.now().timestamp()) - (max_stagnant_days * 24 * 3600)
        stagnant_leads = []

        for lead in active_leads:
            lead_id = int(lead.get("id"))
            updated_at = int(lead.get("updated_at") or 0)

            # Criteria: Open task bo'lmasligi va updated_at thresholddan eski bo'lishi
            if lead_id not in open_task_lead_ids and updated_at < stagnant_threshold:
                stagnant_leads.append(lead)

        # Sort stagnant leads by updated_at ascending (eng eski qotib qolganlar birinchi)
        stagnant_leads.sort(key=lambda x: x.get("updated_at", 0))
        logger.info(f"[ARCHIVER] Stagnatsiyadagi bitimlar aniqlandi: {len(stagnant_leads)}")
        return stagnant_leads

    async def fetch_contact_details(self, contact_id: int) -> Dict[str, Any]:
        """Kontakt ID orqali telefon va ismini olish."""
        url = f"{self.amocrm.base_url}/api/v4/contacts/{contact_id}"
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    headers=self.amocrm._get_headers(),
                    timeout=30
                )
            )
            if response.status_code == 200:
                data = response.json()
                name = data.get("name")
                phone = None
                fields = data.get("custom_fields_values", [])
                for field in fields:
                    if field.get("field_code") == "PHONE":
                      phone = field.get("values", [{}])[0].get("value")
                      break
                return {"name": name, "phone": phone, "raw": data}
            return {}
        except Exception as e:
            logger.error(f"[ARCHIVER ERROR] Kontakt yuklashda xato (ID {contact_id}): {e}")
            return {}

    async def generate_outreach_campaign(self, lead: Dict[str, Any], phone: str, contact_name: str, notes: List[Dict[str, Any]]) -> Dict[str, str]:
        """Gemini yordamida 3 bosqichli outreach xabarlarini yaratish."""
        import google.generativeai as genai

        # Prepare context for the prompt
        lead_name = lead.get("name", "Noma'lum")
        price = lead.get("price", 0)
        custom_fields = lead.get("custom_fields_values", []) or []

        # Convert custom fields to string description
        cf_desc = []
        for cf in custom_fields:
            name = cf.get("field_name", "")
            vals = [str(v.get("value", "")) for v in cf.get("values", [])]
            cf_desc.append(f"{name}: {', '.join(vals)}")

        # Summarize notes for context
        notes_desc = []
        for n in notes[:10]: # Oxirgi 10 izohni ishlatamiz
            text = n.get("params", {}).get("text", "") or n.get("text", "")
            if text:
                notes_desc.append(text)

        context_prompt = f"""
        Bitim nomi: {lead_name}
        Mijoz ismi: {contact_name or "Noma'lum"}
        Telefon: {phone or "Noma'lum"}
        Narxi: {price:,} so'm
        Maxsus maydonlar:
        {chr(10).join(cf_desc)}

        Suhbat tarixi/Izohlar:
        {chr(10).join(notes_desc)}
        """

        # System Instruction for Gemini
        system_instruction = """
        Siz Jon Branding premium branding agentligining (Oisha-OS) yetakchi outreach strategisiz.
        Vazifangiz: Mijoz bilan avvalgi muloqot va bitim kontekstini (tarixi, yozishmalar, izohlar) tahlil qilib, uni qayta uyg'otish (reactivation) uchun shaxsiy va juda yuqori konversiyali 3 bosqichli outreach xabarlarini o'zbek tilida (lotin alifbosida) tayyorlash.

        Talablar:
        1. Tone: Premium, o'ta samimiy, insoniy, hurmat bilan (VIP ton). Hech qanday robotlik yoki andozaviy bot iboralari bo'lmasin. Baxtiyorjon aka yoki agentlik PM-lari nomidan yoziladi.
        2. Har bir xabar mijozning ismini va original qiziqishini (masalan, Naming, Logo, Brandbook, SMM yoki Web) hisobga olsin.
        3. Format: Natijani faqat va faqat quyidagi JSON formatida qaytaring, boshqa hech qanday so'z yoki tushuntirish qo'shmang:
        {
          "step1": "1-bosqich xabari matni...",
          "step2": "2-bosqich xabari matni...",
          "step3": "3-bosqich xabari matni..."
        }
        """

        api_key = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("[ARCHIVER] GEMINI_API_KEY topilmadi. Standart outreach xabarlar ishlatiladi.")
            return {
                "step1": f"Assalomu alaykum, {contact_name or 'Mijoz'}. Jon Branding agentligidan bezovta qilyapmiz. Loyihangiz bo'yicha qanday yangiliklar bor?",
                "step2": "Sizga yaqinda amalga oshirgan yangi keyslarimizni ulashmoqchi edik. Ko'rib chiqish qiziqmi?",
                "step3": "Branding masalalarini qisqa 15 daqiqalik qo'ng'iroqda muhokama qila olamiz. Sizga qaysi kun qulay?"
            }

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                os.getenv("GEMINI_CALL_MODEL", "gemini-2.5-flash")
            )
            loop = asyncio.get_event_loop()

            prompt = f"Mijoz va bitim konteksti:\n{context_prompt}\n\nIltimos, outreach xabarlarini yuqoridagi system instruction talablariga mos ravishda JSON ko'rinishida generatsiya qiling."

            # Execute in thread executor to avoid blocking async loop
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(response_mime_type="application/json"),
                    system_instruction=system_instruction
                )
            )

            text = getattr(response, "text", "") or ""
            data = json.loads(text.strip())
            return {
                "step1": data.get("step1", "").strip(),
                "step2": data.get("step2", "").strip(),
                "step3": data.get("step3", "").strip(),
            }
        except Exception as e:
            logger.error(f"[ARCHIVER AI ERROR] Outreach yaratishda xato: {e}")
            return {
                "step1": f"Assalomu alaykum, {contact_name or 'Mijoz'}. Jon Branding agentligidan bezovta qilyapmiz. Loyihangiz bo'yicha qanday yangiliklar bor?",
                "step2": "Sizga yaqinda amalga oshirgan yangi keyslarimizni ulashmoqchi edik. Ko'rib chiqish qiziqmi?",
                "step3": "Branding masalalarini qisqa 15 daqiqalik qo'ng'iroqda muhokama qila olamiz. Sizga qaysi kun qulay?"
            }

    async def archive_lead(self, lead: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        """Bitta stagnant leadni arxivlash: ma'lumotlarni yig'ish, Turso ga yozish va AmoCRM da Closed Lost qilish."""
        lead_id = int(lead.get("id"))
        logger.info(f"[ARCHIVER] Bitim arxivlanmoqda {lead_id} ({lead.get('name')}) - Dry run: {dry_run}")

        # 1. Fetch Contact Phone and Name
        contact_id = None
        contact_name = None
        phone = None
        contacts = lead.get("_embedded", {}).get("contacts", []) or []
        if contacts:
            contact_id = int(contacts[0].get("id"))
            contact_details = await self.fetch_contact_details(contact_id)
            contact_name = contact_details.get("name")
            phone = contact_details.get("phone")

        # 2. Fetch Lead Notes
        notes = await self.amocrm.get_lead_notes(lead_id)

        # 3. Generate Outreach Campaign
        campaign = await self.generate_outreach_campaign(lead, phone, contact_name, notes)

        # Build payload
        archive_payload = {
            "lead_id": lead_id,
            "name": lead.get("name"),
            "price": lead.get("price", 0),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "responsible_user_id": lead.get("responsible_user_id"),
            "created_at": lead.get("created_at"),
            "updated_at": lead.get("updated_at"),
            "phone": phone,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "notes": json.dumps(notes, ensure_ascii=False),
            "custom_fields": json.dumps(lead.get("custom_fields_values", []), ensure_ascii=False),
            "archived_at": datetime.datetime.now().isoformat()
        }

        if not dry_run:
            # 4. Insert into database
            async with await self.db.get_connection() as conn:
                # Save lead
                await conn.execute("""
                    INSERT OR REPLACE INTO amocrm_archived_leads
                    (lead_id, name, price, status_id, pipeline_id, responsible_user_id, created_at, updated_at, phone, contact_id, contact_name, notes, custom_fields, archived_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    archive_payload["lead_id"],
                    archive_payload["name"],
                    archive_payload["price"],
                    archive_payload["status_id"],
                    archive_payload["pipeline_id"],
                    archive_payload["responsible_user_id"],
                    archive_payload["created_at"],
                    archive_payload["updated_at"],
                    archive_payload["phone"],
                    archive_payload["contact_id"],
                    archive_payload["contact_name"],
                    archive_payload["notes"],
                    archive_payload["custom_fields"],
                    archive_payload["archived_at"]
                ))

                # Save campaign
                await conn.execute("""
                    INSERT OR REPLACE INTO amocrm_archived_campaigns
                    (lead_id, campaign_step1, campaign_step2, campaign_step3, generated_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    lead_id,
                    campaign["step1"],
                    campaign["step2"],
                    campaign["step3"],
                    datetime.datetime.now().isoformat(),
                    "pending"
                ))

                await conn.commit()

            # 5. Move lead to Closed Lost in AmoCRM (Status ID = 143)
            loop = asyncio.get_event_loop()
            status_updated = await self.amocrm.update_lead_status(lead_id, 143, lead.get("pipeline_id"))
            if not status_updated:
                logger.error(f"[ARCHIVER] {lead_id} bitimni Closed Lost qilishda HTTP xato.")
                return {"success": False, "lead_id": lead_id, "error": "AmoCRM status o'zgartirish xatosi"}

            # Add archive note
            await loop.run_in_executor(
                None,
                lambda: self.amocrm.add_lead_note(
                    lead_id,
                    "Oisha-OS: Bitim Turso bazasiga xavfsiz arxivlandi va faol limitsiz holatga (Closed Lost) o'tkazildi."
                )
            )

        return {
            "success": True,
            "lead_id": lead_id,
            "name": lead.get("name"),
            "phone": phone,
            "contact_name": contact_name,
            "campaign": campaign
        }
