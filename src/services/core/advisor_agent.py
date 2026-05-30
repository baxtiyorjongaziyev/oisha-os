import logging
import datetime
import time
from contextlib import asynccontextmanager
from typing import Optional, Any
from google import genai

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _db_connection(db: Any):
    get_conn = getattr(db, "get_conn", None)
    if callable(get_conn):
        conn_or_cm = get_conn()
        if hasattr(conn_or_cm, "__aenter__"):
            async with conn_or_cm as conn:
                yield conn
            return
        yield conn_or_cm
        return

    get_connection = getattr(db, "get_connection", None)
    if not callable(get_connection):
        raise AttributeError("db must expose get_conn() or get_connection()")

    conn = await get_connection()
    yield conn


class AdvisorAgent:
    """
    Shadow Advisor (Coach Mode) that listens to private chats and
    provides strategic advice + action suggestions to the owner.
    Now equipped with Dual-Persona intelligence.
    """

    def __init__(self, api_key: str, db, action_parser):
        self.client = genai.Client(api_key=api_key)
        self.db = db
        self.action_parser = action_parser
        self.model_name = "gemini-2.0-flash"
        from src.services.core.persona_hub import (
            INTERNAL_COO_PROMPT,
            EXTERNAL_CONCIERGE_PROMPT,
        )

        self.internal_prompt = INTERNAL_COO_PROMPT
        self.external_prompt = EXTERNAL_CONCIERGE_PROMPT

    async def generate_sales_celebration(self, manager_name: str, amount: Any) -> str:
        """
        Sotuv menejeri uchun takrorlanmas, motivatsion tabrik yaratish.
        """
        # Ensure amount is a string for the prompt
        amt_str = str(amount)
        system_instruction = f"""
        Siz jamoaning samimiy va tajribali yordamchisisiz. 
        Vazifangiz: Sotuv menejerini yangi bitim (Kirim) yoki muvaffaqiyatli yakunlangan ish bilan samimiy tabriklash.
        Uslub: {self.external_prompt}
        
        Qoidalar:
        1. Xabar jamoa guruhida (Telegram) yuboriladi. Uslubingiz iliq, ruhlantiruvchi va xuddi jilmayib turgan insondek bo'lsin.
        2. Robot ekanligingizni bildirmang.
        3. Manager ismini va bitim summasini (agar berilgan bo'lsa) albatta eslatib o'ting.
        4. Har safar har xil so'zlar ishlating.
        5. O'zbek tilida, lotin alifbosida.
        
        Javob faqat tabrik matnidan iborat bo'lsin.
        """

        prompt = f"Manager: {manager_name}, Summa: {amt_str}. Uni ajoyib sotuv bilan tabriklang!"

        try:
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction=system_instruction,
                model=self.model_name,
            )
            return (
                response.text.strip()
                if response and response.text
                else "Tabriklayman! 🎉"
            )
        except Exception as e:
            logger.error(f"[ADVISOR] Celebration generation error: {e}")
            return f"Tabriklaymiz! {manager_name} tomonidan yangi bitim yopildi: {amount} so'm. 👸🛡️"

    async def analyze_and_advise(
        self, chat_id: int, message_text: str, history_context: str, sender_name: str
    ) -> Optional[str]:
        """
        Analyzes the conversation and returns a strategic tip/action if necessary.
        """

        from src.services.core.agency_personas import AGENCY_PERSONAS
        _discovery_coach = AGENCY_PERSONAS.get("sales-discovery-coach", "")
        _sales_coach = AGENCY_PERSONAS.get("sales-coach", "")

        system_instruction = f"""
        {self.internal_prompt}

        Siz hozir "{sender_name}" va @baxtiyor_uz uchun strategik maslahatchisiz.
        Menejer "{sender_name}" mijoz bilan suhbatlashmoqda.

        DISCOVERY FRAMEWORK (amal qiling, lekin yashirin tarzda):
        {_discovery_coach}

        COACHING FRAMEWORK:
        {_sales_coach}

        Vazifangiz:
        1. Mijozning PSIXOTIPINI aniqlash (Analitik, Pragmatik, Emotsional, Shoshqaloq).
           Sandler Pain Funnel: Surface Pain → Business Impact → Personal Stakes
        2. Menejerga ushbu mijozni qanday yopish (Closing) bo'yicha tactical maslahat bering.
           Discovery gap: Nimani BILMAYMIZ? (MEDDPICC lens: Metrics, Champion, Paper Process)
        3. MIJOZ UCHUN JAVOB DRAFTLARINI TAYYORLASH (ENG MUHIMI):
           Ushbu draftlarda quyidagi personadan foydalaning:
           ---
           {self.external_prompt}
           ---

        Javob formati (O'zbek tilida):
        🧠 [PSIXOTIP]: (Uslub va qisqa asos, Pain funnel qaysi darajada?)
        💡 [STRATEGIYA]: (Discovery gap + closing taktika — SPIN/Challenger)
        ✍️ [DRAFTLAR (MIJOZGA)]:
           1. ⚡️ TEZKOR: ...
           2. 💎 EKSPERT: ...
           3. 🚀 PERSUASIVE (SOTUV): ...
        ⚙️ [ACTION]: (Agar kerak bo'lsa: [TASK:...] yoki [AMO_UPDATE:...])
        """

        contents = [
            f'Suhbat tarixi (oxirgi xabarlar):\n{history_context}\n\nYangi xabar: "{message_text}"'
        ]

        try:
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.client,
                prompt=contents,
                system_instruction=system_instruction,
                model=self.model_name,
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
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.client, prompt=[prompt], model=self.model_name
            )
            return (
                response.text.strip()
                if response and response.text
                else "Tahlil natijasi bo'sh qaytdi."
            )
        except Exception as e:
            logger.error(f"[ADVISOR] Lead context analysis error: {e}")
            return f"Xatolik yuz berdi: {e}"

    async def should_notify(
        self, chat_id: int, message_id: int, advice_content: str
    ) -> bool:
        """Checks if this advice was already sent and rate-limits advisor pings."""
        try:
            msg_key = f"advisor_notify:msg:{chat_id}:{message_id}"
            cooldown_key = f"advisor_notify:cooldown:{chat_id}"
            now = time.time()

            if await self.db.get_state(msg_key):
                return False

            last_sent_raw = await self.db.get_state(cooldown_key, "0")
            try:
                last_sent = float(last_sent_raw or 0)
            except (TypeError, ValueError):
                last_sent = 0.0
            if now - last_sent < 1800:
                logger.info(
                    f"[ADVISOR] Cooldown active for chat {chat_id}; notification skipped."
                )
                return False

            await self.db.set_state(msg_key, "sent")
            await self.db.set_state(cooldown_key, str(now))

            async with _db_connection(self.db) as conn:
                await conn.execute(
                    "INSERT INTO advisor_logs (chat_id, message_id, advice_type, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        chat_id,
                        message_id,
                        "tactical",
                        advice_content,
                        datetime.datetime.now(),
                    ),
                )
                await conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ADVISOR] DB check error: {e}")
            return False
