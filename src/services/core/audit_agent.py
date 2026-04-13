import logging
from google import genai
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AuditAgent:
    """
    Foydalanuvchi harakatlarini tahlil qilib, unumdorlikni oshirish bo'yicha audit o'tkazuvchi agent.
    """

    def __init__(self, api_key: str, db):
        self.api_key = api_key
        self.db = db
        self.client = genai.Client(api_key=api_key)
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
            return f"❌ Audit o'tkazishda xatolik yuz berdi: {str(e)}"
