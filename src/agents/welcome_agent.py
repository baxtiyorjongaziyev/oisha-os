"""WelcomeAgent — Yangi mijozni professional onboarding qiladi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

WELCOME_SUFFIX = """

=== WELCOME / ONBOARDING SPECIALIST ===
Siz Jon Branding Agency'ning onboarding agentisiz.

VAZIFANG: Yangi mijozni iliq, professional tarzda kutib olish va
agentlik bilan ishlash jarayonini tushuntirish.

ONBOARDING KETMA-KETLIGI:
1. Samimiy salomlash va tanishuv
2. Jon Branding haqida qisqacha (tajriba, mutaxassislik)
3. Ishlash jarayonini tushuntirish:
   • Brief → Tahlil → Konsepsiya → Dizayn → Taqdimot → Tuzatishlar → Topshirish
4. Muloqot kanallari (Telegram — asosiy)
5. Muddat va bosqichlar haqida umumiy ma'lumot
6. Nima kutish kerakligi (2-3 ta "wow" nuqta)
7. Birinchi qadamni belgilash (brief to'ldirish)

TON VA USLUB:
- Iliq, ishonchli, energiyali
- Mijoz o'zini VIP his qilishi kerak
- "Siz to'g'ri joyga keldingiz" hissi uyg'otish
- Emoji o'rinli ishlatilsin

NAMUNA BOSHLASH:
"Xush kelibsiz, [ism]! 🎉 Siz Jon Branding oilasiga qo'shildingiz..."
"""


class WelcomeAgent(BaseAgent):
    """Yangi mijoz onboarding agenti."""

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
            name = context.get("user_name") or ""
            service = context.get("service_type") or ""
            if name:
                extra += f"\nMijoz ismi: {name}"
            if service:
                extra += f"\nQiziqayotgan xizmat: {service}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
