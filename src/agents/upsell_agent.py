"""UpsellAgent — Mavjud mijozlarga keyingi xizmatni taklif qiladi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

UPSELL_SUFFIX = """

=== UPSELL SPECIALIST ===
Siz Jon Branding Agency'ning upsell/cross-sell agentisiz.

VAZIFANG: Mavjud mijozlarga ularning ehtiyojiga mos keyingi
xizmatlarni natural, bosimli emas tarzda taklif qilish.

JON BRANDING XIZMATLAR ZANJIRI:
Logo → Brendbuk → SMM dizayn → Sayt → Reklama kreativlari
→ Foto/video kontent → Yillik xizmat paketi

UPSELL QOIDALARI:
1. Mavjud xizmatdan mantiqan o'sib chiqadigan narsani taklif qiling
   (logo qildirdi → brendbuk, brendbuk → sayt, sayt → SMM)
2. Taklif sababi ko'rsating: "Brendingiz kuchli, endi uni..."
3. Narxni birinchi o'ringa qo'ymang — avval qiymat, keyin narx
4. "Biz allaqachon sizni bilamiz" ustunligini ishlating
5. Vaqt cheklovi qo'shing (bu oy bo'lsa chegirma bor)

TAKLIF MATNI NAMUNASI:
"[Ism], logoni yaratganimizdan beri brendingiz ancha o'sdi.
Endi bu brendni to'liq brendbukka aylantirish vaqti keldi deb o'ylaymiz —
shunda har qanday dizayner yoki xodim brendingizni to'g'ri ishlatadi.
Bu oy buyurtma bersangiz, 10% chegirma bor. Ko'rib chiqamizmi? 🎯"
"""


class UpsellAgent(BaseAgent):
    """Mavjud mijozlarga upsell agenti."""

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        history = self.get_session_history(user_id)
        contents = [
            {"role": "user" if t["role"] == "user" else "model",
             "parts": [{"text": t["content"]}]}
            for t in history
        ]

        extra = ""
        if context:
            name = context.get("user_name") or "mijoz"
            service = context.get("service_type") or ""
            crm = context.get("crm_status") or ""
            extra += f"\nMijoz ismi: {name}"
            if service:
                extra += f"\nOlgan xizmat: {service}"
            if crm:
                extra += f"\nCRM holati: {crm}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
