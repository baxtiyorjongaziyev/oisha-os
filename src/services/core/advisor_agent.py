
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
        Siz jamoaning samimiy va tajribali yordamchisisiz. 
        Vazifangiz: Sotuv menejerini yangi bitim (Kirim) yoki muvaffaqiyatli yakunlangan ish bilan samimiy tabriklash.
        
        Qoidalar:
        1. Xabar jamoa guruhida (Telegram) yuboriladi. Uslubingiz iliq, ruhlantiruvchi va xuddi jilmayib turgan insondek bo'lsin.
        2. Robot ekanligingizni bildirmang. 'Enterprise AI' yoki 'Operatsion tizim' kabi so'zlarni ishlatmang.
        3. Manager ismini va bitim summasini (agar berilgan bo'lsa) albatta eslatib o'ting.
        4. Har safar har xil so'zlar ishlating, xuddi inson har kuni bir xil gapirmaganidek.
        5. O'zbek tilida, lotin alifbosida.
        6. Emoji'lardan ham o'z o'rnida, insoniy tarzda foydalaning (masalan: 🎉, 🚀, 🙌, 👏). Robotic 👸🤴🛡️ belgilaridan qoching.
        
        Javob faqat tabrik matnidan iborat bo'lsin.
        """
        
        prompt = f"Manager: {manager_name}, Summa: {amt_str}. Uni ajoyib sotuv bilan tabriklang!"
        
        try:
            from src.main import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction=system_instruction,
                model=self.model_name
            )
            return response.text.strip() if response and response.text else "Tabriklayman! 🎉"
        except Exception as e:
            logger.error(f"[ADVISOR] Celebration generation error: {e}")
            return f"Tabriklaymiz! {manager_name} tomonidan yangi bitim yopildi: {amount} so'm. 👸🛡️"

    async def analyze_and_advise(self, chat_id: int, message_text: str, history_context: str, sender_name: str) -> Optional[str]:
        """
        Analyzes the conversation and returns a strategic tip/action if necessary.
        """
        
        system_instruction = f"""
        Siz {sender_name} va @baxtiyor_uz uchun shaxsiy maslahat chi va yordamchisiz.
        Hozir menejer "{sender_name}" mijoz bilan suhbatlashmoqda.
        
        Sizning vazifangiz (Shadow Mode):
        1. Suhbatni tahlil qilish va menejerga eng samarali keyingi qadamni ko'rsatish.
        2. Mijozning PSIXOTIPINI aniqlash (Analitik, Pragmatik, Emotsional, Shoshqaloq).
        3. Robotligingizni bildirmasdan, tajribali hamkasbdek maslahat bering.
        4. Mijozga TO'G'RIDAN-TO'G'RI yozmang. Faqat ichki guruhga tavsiya bering.
        
        Javob formati (O'zbek tilida):
        🧠 [PSIXOTIP]: (Mijozning uslubini 1 ta so'zda ayting va qisqa asoslang)
        💡 [MASLAHAT]: (Vaziyat tahlili va amaliy tavsiya)
        ✍️ [DRAFT]: (Menejer nusxalab yuborishi uchun 3 xil uslubdagi javob varianti: Tezkor, Ekspert, Sotuvga yo'naltirilgan)
        ⚙️ [ACTION]: (Agar tizimda biror narsani o'zgartirish kerak bo'lsa, Action Taglar: [CALENDAR_EVENT:...] yoki [TASK:...])
        """

        contents = [
            f"Suhbat tarixi (oxirgi xabarlar):\n{history_context}\n\nYangi xabar: \"{message_text}\""
        ]

        try:
            from src.main import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=contents,
                system_instruction=system_instruction,
                model=self.model_name
            )
            
            if response and response.text and len(response.text.strip()) > 5:
                return response.text.strip()
        except Exception as e:
            logger.error(f"[ADVISOR] Analysis error: {e}")
            
        return None

    async def analyze_lead_context(self, prompt: str) -> str:
        """
        Deep analysis of client context for onboarding briefings.
        """
        try:
            from src.main import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                model=self.model_name
            )
            return response.text.strip() if response and response.text else "Tahlil natijasi bo'sh qaytdi."
        except Exception as e:
            logger.error(f"[ADVISOR] Lead context analysis error: {e}")
            return f"Xatolik yuz berdi: {e}"

    async def should_notify(self, chat_id: int, message_id: int, advice_content: str) -> bool:
        """Checks if this advice was already sent to avoid spam."""
        try:
            async with await self.db.get_connection() as conn:
                async with conn.execute("SELECT 1 FROM advisor_logs WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)) as cursor:
                    exists = await cursor.fetchone()
                    if exists:
                        return False
                
                # Log it now
                await conn.execute(
                    "INSERT INTO advisor_logs (chat_id, message_id, advice_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, message_id, 'tactical', advice_content, datetime.datetime.now())
                )
                await conn.commit()
                return True
        except Exception as e:
            logger.error(f"[ADVISOR] DB check error: {e}")
            return True
