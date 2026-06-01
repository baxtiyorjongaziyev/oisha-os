import logging
import os

from src.settings import settings
import json
import re
import time
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(?:(?:\+|00)?998[\s\-()]*)?(?:\d[\s\-()]*){9,12}")


def detect_non_customer_context(message_text: str) -> str:
    """Return a reason when text is internal/personal, not a customer lead."""
    lowered = (message_text or "").lower()
    if not lowered.strip():
        return ""

    if "sotuv skript" in lowered and (
        "tasdiq" in lowered or "to'g'ri" in lowered or "tog'ri" in lowered
    ):
        return "internal_sales_script_review"
    if "baholash mezonlari" in lowered and "menejer" in lowered:
        return "internal_sales_quality_rubric"
    if (
        "jon branding agency" in lowered
        and "tavsif:" in lowered
        and "xizmat yo" in lowered
        and "baholash mezonlari" in lowered
    ):
        return "internal_company_script_document"
    if re.search(
        r"@?\w+\s+aka\b.*(tasdiq|tasdiqlab|to'g'ri|tog'ri|skript)", lowered, re.DOTALL
    ):
        return "personal_advice_request"
    if "shu sotuv" in lowered and (
        "tasdiq" in lowered or "to'g'ri" in lowered or "tog'ri" in lowered
    ):
        return "internal_sales_review_request"
    return ""


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return ""


class AutoLeadAgent:
    """
    Agent that analyzes incoming Telegram messages to extract lead information
    for automatic AmoCRM synchronization.
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = os.getenv("GEMINI_AUTO_LEAD_MODEL", settings.GEMINI_CALL_MODEL)
        self._cooldown_until = 0.0
        self._last_quota_warning = 0.0

    def _is_quota_error(self, exc: Exception) -> bool:
        err = str(exc)
        return "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower()

    def _extract_phone(self, text: str) -> str:
        for match in _PHONE_RE.finditer(text or ""):
            phone = _normalize_phone(match.group(0))
            if phone:
                return phone
        return ""

    def _fallback_extract_lead_info(
        self,
        message_text: str,
        user_profile: Dict[str, Any],
        reason: str = "ai_unavailable",
    ) -> Optional[Dict[str, Any]]:
        """Cheap deterministic fallback used when Gemini quota is exhausted."""
        text = message_text or ""
        lowered = text.lower()
        phone = self._extract_phone(text)

        hot_terms = (
            "narx",
            "qancha",
            "uchrash",
            "konsultatsiya",
            "logo",
            "branding",
            "sayt",
            "dizayn",
        )
        lead_terms = hot_terms + (
            "marketing",
            "portfolio",
            "xizmat",
            "brend",
            "reklama",
            "smm",
            "kerak",
        )
        team_terms = ("jonbranding", "oisha-os", "oisha", "admin", "pm")

        if any(term in lowered for term in team_terms):
            intent = "TEAM"
            is_lead = False
        elif phone or any(term in lowered for term in hot_terms):
            intent = "HOT_LEAD"
            is_lead = True
        elif any(term in lowered for term in lead_terms):
            intent = "POTENTIAL"
            is_lead = True
        else:
            return None

        first_name = str(
            user_profile.get("first_name")
            or user_profile.get("name")
            or user_profile.get("username")
            or ""
        ).strip()
        return {
            "is_lead": is_lead,
            "intent_category": intent,
            "first_name": first_name,
            "last_name": str(user_profile.get("last_name") or "").strip(),
            "phone": phone,
            "city": "",
            "activity": "",
            "brand_name": "",
            "business": "",
            "needs": text[:300],
            "summary": f"AI quota sabab fallback tahlil ({reason}). Signal: {intent}",
            "coaching_tip": "AI quota band: avval ehtiyoj va muddatni aniqlang, keyin keyingi qadamni belgilang.",
            "confidence_score": 0.55 if is_lead else 0.35,
        }

    async def generate_content(self, prompt: str) -> str:
        """Shared lightweight AI provider interface used by SalesCoach."""
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=[prompt],
        )
        return response.text or ""

    async def qualify_chat(self, chat_text: str) -> tuple[bool, Dict[str, Any]]:
        """
        Backward compatible wrapper for extract_lead_info.
        Returns:
            (is_lead, lead_details_dict)
        """
        user_profile = {"source": "Chat History Analysis"}
        res = await self.extract_lead_info(chat_text, user_profile)
        if not res:
            return False, {}

        is_lead = res.get("is_lead", False)
        # Add summary field if missing for scraper compatibility
        if "summary" not in res:
            res["summary"] = (
                f"Intent: {res.get('intent_category')}. Needs: {res.get('needs', 'N/A')}"
            )

        return is_lead, res

    async def extract_lead_info(
        self, message_text: str, user_profile: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the message and user profile to extract structured lead data.
        """
        non_customer_reason = detect_non_customer_context(message_text)
        if non_customer_reason:
            return {
                "is_lead": False,
                "intent_category": "TEAM",
                "first_name": str(
                    user_profile.get("first_name") or user_profile.get("name") or ""
                ).strip(),
                "last_name": str(user_profile.get("last_name") or "").strip(),
                "phone": "",
                "city": "",
                "activity": "",
                "brand_name": "",
                "business": "",
                "needs": "",
                "summary": f"Ichki/shaxsiy kontekst: {non_customer_reason}. Lead emas.",
                "coaching_tip": "CRMga kiritmang; bu mijoz murojaati emas.",
                "confidence_score": 0.99,
            }

        if time.monotonic() < self._cooldown_until:
            return self._fallback_extract_lead_info(
                message_text, user_profile, reason="quota_cooldown"
            )

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
          "summary": string,   // Qisqa tahlil (menejer uchun)
          "coaching_tip": string, // Sotuv menejeriga tavsiya: mijoz bilan qanday gaplashish, nimalarga e'tibor berish kerak (Metasell-style coach tip)
          "confidence_score": number
        }
        
        MUHIM (Filtrni yanada aqlli qiling): 
        - Agar foydalanuvchi "Logo", "Branding", "Sayt", "Dizayn", "Marketing", "Random Coffee" yoki "Uchrashuv" so'zlarini aytgan bo'lsa, uni ALBATTA HOT_LEAD, POTENTIAL yoki NETWORKING deb hisoblang.
        - "coaching_tip" maydonida o'zbek tilida sotuv menejeriga juda qisqa va kreativ maslahat bering (masalan: "Mijozni natijaga qiziqtiring", "Portfolioni darhol tashlamang, avval ehtiyojini aniqlang").
        - "JonBranding" yoki "Oisha" jamoasiga tegishli xabarlarni TEAM qiling.
        - Sotuv skripti, baholash mezoni, ichki hujjat, "tasdiqlab bering", "@... aka shu to'g'rimi" kabi maslahat/review xabarlarini TEAM qiling va is_lead=false qaytaring.
        
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
                    response_mime_type="application/json",
                ),
            )

            if response.text:
                data = json.loads(response.text)
                # Ensure we always have an intent_category
                if "intent_category" not in data:
                    data["intent_category"] = (
                        "POTENTIAL" if data.get("is_lead") else "SPAM"
                    )
                return data
        except Exception as e:
            if self._is_quota_error(e):
                self._cooldown_until = time.monotonic() + 300
                now = time.monotonic()
                if now - self._last_quota_warning > 60:
                    logger.warning(
                        "[AUTO_LEAD] Gemini quota exhausted; using deterministic fallback for 5 minutes."
                    )
                    self._last_quota_warning = now
                return self._fallback_extract_lead_info(
                    message_text, user_profile, reason="quota_429"
                )
            logger.error(f"[AUTO_LEAD] Error extracting info: {type(e).__name__}: {e}")

        return None
