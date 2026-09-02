"""
LLM classification, contact categorization, and comprehensive lead audit logic.
"""
import asyncio
import json
import re
from typing import Any, Dict, Optional, Tuple

import structlog
logger = structlog.get_logger(__name__)

from src.services.core.crm.auditor.db_storage import _maybe_await
from src.services.utils.gemini_fallback import generate_content_with_fallback

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None


class ClassifierMixin:
    """Handles contact classification and multi-channel audit execution."""

    async def classify_contact(
        self,
        lead_name: str,
        contact_name: str,
        phone: str,
        username: str,
        call_summary: str,
        telegram_history: str,
        lead_details: str = "",
        group_history: str = "",
        tasks_history: str = "",
        notes_history: str = "",
        telegram_unanswered_info: str = "",
    ) -> Tuple[str, str, str, str, str]:  # Return (category, explanation, detailed_summary, task_text, telegram_draft_reply)
        """Use Gemini to classify the contact and generate conclusion, follow-up task, and draft reply."""
        if not self.genai_client:
            return "Boshqa", "Gemini API sozlanmagan. Standart toifa 'Boshqa' deb tanlandi.", "", "", ""

        context = {
            "lead_name": lead_name,
            "contact_name": contact_name,
            "phone": phone,
            "username": username,
            "call_summary_or_transcript": call_summary[:2000],
            "telegram_history": telegram_history[:3000],
            "lead_details": lead_details[:2000],
            "group_history": group_history[:3000],
            "tasks_history": tasks_history[:2000],
            "notes_history": notes_history[:3000],
            "telegram_unanswered_info": telegram_unanswered_info,
        }

        prompt = (
            "Siz Oisha-OS Surgical Agent tizimining aloqalarni tahlil qilish va saralash xizmatining bir bo'lagisiz. "
            "Sizga amoCRM dagi bitim nomi, bitimning to'liq har bir maydoni (field), bitimdagi izohlar va eslatmalar tarixi (notes_history), kontakt ma'lumotlari, qo'ng'iroq yozuvlari tahlili/tarixi, "
            "Telegram shaxsiy va guruh yozishmalari tarixi, amoCRM bitimidagi vazifalar (zadachalar) tarixi hamda ularga berilgan javoblar/izohlar, "
            "va Telegram chatlaridagi javobsiz qolib ketgan suhbatlar holati taqdim etiladi.\n\n"
            "Sizning vazifangiz taqdim etilgan barcha ma'lumotlarni, jumladan sdelkaning har bir fieldini, vazifalar va ularning bajarilish javoblarini, ayniqsa notes_history dagi izohlarni chuqur tahlil qilib, quyidagi natijalarni ishlab chiqish:\n\n"
            "1. **Tasniflash (category)**: Kontaktni quyidagi 5 ta toifadan faqat bittasiga tasniflash:\n"
            "   - Mijoz: Brending, SMM, sayt yaratish, dizayn kabi xizmatlarimizni so'ragan, sotib olgan, narxi yoki tijorat taklifi bilan qiziqqan har qanday shaxs.\n"
            "   - Shaxsiy: Shaxsiy oila a'zolari, do'stlar yoki biznesga mutlaqo aloqasi bo'lmagan shaxsiy masaladagi suhbatdoshlar.\n"
            "   - Kandidat: Ish so'rab kelganlar, rezyume (CV) tashlaganlar, vakansiya yoki amaliyot haqida so'raganlar.\n"
            "   - Hamkor/Jamoa: Jamoamiz a'zolari (xodimlar), hamkorlar yoki birgalikda ish olib borayotgan tashqi hamkorlar.\n"
            "   - Boshqa: Spam qo'ng'iroqlar, xato tushganlar, yoki suhbat tarixi bo'sh bo'lgan va aniq toifaga kirmaydigan kontaktlar. SHUNINGDEK, agar notes_history da mijoz bo'lmaganligi, puli qaytarilganligi yoki bitim bekor qilinganligi (masalan, 'mijozimiz emas', 'ishlab bo'lmaydi', 'pulini qaytarganmiz', 'junk', 'reject') aniq yozilgan bo'lsa, uni Boshqa toifasiga kiriting.\n\n"
            "2. **Tasniflash sababi (explanation)**: Qisqa va londa o'zbek tilida (lotin alifbosida) tasniflash sababi.\n\n"
            "3. **Mukammal Tahlil Xulosasi (detailed_summary)**: Har bir mijozning ma'lumotlarini (Telefon qo'ng'iroqlari, Telegram shaxsiy va guruh yozishmalari, sdelka maydonlari, vazifalar tarixi va ularning bajarilish izohlari) to'liq tahlil qilib, o'zbek tilida (lotin alifbosida) professional biznes-konsalting ohangida yozilgan mukammal xulosa. \n"
            "Xulosaning oxiriga har doim va faqat haqiqiy faol mijozlar uchun quyidagi maslahatni qo'shing:\n"
            "   '💡 Menejerga maslahat: Vazifa bajarilgach, uni amoCRMda \"Bajarildi\" deb belgilang va bajarilish izohini yozing. Oisha boti bajarilgan vazifalar tarixi va izohlarini to'liq tahlil qiladi va qayta takroriy vazifa yaratilishining oldini oladi.'\n\n"
            "4. **Keyingi Qadam Vazifasi (next_step_task)**: Mas'ul menejer uchun keyingi qadam bo'yicha aniq vazifa matni. \n"
            "   - **MUHIM QOIDA (Takroriy vazifalarni oldini olish va bekorchi bitimlar)**:\n"
            "     - Agar bitimdagi izohlar yoki eslatmalar (notes_history) ichida 'mijozimiz emas', 'ishlamaymiz', 'pulini qaytarganmiz', 'ishlab bo'lmaydi', 'junk' yoki shunga o'xshash mijoz bo'lmaganligi yoki bitim tugatilganligi haqidagi ma'lumotlar mavjud bo'lsa, keyingi qadam vazifasini mutlaqo yozmang (bo'sh satr '' qoldiring).\n"
            "     - Agar keyingi qadam vazifasi taqdim etilgan vazifalar tarixida (tasks_history) allaqachon bajarilgan bo'lsa yoki hozirda faol bo'lsa, xuddi shu vazifani qaytadan yaratishni tavsiya qilmang. Buning o'rniga yangi mantiqiy vazifa yozing.\n"
            "     - Agar bitim toifasi 'Boshqa' (Other) deb saralansa va faol biznes vazifasi talab etilmasa, keyingi qadam vazifasini bo'sh satr ('') qoldiring.\n"
            "     - Telegram javobsiz xabarlar: Agar 'telegram_unanswered_info' maydoni mijozning xabari javobsiz qolganini ko'rsatsa, birinchi navbatda Telegramda mijozga javob yozish vazifasini qo'ying.\n"
            "     - Agar mutlaqo yangi vazifa qo'yish shart bo'lmasa yoki barcha ishlar yakunlangan bo'lsa, 'next_step_task' maydonini bo'sh satr ('') qoldiring.\n\n"
            "5. **Telegram Draft Reply (telegram_draft_reply)**: Mijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga taklif qilinayotgan javob matni (o'zbek tilida, lotin alifbosida, samimiy va professional ohangda). Agar shaxsiy Telegram chatida mijozning xabari javobsiz qolgan bo'lsa, ushbu maydonga tahminiy javob matnini yozing. Userbot buni shaxsiy chatda avtomatik ravishda qoralama (draft) qilib qo'yadi. Agar javobsiz xabar bo'lmasa, bo'sh satr ('') qaytaring.\n\n"
            "Javobni quyidagi JSON formatida qaytaring, boshqa hech qanday qo'shimcha tushuntirish va markdown belgilari (masalan, ```json) yozmang:\n"
            "{\n"
            '  "category": "Mijoz|Shaxsiy|Kandidat|Hamkor/Jamoa|Boshqa",\n'
            '  "explanation": "Tasniflash sababi...",\n'
            '  "detailed_summary": "Tahlil xulosasi...",\n'
            '  "next_step_task": "Menejer uchun vazifa...",\n'
            '  "telegram_draft_reply": "Taklif etiladigan javob matni..."\n'
            "}\n\n"
            f"Kontekst JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        )

        try:
            kwargs = {"model": self.model_name, "contents": [prompt]}
            if genai_types is not None:
                kwargs["config"] = genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )

            # Using generate_content_with_fallback for resiliency
            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.model_name,
                contents=kwargs["contents"],
                config=kwargs.get("config"),
                env_name="GEMINI_CRM_AUDIT_FALLBACK_MODELS",
                log_prefix="[AUDITOR_GEMINI]",
            )
            text = str(getattr(response, "text", "") or "").strip()

            # Parse JSON safely
            data = {}
            if text:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    # Try regex match
                    match = re.search(r"\{.*\}", text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))

            category = data.get("category")
            explanation = data.get("explanation", "Sabab taqdim etilmadi.")
            detailed_summary = data.get("detailed_summary", f"Tizim tomonidan avtomatik tahlil: {explanation}")
            next_step_task = data.get("next_step_task", "Mijoz bilan bog'lanib, holatni aniqlashtiring.")
            telegram_draft_reply = data.get("telegram_draft_reply", "")

            valid_categories = {"Mijoz", "Shaxsiy", "Kandidat", "Hamkor/Jamoa", "Boshqa"}
            if category not in valid_categories:
                category = "Boshqa"

            return category, explanation, detailed_summary, next_step_task, telegram_draft_reply
        except Exception as e:
            logger.error("[AUDITOR] Gemini classification/analysis failed: %s", e)

            # Rules-based fallback if Gemini fails
            lowered_history = (telegram_history + " " + call_summary + " " + group_history + " " + notes_history).lower()
            category = "Boshqa"
            if any(w in lowered_history for w in ("mijozimiz emas", "ishlab bo'lmaydi", "pulini qaytar", "not a client", "junk")):
                category = "Boshqa"
                next_step_task = ""
            elif any(w in lowered_history for w in ("rezyume", "resume", "cv", "ishga", "vakansiya", "amaliyot")):
                category = "Kandidat"
                next_step_task = ""
            elif any(w in lowered_history for w in ("branding", "brending", "narxi", "narx", "site", "sayt", "logo", "smm", "dizayn")):
                category = "Mijoz"
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."
            else:
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."

            explanation = f"Xatolik tufayli qoida bo'yicha saralandi (Fallback): {str(e)}"
            detailed_summary = f"Mijoz va uning yozishmalari tahlili xatolik tufayli yakunlanmadi. Aloqa toifasi: {category}."

            return category, explanation, detailed_summary, next_step_task, ""

    async def audit_lead_by_data(self, lead: Dict[str, Any], force: bool = False) -> Optional[str]:
        """Audit and classify a single AmoCRM lead data dictionary."""
        lead_id = lead.get("id")
        if not lead_id:
            return None

        if not force and await self.is_lead_audited(int(lead_id)):
            return "skipped"

        lead_name = lead.get("name") or "Noma'lum Bitim"
        contacts = lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", [])
        
        contact_id = None
        contact_name = "Noma'lum Kontakt"
        phone = ""
        username = ""
        
        if contacts:
            contact_id = contacts[0].get("id")
            contact_name = contacts[0].get("name") or contact_name
            if contact_id:
                phone, username = await self.get_contact_phone_and_username(int(contact_id))

        # Lookup Telegram Account & chat history
        telegram_user_id = None
        telegram_history = ""
        is_unanswered_tg = False
        tg_unanswered_duration = ""
        if phone or username:
            telegram_user_id, username = await self.get_or_lookup_telegram_user(phone, username)
            if telegram_user_id:
                telegram_history, is_unanswered_tg, tg_unanswered_duration = await self.get_telegram_history_and_unanswered(telegram_user_id, limit=20)

        # Lookup Shared Group Chats & histories
        group_history_parts = []
        is_unanswered_group = False
        group_unanswered_duration = ""
        try:
            shared_groups = await self.find_shared_group_chats(lead_name, contact_name, telegram_user_id)
            for group_entity, group_title in shared_groups:
                g_hist, g_unanswered, g_duration = await self.get_group_chat_history_and_unanswered(group_entity, limit=15)
                if g_hist:
                    group_history_parts.append(f"--- Guruh: {group_title} ---\n{g_hist}")
                    if g_unanswered:
                        is_unanswered_group = True
                        group_unanswered_duration = g_duration
        except Exception as group_err:
            logger.warning("[AUDITOR] Error fetching shared group chats for lead %s: %s", lead_id, group_err)

        group_history = "\n\n".join(group_history_parts)

        # Determine Telegram unanswered status info
        telegram_unanswered_info = ""
        if is_unanswered_tg:
            telegram_unanswered_info += f"Mijoz shaxsiy telegramda oxirgi xabarni yozgan ({tg_unanswered_duration}) va javob berilmagan. "
        if is_unanswered_group:
            telegram_unanswered_info += f"Mijoz loyiha guruhida oxirgi xabarni yozgan ({group_unanswered_duration}) va javob berilmagan."
        if not telegram_unanswered_info:
            telegram_unanswered_info = "Barcha Telegram xabarlariga javob berilgan."

        # Fetch and serialize Lead Tasks
        existing_tasks = await self.get_lead_tasks(int(lead_id))
        tasks_history = self.serialize_tasks(existing_tasks)

        # Serialize Lead details
        lead_details = self.serialize_lead_details(lead)

        # Lookup call notes/transcripts
        _, call_summary = await self.get_call_notes_and_transcripts(int(lead_id), phone)

        # Fetch notes history (comments) from AmoCRM
        notes_history = await self.get_lead_notes_history(int(lead_id))

        # Classify and analyze via Gemini
        category, explanation, detailed_summary, next_step_task, telegram_draft_reply = await self.classify_contact(
            lead_name=lead_name,
            contact_name=contact_name,
            phone=phone,
            username=username,
            call_summary=call_summary,
            telegram_history=telegram_history,
            lead_details=lead_details,
            group_history=group_history,
            tasks_history=tasks_history,
            notes_history=notes_history,
            telegram_unanswered_info=telegram_unanswered_info,
        )

        # Save to DB
        await self.save_audit_result(
            lead_id=int(lead_id),
            lead_name=lead_name,
            contact_id=contact_id,
            contact_name=contact_name,
            phone=phone,
            username=username,
            telegram_user_id=telegram_user_id,
            call_summary=call_summary,
            telegram_history=telegram_history + ("\n\n" + group_history if group_history else ""),
            category=category,
            explanation=explanation,
            detailed_summary=detailed_summary,
            task_text=next_step_task,
        )

        # Add note to AmoCRM lead
        if detailed_summary:
            try:
                full_note_text = f"🤖 **Oisha-OS: Bitim va Suhbatlar Mukammal Tahlili**\n\n{detailed_summary}"
                await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), full_note_text)
                logger.info("[AUDITOR] Added audit note to AmoCRM for lead %s.", lead_id)
            except Exception as note_err:
                logger.error("[AUDITOR] Failed to add audit note to AmoCRM for lead %s: %s", lead_id, note_err)

        # Save draft in Telegram if unanswered
        if telegram_user_id and is_unanswered_tg and telegram_draft_reply:
            try:
                draft_text = telegram_draft_reply.strip()
                await self.tg_client.edit_draft(int(telegram_user_id), draft_text)
                logger.info("[AUDITOR] Saved draft reply in Telegram for user %s: %s", telegram_user_id, draft_text[:50])
                
                # Add note to AmoCRM that a draft reply has been saved
                try:
                    draft_note = f"🤖 **Oisha-OS Telegram Draft:**\nMijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga userbot orqali taklif etilgan javob qoralama (draft) sifatida saqlandi:\n\n\"{draft_text}\"\n\n*(Menejer ushbu javobni tahrirlashi yoki o'zgartirmasdan shaxsiy Telegram orqali yuborishi mumkin)*"
                    await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), draft_note)
                except Exception:
                    logger.warning("[CRM_AUDIT] Failed to add draft reply note to AmoCRM for lead %s", lead_id, exc_info=True)
            except Exception as draft_err:
                logger.error("[AUDITOR] Failed to save draft in Telegram for user %s: %s", telegram_user_id, draft_err)

        # Create task in AmoCRM (with duplication prevention)
        if next_step_task:
            next_step_task_clean = next_step_task.strip()
            # Double check duplication logic
            is_dup = self.is_duplicate_task(next_step_task_clean, existing_tasks)
            if is_dup:
                logger.info("[AUDITOR] Skipped creating duplicate task for lead %s: %s", lead_id, next_step_task_clean)
                try:
                    dup_note = f"🤖 **Oisha-OS Eslatma:**\nKeyingi qadam vazifasi ('{next_step_task_clean}') bitimda allaqachon faol yoki bajarilganligi sababli takroran yaratilmadi."
                    await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), dup_note)
                except Exception:
                    logger.warning("[CRM_AUDIT] Failed to add duplicate task note to AmoCRM for lead %s", lead_id, exc_info=True)
            else:
                try:
                    responsible_user_id = lead.get("responsible_user_id")
                    # Calculate tomorrow at 18:00 local time (GMT+5 offset)
                    from src.utils.task_scheduler import task_deadline
                    complete_till = task_deadline(due_in_hours=24)

                    task_text = f"🤖 Oisha-OS Keyingi Qadam:\n{next_step_task_clean}"
                    await self.amocrm.create_task(
                        element_id=int(lead_id),
                        text=task_text,
                        complete_till=complete_till,
                        responsible_user_id=responsible_user_id,
                    )
                    logger.info("[AUDITOR] Created follow-up task in AmoCRM for lead %s (responsible: %s).", lead_id, responsible_user_id)
                except Exception as task_err:
                    logger.error("[AUDITOR] Failed to create follow-up task in AmoCRM for lead %s: %s", lead_id, task_err)

        # Tag lead in AmoCRM automatically
        try:
            add_tag = getattr(self.amocrm, "add_lead_tag", None)
            if callable(add_tag):
                await _maybe_await(add_tag(int(lead_id), category))
                logger.info("[AUDITOR] Auto-tagged lead %s as '%s' in AmoCRM.", lead_id, category)
        except Exception as tag_err:
            logger.warning("[AUDITOR] Failed to tag lead %s as '%s' in AmoCRM: %s", lead_id, category, tag_err)

        return category

    async def run_audit(
        self,
        limit: int = 500,
        progress_callback: Optional[callable] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Main entry point. Fetches and audits leads, updates progress."""
        await self.init_db()
        
        leads = await self.fetch_recent_leads(limit=limit)
        stats = {
            "total_leads": len(leads),
            "processed": 0,
            "skipped": 0,
            "categories": {
                "Mijoz": 0,
                "Shaxsiy": 0,
                "Kandidat": 0,
                "Hamkor/Jamoa": 0,
                "Boshqa": 0,
            },
        }

        for idx, lead in enumerate(leads):
            lead_id = lead.get("id")
            if not lead_id:
                continue

            try:
                result = await self.audit_lead_by_data(lead, force=force)
                if result == "skipped":
                    stats["skipped"] += 1
                elif result:
                    stats["processed"] += 1
                    stats["categories"][result] = stats["categories"].get(result, 0) + 1
                
                # Sleep between requests to avoid rate limits
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error("[AUDITOR] Error auditing lead %s: %s", lead_id, e, exc_info=True)
                stats["processed"] += 1
                stats["categories"]["Boshqa"] += 1

            # Progress callback every 10 leads
            if progress_callback and (idx + 1) % 10 == 0:
                try:
                    await progress_callback(idx + 1, len(leads), stats)
                except Exception as cb_err:
                    logger.error("[AUDITOR] Progress callback error: %s", cb_err)

        # Final progress callback
        if progress_callback:
            try:
                await progress_callback(len(leads), len(leads), stats)
            except Exception:
                logger.debug("[CRM_AUDIT] Final progress callback failed", exc_info=True)

        return stats
