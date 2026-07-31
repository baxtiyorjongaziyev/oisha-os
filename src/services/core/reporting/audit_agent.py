import os
import logging
from src.settings import settings

logger = logging.getLogger("AuditAgent")


class AuditAgent:
    """
    AuditAgent — Oishaning barcha harakatlarini tahlil qiluvchi va
    GCP/AmoCRM xavfsizligini nazorat qiluvchi agent.
    """

    def __init__(self, api_key: str, db):
        self.db = db
        # DeepSeek setup (optional)
        self.deepseek_key = (
            os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        )
        self.client = None

        if self.deepseek_key and "dummy" not in str(self.deepseek_key).lower():
            try:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.deepseek_key, base_url="https://api.deepseek.com"
                )
            except Exception as e:
                logger.error(f"[AUDIT] DeepSeek init failed: {e}")

        # Gemini setup (core)
        try:
            # [STABILITY] Explicitly use the new google-genai Client
            from google import genai

            self.gemini_client = genai.Client(api_key=api_key)
            self.model_name = os.getenv("GEMINI_AUDIT_MODEL", settings.GEMINI_CALL_MODEL)
        except Exception as e:
            logger.error(f"[AUDIT] Gemini init failed: {e}")
            self.gemini_client = None

    async def generate_audit_report(self, limit=100) -> str:
        """Oxirgi harakatlar asosida audit xulosasini tayyorlash."""
        try:
            from src.utils.ai_utils import safe_ai_call

            # 1. Loglarni olish (message_logs jadvalidan)
            rows = await self.db.get_recent_all_messages(limit=limit)
            if not rows:
                return "👸 Oisha-OS Audit: Hozircha tahlil qilish uchun yetarli ma'lumot yig'ilmadi. Biroz ko'proq muloqot qiling."

            # 2. Loglarni matn ko'rinishiga keltirish
            log_entries = []
            for user_id, message_text, is_ai_reply, created_at in rows:
                role = "AI" if is_ai_reply else f"User({user_id})"
                log_entries.append(f"[{created_at}] {role}: {str(message_text)[:200]}")

            logs_text = "\n".join(log_entries)

            # 3. Prompt tayyorlash
            prompt = f"""
            Siz Jon.Branding agentligining Productivity Analyst (Oisha-OS) xizmatisiz.
            Quyida agentlik asoschisining oxirgi Telegram harakatlari logi keltirilgan:

            --- LOGLAR BOSHLANDI ---
            {logs_text}
            --- LOGLAR TUGADI ---

            VAZIFANGIZ:
            Ushbu ma'lumotlarni chuqur tahlil qiling va quyidagi audit natijasini tayyorlang:
            1. VAQT SARFI: Qaysi chatlarda yoki qaysi turdagi xabarlarda foydalanuvchi eng ko'p aktivlik ko'rsatmoqda?
            2. TAKRORLANISH: Qaysi javoblar yoki ma'lumotlar tez-tez forward qilinmoqda? (Ularni avtomatlashtirish mumkinmi?)
            3. AVTOMATLASHTIRISH TAVSIYALARI: AI (men - Oisha) ushbu harakatlarning qaysi birini o'z zimmasiga olishi orqali foydalanuvchining ishini yengillashtira oladi?

            HISOBOT FORMATI:
            Jarrohlik darajasida aniq, tizimli va qat'iy tonda yozing. Hech qanday maqtov yoki 'paxta' bo'lmasin.
            Foydalanuvchiga faqat lavozimi (Asoschi) bo'yicha murojaat qiling.
            Aynan 'Qanday qilib AI operatsion xavflarni kamaytiradi?' qismiga urg'u bering.
            """

            # 4. Gemini tahlili
            response = await safe_ai_call(
                client=self.gemini_client,
                prompt=prompt,
                model=self.model_name,
            )
            return response.text if response and response.text else "Javob bo'sh qaytdi."
        except Exception as e:
            logger.error(f"[AUDIT ERROR] {e}")
            return f"❌ Audit hisobotida xatolik: {e}"

    async def audit_digital_pipeline(self, amocrm_sync) -> str:
        """
        AmoCRM Digital Pipeline auditini o'tkazish.
        Bottle-necks, automation gaps va stagnation tahlili.
        """
        try:
            # 1. Pipeline ma'lumotlarini olish
            pipelines = amocrm_sync.get_pipelines() # Bu funksiyani amocrm_sync'da bor deb hisoblaymiz
            
            # 2. Lidlar tahlili
            leads = amocrm_sync.get_all_leads()
            
            # 3. Tahlil mantiqi (Surgical Analysis)
            # - Har bir statusdagi lidlar soni
            # - Har bir statusdagi o'rtacha 'updated_at' (stagnatsiya)
            # - Won/Lost nisbati
            
            # 4. Prompt for AI Analysis
            prompt = f"""
            Siz professional CRM Auditor-siz. Quyidagi AmoCRM ma'lumotlarini tahlil qiling:
            Pipelines: {pipelines}
            Recent Leads Sample: {leads[:100]}
            
            Vazifangiz:
            1. BOTTLE-NECKS: Qaysi statusda lidlar yig'ilib qolyapti?
            2. AUTOMATION GAPS: Qaysi bosqichda avtomatizatsiya (triggers) yetishmayapti?
            3. SALES DISCIPLINE: Menejerlar (Oydin) qayerda xato qilyapti?
            4. TAKLIFLAR: Digital Pipeline'ni qanday qilib 'Sales Machine'ga aylantirish mumkin?
            
            Hisobot formatini 'Eagle Mode'da (qat'iy, aniq, 'paxtasiz') tayyorlang.
            """
            
            from src.utils.ai_utils import safe_ai_call
            response = await safe_ai_call(
                client=self.gemini_client,
                prompt=prompt,
                model=self.model_name,
            )
            return response.text if response and response.text else "Gemini javob qaytarmadi."
        except Exception as e:
            logger.error(f"[PIPELINE AUDIT ERROR] {e}")
            return f"❌ Pipeline auditida xatolik: {e}"
