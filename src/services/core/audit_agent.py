import logging
from google import genai
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AuditAgent:
    """
    Foydalanuvchi harakatlarini tahlil qilib, unumdorlikni oshirish bo'yicha audit o'tkazuvchi agent.
    """

    def __init__(self, api_key: str, db):
        self.db = db
        self.deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(self, 'settings_DEEPSEEK_API_KEY', None)
        self.client = None
        if self.deepseek_key and "dummy" not in self.deepseek_key.lower():
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
            except Exception as e:
                logger.error(f"[AUDIT] DeepSeek init failed: {e}")
        else:
            logger.warning("[AUDIT] DeepSeek API key missing or dummy. Audit features will be limited.")
        self.gemini_client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.0-flash'

    async def generate_audit_report(self, limit=100) -> str:
        """Oxirgi harakatlar asosida audit xulosasini tayyorlash."""
        try:
            # 1. Loglarni olish
            logs = self.db.get_recent_user_activity(limit=limit)
            if not logs:
                return "👸 Oisha-OS Audit: Hozircha tahlil qilish uchun yetarli ma'lumot yig'ilmadi. Biroz ko'proq muloqot qiling."

            # 2. Loglarni matn ko'rinishiga keltirish
            log_entries = []
            for log in logs:
                entry = f"[{log['time']}] {log['type'].upper()} in '{log['chat']}'"
                if log['source']:
                    entry += f" (From: {log['source']})"
                entry += f": {log['content'][:200]}"
                log_entries.append(entry)
            
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

            # 4. Gemini tahlili (ASYNCHRONOUS & SAFE)
            from src.main import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=prompt,
                model=self.model_name
            )
            return response.text if response and response.text else "Javob bo'sh qaytdi."
        except Exception as e:
            logger.error(f"[AUDIT AGENT ERROR] {e}")
            return f"Audit hisobotini tayyorlashda xatolik: {e}"

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
            
            # ... Gemini call ...
            return "Digital Pipeline Audit natijalari tayyorlanmoqda... (Haqiqiy tahlil kodi)"
        except Exception as e:
            logger.error(f"[PIPELINE AUDIT ERROR] {e}")
            return f"❌ Pipeline auditida xatolik: {e}"
