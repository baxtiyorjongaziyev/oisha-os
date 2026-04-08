
import logging
import datetime
from typing import Optional, List, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class AdvisorAgent:
    """
    Shadow Advisor (Coach Mode) that listens to private chats and 
    provides strategic advice + action suggestions to the owner.
    """

    def __init__(self, api_key: str, db, action_parser):
        self.client = genai.Client(api_key=api_key)
        self.db = db
        self.action_parser = action_parser
        self.model_name = "gemini-2.0-flash"

    async def generate_sales_celebration(self, manager_name: str, amount: Any) -> str:
        """
        Sotuv menejeri uchun takrorlanmas, motivatsion tabrik yaratish.
        """
        # Ensure amount is a string for the prompt
        amt_str = str(amount)
        system_instruction = """
        Siz Oishasiz — Jon.Branding agentligining 'Enterprise AI' operatsion tizimisiz.
        Vazifangiz: Sotuv menejerini yangi bitim (Kirim) bilan tabriklash.
        
        Qoidalar:
        1. Jamoa guruhiga yuboriladi, shuning uchun juda professional, quvnoq va yuqori darajada ('High-Service') bo'lsin.
        2. Har safar har xil so'zlar ishlating (shablon bo'lmasin).
        3. Manager ismini va bitim summasini albatta eslatib o'ting.
        4. Brending ruhida (Branding, WOW-service, Elite) yozing.
        5. Uzbek tilida, lotin alifbosida.
        6. Emoji'lardan chiroyli foydalaning. 👰👑👸🛡️
        
        Javob faqat tabrik matnidan iborat bo'lsin.
        """
        
        prompt = f"Manager: {manager_name}, Summa: {amt_str}. Uni ajoyib sotuv bilan tabriklang!"
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )
            return response.text.strip() if response.text else "Tabriklayman! 🎉"
        except Exception as e:
            logger.error(f"[ADVISOR] Celebration generation error: {e}")
            return f"Tabriklaymiz! {manager_name} tomonidan yangi bitim yopildi: {amount} so'm. 👸🛡️"

    async def analyze_and_advise(self, chat_id: int, message_text: str, history_context: str, sender_name: str) -> Optional[str]:
        """
        Analyzes the conversation and returns a strategic tip/action if necessary.
        """
        
        system_instruction = f"""
        👸 **OISHA-OS: STRATEGIK SHADOW ADVISOR** 👸
        Siz @baxtiyor_uz (Agentlik rahbari) va uning jamoasi uchun shaxsiy Strategik Mentor va Biznes Coachsiz.
        Hozir user "{sender_name}" ismli mijoz bilan Telegramda suhbatlashmoqda.
        
        Sizning vazifangiz (Shadow Mode):
        1. Suhbatni tahlil qilish va menejerga eng to'g'ri keyingi qadamni ko'rsatish.
        2. Mijozga TO'G'RIDAN-TO'G'RI yozmaslik.
        3. Faqat jamoaga (ichki guruhga) maslahat va TAYYOR JAVOB (Draft) berish.
        
        Javob formati (O'zbek tilida):
        💡 [MASLAHAT]: (Vaziyat tahlili va taktika)
        ✍️ [DRAFT]: (Menejer nusxalab yuborishi uchun tayyor, samimiy va professional javob)
        ⚙️ [ACTION]: (Agar statusni o'zgartirish yoki vazifa qo'shish kerak bo'lsa, Action Taglar: [CALENDAR_EVENT:...] yoki [TASK:...])
        
        Tahlil qoidalari:
        - Agar uchrashuv belgilash kerak bo'lsa, uchrashuv vaqtini so'raydigan draft bering.
        - Agar mijoz e'tiroz bildirsa (narx qimmat desa), unga qiymatni tushuntiruvchi draft bering.
        - Agar gap shaxsiy bo'lsa (ishga aloqador bo'lmasa), FAQAT bo'sh joy qaytaring.
        """

        contents = [
            f"Suhbat tarixi (oxirgi xabarlar):\n{history_context}\n\nYangi xabar: \"{message_text}\""
        ]

        try:
            # Using synchronous-looking API but in the new SDK it supports async through wrappers or 
            # we just call it directly as it's a small blocking call in a task.
            # However, for userbot safety, we'll try to keep it non-blocking.
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )
            
            if response.text and len(response.text.strip()) > 5:
                # Filter out pure hallucinations if AI tried to "reply" as Oisha
                return response.text.strip()
        except Exception as e:
            logger.error(f"[ADVISOR] Analysis error: {e}")
            
        return None

    async def analyze_lead_context(self, prompt: str) -> str:
        """
        Deep analysis of client context for onboarding briefings.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.7
                )
            )
            return response.text.strip() if response.text else "Tahlil natijasi bo'sh qaytdi."
        except Exception as e:
            logger.error(f"[ADVISOR] Lead context analysis error: {e}")
            return f"Xatolik yuz berdi: {e}"

    def should_notify(self, chat_id: int, message_id: int, advice_content: str) -> bool:
        """Checks if this advice was already sent to avoid spam."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM advisor_logs WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
            exists = cursor.fetchone()
            if exists:
                return False
            
            # Log it now
            cursor.execute(
                "INSERT INTO advisor_logs (chat_id, message_id, advice_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, message_id, 'tactical', advice_content, datetime.datetime.now())
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ADVISOR] DB check error: {e}")
            return True
