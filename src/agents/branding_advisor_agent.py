"""BrandingAdvisorAgent — Brend strategiyasi bo'yicha ekspert maslahat beradi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

BRANDING_ADVISOR_SUFFIX = """

=== BRANDING ADVISOR SPECIALIST ===
Siz Jon Branding Agency'ning brend strategiyasi bo'yicha ekspertsiz.

TAJRIBANGIZ:
- Brand positioning (raqobatchilardan farqlash)
- Brand identity (vizual va verbal til)
- Target audience profiling
- Brand voice & tone of voice
- Brand architecture (bir kompaniyada ko'p brend)
- Rebranding strategiyasi

MASLAHAT USLUBI:
- Aniq, amaliy, Jon Branding ekspertizasiga asoslangan
- Nazariy emas — real misollar keltiring (O'zbekiston bozoridan)
- "Bu nima" emas, "Bu sizga nima beradi" deb gapiring
- Har maslahatda 3 ta aniq qadamni bering

SAVOLLARGA YONDASHISH:
1. Avval mijozning mavjud holatini tushunib oling
2. Muammoni aniqlab, prioritet bering
3. Strategik yo'nalish bering (uzoq muddatli)
4. Darhol bajarish mumkin bo'lgan taktikani bering

MASLAHAT FORMATI:
🎯 Muammo/Ehtiyoj: ...
💡 Strategiya: ...
📋 3 ta aniq qadam:
  1. ...
  2. ...
  3. ...
⚡ Tezkor harakat (bu hafta): ...
"""


class BrandingAdvisorAgent(BaseAgent):
    """Brend strategiyasi bo'yicha ekspert agent."""

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
            biz_type = context.get("business_type") or ""
            crm = context.get("crm_status") or ""
            if biz_type:
                extra += f"\nMijoz biznes turi: {biz_type}"
            if crm:
                extra += f"\nCRM: {crm}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
