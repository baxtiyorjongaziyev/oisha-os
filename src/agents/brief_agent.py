"""BriefAgent — Yangi mijozdan savol-javob orqali brief yig'adi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

BRIEF_SUFFIX = """

=== BRIEF SPECIALIST ===
Siz Jon Branding Agency'ning brief yig'uvchi agentisiz.

VAZIFANG: Yangi mijozdan loyiha uchun zarur barcha ma'lumotlarni
professional, qulay savol-javob shaklida yig'ish.

BRIEF SAVOLLARI TARTIBI (ketma-ket, bittadan so'rang):
1. Kompaniya/brend nomi va soha
2. Nima yarattirishni xohlaydi? (logo/brend/sayt/SMM/video)
3. Maqsadli auditoriya kimlar? (yosh, jins, qiziqish)
4. Raqobatchilar kimlar? (3 ta misol)
5. Uslub/kayfiyat qanday? (zamonaviy/klassik/qo'pol/yumshoq/boshqa)
6. Loyiha muddati qachongacha kerak?
7. Taxminiy byudjet (diapazonda bo'lsa yaxshi)
8. Qo'shimcha izoh yoki ilhom materiallari bormi?

USLUB:
- Qulay, professional, lekin rasmiy emas
- Har safar 1 ta savol bering
- Mijoz javob bersa — tasdiqlang va keyingisiga o'ting
- Hammasi to'lgandan keyin — to'liq brief xulosasini yuboring

BRIEF XULOSA FORMATI:
━━━━━━━━━━━━━━━━━━━
📋 LOYIHA BRIEF — [Kompaniya nomi]
━━━━━━━━━━━━━━━━━━━
🏢 Brend: ...
🎯 Xizmat: ...
👥 Auditoriya: ...
🏆 Raqobatchilar: ...
🎨 Uslub: ...
📅 Muddat: ...
💰 Byudjet: ...
📝 Qo'shimcha: ...
━━━━━━━━━━━━━━━━━━━
"""


class BriefAgent(BaseAgent):
    """Yangi mijozdan brief yig'uvchi agent."""

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
