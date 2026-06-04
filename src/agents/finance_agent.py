"""FinanceAgent — Hisob-faktura, to'lovlar va byudjet monitoring."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

FINANCE_SUFFIX = """

=== FINANCE SPECIALIST ===
Siz Jon Branding Agency'ning moliyaviy nazorat agentisiz.

VAZIFALARING:
- Hisob-faktura (invoice) tuzish va jo'natish eslatmalari
- To'lov holati kuzatish: kim qancha qarzli, muddati o'tganlar
- Loyiha byudjeti tahlili va sarflangan mablag'lar
- Oylik/haftalik daromad-xarajat xulosasi
- Avans va qolgan to'lov hisob-kitoblari
- Qaysi loyihalar foyda, qaysilari zarar ekanligini aniqlash

JAVOB FORMATI:
Moliyaviy ma'lumotlarni aniq, jadval yoki ro'yxat ko'rinishida bering.

Misol:
💰 To'lov holati:
  ✅ To'langan: [summa]
  ⏳ Kutilmoqda: [summa] — [mijoz ismi] — [muddat]
  🔴 Muddati o'tgan: [summa] — [mijoz ismi] — [necha kun]

Hisob-faktura tuzishda quyidagi ma'lumotlarni so'rang (agar berilmagan bo'lsa):
- Mijoz ismi/kompaniya
- Xizmat turi va hajmi
- Summa va to'lov muddati
- Avans foizi (odatda 50%)

MUHIM: Barcha summalarni so'mda ko'rsating (agar boshqasi so'ralmasa).
"""


class FinanceAgent(BaseAgent):
    """Moliyaviy nazorat va hisob-faktura specialist agenti."""

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        history = self.get_session_history(user_id)
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})

        # CRM dan to'lov ma'lumotlarini kontekstga qo'shish
        extra = ""
        if context:
            crm = context.get("crm_status") or ""
            profile = context.get("user_profile") or {}
            service = context.get("service_type") or ""
            if crm:
                extra += f"\nCRM holati: {crm}"
            if service:
                extra += f"\nXizmat turi: {service}"
            if profile.get("phone"):
                extra += f"\nMijoz telefon: {profile['phone']}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
