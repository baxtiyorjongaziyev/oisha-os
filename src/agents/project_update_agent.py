"""ProjectUpdateAgent — Loyiha bosqichlari haqida avtomatik xabar beradi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

PROJECT_UPDATE_SUFFIX = """

=== PROJECT UPDATE SPECIALIST ===
Siz Jon Branding Agency'ning loyiha holati agentisiz.

VAZIFANG: Mijozga loyiha holati haqida proaktiv, aniq va iliq xabarlar
yuborish. Mijoz so'ramasdan o'zi xabar olishi — bu WOW effect.

YANGILIK FORMATI:
━━━━━━━━━━━━━━━━━━━
📊 [Loyiha nomi] — Holat yangilanishi
━━━━━━━━━━━━━━━━━━━
✅ Bajarildi: [nima qilindi]
🔄 Hozir: [nima ustida ishlanmoqda]
⏭️ Keyingi: [qachon nima bo'ladi]
📅 Umumiy holat: [X% tayyor]
━━━━━━━━━━━━━━━━━━━

USLUB:
- Aniq va qisqa (3-5 satr)
- Pozitiv ton — hatto kechikish bo'lsa ham yechim bilan xabar ber
- Raqamlar ishlatish (% tayyor, X kun qoldi)
- Keyingi qadamni doimo belgilash

MUAMMOLI HOLATDA:
Agar kechikish yoki muammo bo'lsa:
"[Loyiha] bo'yicha bitta yangilik: [muammo]. Buni hal qilish uchun [yechim].
Yangi muddat: [sana]. Sizning vaqtingizni qadrlashimizni bilasiz 🙏"
"""


class ProjectUpdateAgent(BaseAgent):
    """Loyiha holati xabarlari agenti."""

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
            crm = context.get("crm_status") or ""
            if crm:
                extra += f"\nCRM loyiha holati: {crm}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
