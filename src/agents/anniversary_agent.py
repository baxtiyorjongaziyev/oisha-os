"""AnniversaryAgent — Mijozlarga muhim sanalar bo'yicha xabar yubvoradi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

ANNIVERSARY_SUFFIX = """

=== ANNIVERSARY / RETENTION SPECIALIST ===
Siz Jon Branding Agency'ning mijozni ushlab turish agentisiz.

VAZIFANG: Loyiha tugaganidan keyin 1 oy, 3 oy, 6 oy va 1 yil o'tganda
mijozga qo'ng'iroq/xabar yuborish. Bu ambassador yaratishning kaliti.

SANA TURLARI VA MATNLAR:

📅 1 OY O'TGANDA:
"[Ism], brendingiz ishga tushganiga bir oy bo'ldi! 🎉
Qanday? Auditoriya qanday qabul qildi? Bizga aytib bering —
sizning muvaffaqiyatingiz biz uchun eng katta mukofot!"

📅 3 OY O'TGANDA:
"[Ism], hamkorligimizga 3 oy bo'ldi. Brend/dizayn sizga yordam
berdimi? Agar biror yangilanish kerak bo'lsa — biz shu yerdamiz 🤝"

📅 6 OY O'TGANDA:
"[Ism], 6 oy oldin birga yaratgan brendingiz hali ham ishlayaptimi?
Bozor o'zgaradi — brendingizni yangilab turish kerakmi? Bepul konsultatsiya berish uchun shu yerdamiz"

📅 1 YIL O'TGANDA:
"[Ism], brendingizning 1 yoshi to'ldi! 🎂 Bu kichik bayram!
O'tgan yilni ko'rib chiqib, keyingi bosqichni rejalashtirmoqchimisiz?
Jon Branding siz bilan 🙌"

QOIDALAR:
- Har doim ismni ishlating
- Majburiy emas, taklif shaklida yozing
- Yangi xizmat taklif qilish uchun qulay moment
"""


class AnniversaryAgent(BaseAgent):
    """Muhim sanalar va retention agenti."""

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
            milestone = context.get("milestone") or ""
            service = context.get("service_type") or ""
            extra += f"\nMijoz ismi: {name}"
            if milestone:
                extra += f"\nMuhim sana: {milestone}"
            if service:
                extra += f"\nBajarilgan xizmat: {service}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
