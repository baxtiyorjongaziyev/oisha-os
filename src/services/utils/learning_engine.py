import logging
import json
from google import genai

logger = logging.getLogger(__name__)


class LearningEngine:
    def __init__(self, api_keys, db):
        self.api_keys = api_keys
        self.db = db
        self.model_id = "gemini-2.0-flash"
        # Gemini key bo'lsa clientni ochish
        self.client = None
        if isinstance(api_keys, dict) and "gemini" in api_keys:
            self.client = genai.Client(api_key=api_keys["gemini"])
        elif isinstance(api_keys, str):  # Old backward compatibility
            self.client = genai.Client(api_key=api_keys)

    async def analyze_and_learn(self, user_id, history):
        """Chat tarixini tahlil qilib, yangi bilimlarni ajratib olish."""
        if not history or len(history) < 4:  # Kamida 2 ta savol-javob bo'lishi kerak
            return 0

        # Tarixni matn ko'rinishiga o'tkazish
        chat_text = ""
        for entry in history[-10:]:  # Oxirgi 10 ta xabar tahlil uchun yetarli
            role = "Aisha (AI)" if entry["role"] == "model" else "Mijoz"
            chat_text += f"{role}: {entry['parts'][0]['text']}\n"

        prompt = f"""
Siz tahlilchi AIsiz. Quyidagi chat tarixini o'rganib chiqing va biznes (JonBranding) yoki Baxtiyorjon Gaziyev uchun foydali bo'lgan YANGI BILIMLARNI (Learned Facts) ajratib oling.

Maqsad: Keyingi safar Aisha (AI) ushbu bilimlarni eslab qolishi va ishlata olishi kerak.

Qoidalar:
1. FAQAT yangi va muhim ma'lumotlarni oling (masalan: mijozning dizayn bo'yicha maxsus didi, loyiha haqidagi kutilmagan detallar, Baxtiyorjonning yangi aytgan rejasi yoki narxi).
2. Allaqachon tizimda bor bo'lgan standart ma'lumotlarni (Ism, Telefon, Hudud) qayta yozmang.
3. Javobni FAQAT JSON formatida qaytaring: {{"facts": [{{"key": "qisqa_nom", "value": "to'liq_fakt_mazmuni"}}]}}
4. Agar yangi va foydali bilim topilmasa, {{"facts": []}} qaytaring.

CHAT TARIXI:
{chat_text}
"""

        try:
            from src.main import safe_ai_call

            response = await safe_ai_call(
                client=self.client,
                prompt=prompt,
                model=self.model_id,
                mime_type="application/json",
            )

            if not response:
                return 0

            # JSON-ni tozalash (ba'zida AI markdown bloklariga o'raydi)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()

            result = json.loads(text)
            facts = result.get("facts", [])

            added_count = 0
            for fact in facts:
                key = fact.get("key")
                value = fact.get("value")
                if key and value:
                    if self.db.add_learned_fact(key, value, user_id):
                        added_count += 1
                        logger.info(
                            f"[LEARNING] Yangi bilim saqlandi: {key} -> {value}"
                        )

            return added_count
        except Exception as e:
            logger.error(f"[LEARNING ERROR] {e}")
            return 0
