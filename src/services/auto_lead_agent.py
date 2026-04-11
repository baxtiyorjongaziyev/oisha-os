
import logging
import json
import datetime
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class AutoLeadAgent:
    """
    Agent that analyzes incoming Telegram messages to extract lead information
    for automatic AmoCRM synchronization.
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    async def extract_lead_info(self, message_text: str, user_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses the message and user profile to extract structured lead data.
        """
        
        system_instruction = """
        Siz Oisha-OS Elite Lead Analyzer xizmatisiz. 
        Vazifangiz: Mijozning Telegram xabarini tahlil qilib, AmoCRM uchun ma'lumot chiqarish va mijozning maqsadini (intent) toifaga ajratish.
        
        Toifalar (intent_category):
        - HOT_LEAD: Darhol xarid qilishga tayyor, narx so'ragan yoki uchrashuv belgilamoqchi bo'lganlar (🔥).
        - POTENTIAL: Kelajakda hamkorlik qilishi mumkin bo'lgan, professional savollar berganlar (🌱).
        - VIP_CLIENT: Mavjud sodiq mijozlar, katta loyihalar ustida ishlayotganlar yoki VIP statusdagilar (👑).
        - PARTNER: Hamkorlar, agentliklar yoki birgalikda loyiha qilmoqchi bo'lganlar (🤝).
        - CONTENT: Portfolio, materiallar, taqdimot yoki branding namunalarini so'raganlar (📚).
        - NETWORKING: Networking, Random Coffee yoki shunchaki tanishish maqsadida yozganlar (☕️).
        - SUPPORT: Texnik yordam, joriy loyiha bo'yicha savol yoki shikoyat (🛠).
        - TEAM: Jamoa a'zolari, xodimlar yoki ish so'rab yozganlar (👥).
        - SPAM: Reklama, keraksiz xabarlar yoki tushunarsiz kontent (🚫).
        
        Quyidagi JSON formatda javob bering:
        {
          "is_lead": boolean,
          "intent_category": "HOT_LEAD" | "POTENTIAL" | "VIP_CLIENT" | "PARTNER" | "CONTENT" | "NETWORKING" | "SUPPORT" | "TEAM" | "SPAM",
          "first_name": string,
          "last_name": string,
          "phone": string,
          "city": string,      // Shahar/Viloyat (Yashash yoki biznes joylashuvi)
          "activity": string,  // Faoliyat turi/Sohasi (Mebel, IT, Savdo va h.k.)
          "brand_name": string, // Brend nomi / Kompaniya nomi
          "business": string,  // Umumiy biznes ma'lumoti
          "needs": string,     // Mijozning ehtiyoji
          "confidence_score": number
        }
        
        MUHIM (Filtrni yanada aqlli qiling): 
        - Agar foydalanuvchi "Logo", "Branding", "Sayt", "Dizayn", "Marketing", "Random Coffee" yoki "Uchrashuv" so'zlarini aytgan bo'lsa, uni ALBATTA HOT_LEAD, POTENTIAL yoki NETWORKING deb hisoblang.
        - "JonBranding" yoki "Oisha" jamoasiga tegishli xabarlarni TEAM qiling.
        
        Faqat JSON qaytaring.
        """

        prompt = f"""
        Mijoz Profili: {json.dumps(user_profile)}
        Xabar matni: "{message_text}"
        """

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                data = json.loads(response.text)
                # Ensure we always have an intent_category
                if "intent_category" not in data:
                    data["intent_category"] = "POTENTIAL" if data.get("is_lead") else "SPAM"
                return data
        except Exception as e:
            logger.error(f"[AUTO_LEAD] Error extracting info: {e}")
            
        return None
