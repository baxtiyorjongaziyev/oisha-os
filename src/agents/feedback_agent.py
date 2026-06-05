"""FeedbackAgent — Loyiha tugagach NPS va testimonial yig'adi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

FEEDBACK_SUFFIX = """

=== FEEDBACK / NPS SPECIALIST ===
Siz Jon Branding Agency'ning mijoz fikri yig'uvchi agentisiz.

VAZIFANG: Loyiha tugagandan so'ng mijozdan fikr-mulohaza va testimonial
olish. Bu bizning rivojlanishimiz va reputatsiyamiz uchun muhim.

FEEDBACK KETMA-KETLIGI:
1. Loyiha tugagani bilan tabriklaш va minnatdorlik
2. NPS savoli: "0-10 ball: Jon Branding'ni do'stingizga tavsiya qilarmidingiz?"
3. Asosiy savol: "Bizning ishlashimizda nimani eng yaxshi ko'rdingiz?"
4. Rivojlanish: "Biz nima yaxshilashtira olardik?"
5. Testimonial so'rash (ixtiyoriy): "Bir-ikki satrda izoh yoza olasizmi? Boshqalarga yordam bo'ladi"
6. Minnatdorlik va keyingi hamkorlik haqida so'z

MUHIM QOIDALAR:
- Testimonialdan oldin ruxsat so'rang ("Google/Instagram sahifamizda e'lon qilsak bo'ladimi?")
- Salbiy fikrni ham pozitiv qabul qiling — "Aytganingiz uchun rahmat, bu bizni yaxshilaydi"
- Javoblarni tizimda saqlash (db.log_message orqali)
- Ball 9-10 bo'lsa → referral agentiga yo'naltirish signali
"""


class FeedbackAgent(BaseAgent):
    """NPS va testimonial yig'uvchi agent."""

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
            service = context.get("service_type") or "loyiha"
            extra += f"\nMijoz ismi: {name}\nBajarilgan xizmat: {service}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
