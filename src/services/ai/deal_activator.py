"""
Oisha-OS: Toʻxtab qolgan mijozlarni sotuvgacha olib borish va qayta faollashtirish dvigateli.
Mijoz bilan oxirgi muloqotni tahlil qilib, aynan nima qilish va nima deyish kerakligini generatsiya qiladi.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.settings import settings

logger = logging.getLogger("DealActivator")


@dataclass
class ReEngagementPlan:
    """Mijoz bilan aloqani qayta tiklash va sotuvni yopish rejasi."""
    client_name: str
    stagnation_reason: str
    exact_action: str
    ready_to_send_script: str
    prohibited_action: str
    recommended_deadline_hours: int = 4

    def format_card(self) -> str:
        """Telegram yoki CRM uchun toʻliq tavsiya matnini shakllantirish."""
        lines = [
            f"🎯 **MIJOZNI SOTUVGACHA YETAKLASH | {self.client_name.upper()}**",
            "────────────────────────────────────────",
            f"🔍 **Toʻxtash sababi:** {self.stagnation_reason}",
            "",
            f"🛠 **AYNAN NIMA QILISH KERAK? (Taktika):**",
            f"👉 {self.exact_action}",
            "",
            f"💬 **AYNAN NIMA DEYISH KERAK? (Tayyor xabar):**",
            f"\"{self.ready_to_send_script}\"",
            "*(Shunchaki nusxa koʻchirib Telegramʼdan yuboring)*",
            "",
            f"🛑 **NIMA QILISH TAQIQLANADI?**",
            f"⚠️ {self.prohibited_action}",
            "────────────────────────────────────────",
        ]
        return "\n".join(lines)


_PROMPT_TEMPLATE = """Sen Jon Branding agentligining Bosh Sotuv Strategisan (Senior Deal Closer).
Mijoz bilan sotuvchi oʻrtasidagi yozishma maʼlum vaqt davomida toʻxtab qolgan (stagnation).

SENING VAZIFANG:
Menejerga ushbu mijozni yoʻqotib qoʻymasdan, bitimni SOTUVGACHA olib borish uchun:
1. "stagnation_reason" — Nega mijoz toʻxtab qoldi? (Asosiy ikkilanish, narx, byudjet yoki eʼtibor kamligi).
2. "exact_action" — Aynan nima qilish kerak? (Qaysi kanal, qaysi portfolio keysini koʻrsatish, ovozli xabarmi yoki matnmi).
3. "ready_to_send_script" — Aynan nima deyish kerak? (Menejer nusxalab yuboradigan juda samimiy, oʻzbekona, qiymat beruvchi va bosimsiz tayyor xabar).
4. "prohibited_action" — Nima qilish qatʼiyan taqiqlanadi? (Masalan: "Qaror qildingizmi?", "Nima boʻldi?" deb siqish).

Javobni FAQAT quyidagi JSON formatida qaytar:
{{
  "stagnation_reason": "<sabab>",
  "exact_action": "<aniq harakat>",
  "ready_to_send_script": "<tayyor soʻzma-soʻz xabar matni>",
  "prohibited_action": "<taqiqlangan xato>",
  "recommended_deadline_hours": 4
}}

Mijoz ismi: {client_name}
Oxirgi harakatdan beri oʻtgan vaqt: {idle_hours} soat
Oxirgi xabarni kim yozgan: {last_speaker}

Suhbat tarixi:
{transcript}
"""


class DealActivator:
    """Mijozlarni sotuvga yoʻnaltiruvchi faol strategiya xizmati."""

    def __init__(self, gemini_client: Optional[Any] = None) -> None:
        self._gemini_client = gemini_client

    def _get_client(self) -> Optional[Any]:
        if self._gemini_client is not None:
            return self._gemini_client
        try:
            from google import genai
            api_key = settings.GEMINI_API_KEY.get_secret_value().strip()
            if api_key:
                self._gemini_client = genai.Client(api_key=api_key)
                return self._gemini_client
        except Exception as exc:
            logger.warning("[DEAL_ACTIVATOR] Gemini client xatosi: %s", exc)
        return None

    async def generate_activation_plan(
        self,
        transcript: str,
        client_name: str = "Mijoz",
        idle_hours: float = 12.0,
        last_speaker: str = "seller",
    ) -> ReEngagementPlan:
        """Toʻxtab qolgan suhbat uchun aniq harakat va tayyor xabar rejasini tuzish."""
        client = self._get_client()
        if not client or not transcript.strip():
            return self._fallback_plan(client_name, last_speaker)

        prompt = _PROMPT_TEMPLATE.format(
            client_name=client_name or "Mijoz",
            idle_hours=round(idle_hours, 1),
            last_speaker="Menejer" if last_speaker == "seller" else "Mijoz",
            transcript=transcript[:4000],
        )

        try:
            from google.genai import types
            response, _model = await generate_content_with_fallback(
                client,
                primary_model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
                log_prefix="[DEAL_ACTIVATOR]",
            )
            raw = getattr(response, "text", "") or ""
            return self._parse_plan_json(raw, client_name, last_speaker)
        except Exception as exc:
            logger.error("[DEAL_ACTIVATOR] Reja tuzishda xatolik: %s", exc)
            return self._fallback_plan(client_name, last_speaker)

    def _parse_plan_json(
        self, raw: str, client_name: str, last_speaker: str
    ) -> ReEngagementPlan:
        """JSON javobni xavfsiz oʻqib ReEngagementPlan ga aylantirish."""
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)

        try:
            data = json.loads(clean)
        except Exception:
            return self._fallback_plan(client_name, last_speaker)

        return ReEngagementPlan(
            client_name=client_name,
            stagnation_reason=str(data.get("stagnation_reason") or "Mijoz qaror qilishda ikkilanmoqda"),
            exact_action=str(data.get("exact_action") or "Telegram orqali samimiy ovozli xabar yuborish"),
            ready_to_send_script=str(data.get("ready_to_send_script") or ""),
            prohibited_action=str(data.get("prohibited_action") or "Mijozni 'Nima boʻldi?' deb shoshiltirmang"),
            recommended_deadline_hours=int(data.get("recommended_deadline_hours") or 4),
        )

    @staticmethod
    def _fallback_plan(client_name: str, last_speaker: str) -> ReEngagementPlan:
        """AI ishlamagan holat uchun qatʼiy qoidaviy zaxira rejasi."""
        if last_speaker == "seller":
            script = (
                f"Assalomu alaykum, {client_name}! Kecha aytgan loyihangiz boʻyicha "
                "jamoamiz bilan oʻxshash muvaffaqiyatli keysimizni koʻrib chiqdik. "
                "Foydali boʻlishi uchun qisqa taqdimotni yuboraymi? 🤝"
            )
            action = "Telegramʼda soha boʻyicha Jon Branding keysini yuboring va Zoom uchrashuv taklif qiling."
            reason = "Taklif yuborilgan, lekin mijoz oʻrganishga ulgurmagan yoki narx boʻyicha ikkilanmoqda."
        else:
            script = (
                f"Assalomu alaykum, {client_name}! Savolingizni koʻrib chiqdik. "
                "Aynan sizning loyihangizga eng maqbul yechim boʻyicha variantlarni tayyorladik. "
                "Bugun soat 16:00 da 10 daqiqalik qisqa suhbat qila olamizmi?"
            )
            action = "Mijozning savoliga darhol javob berib, tashabbusni oʻz qoʻlingizga oling."
            reason = "Mijoz javob kutmoqda, tezkorlik bilan ishonchni mustahkamlash zarur."

        return ReEngagementPlan(
            client_name=client_name,
            stagnation_reason=reason,
            exact_action=action,
            ready_to_send_script=script,
            prohibited_action="Quruq 'Qaror qildingizmi?' yoki 'Nima boʻldi?' deb bosim oʻtkazish taqiqlanadi.",
            recommended_deadline_hours=4,
        )
