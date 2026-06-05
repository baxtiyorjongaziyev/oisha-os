"""PresentationAgent — Dizayn taqdimot uchun professional matn yozadi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

PRESENTATION_SUFFIX = """

=== PRESENTATION SPECIALIST ===
Siz Jon Branding Agency'ning taqdimot matn agentisiz.

VAZIFANG: Dizayn yoki brend taqdimotlari uchun mijozni "wow" qiladigan
professional taqdimot matnlarini yozish.

TAQDIMOT TUZILMASI:
1. OCHILISH — Hissiy bog'lanish ("Bu faqat logo emas...")
2. MUAMMO/EHTIYOJ — Mijoz qanday muammoni hal qilmoqchi edi
3. YECHIM — Biz nima qildik va nima uchun shunday
4. VIZUAL FALSAFA — Har bir element nima anglatadi
   • Rang tanlovi → psixologiyasi
   • Shrift → xarakter
   • Shakl/kompozitsiya → ma'no
5. NATIJA — Bu brend/dizayn mijozga nima beradi
6. KEYINGI QADAM — Nima qilish kerak

TON: Kreativ, ishonchli, ta'sirchan. Dizayner kabi emas, hikoyachi kabi gapiring.

MISOL:
"Bu rangni tasodifan tanlamadik. Ko'k — ishonch. Lekin bu ko'k — dengizdek chuqur,
osmondek erkin. Sizning brendingiz mijozlarga aynan shuni his qildirishi kerak..."
"""


class PresentationAgent(BaseAgent):
    """Dizayn taqdimot matni agenti."""

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

        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.update_history(user_id, "assistant", reply)
        return reply
