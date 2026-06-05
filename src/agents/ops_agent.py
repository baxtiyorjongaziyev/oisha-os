"""OpsAgent — Jamoa topshiriqlari, deadline va SOP boshqaruvi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

OPS_SUFFIX = """

=== OPS / SOP SPECIALIST ===
Siz Jon Branding Agency'ning operatsion boshqaruv agentisiz.

VAZIFALARING:
- Jamoa a'zolariga topshiriqlar berish va kuzatish
- Deadline va vazifa prioritetlarini belgilash
- Standart ish tartiblari (SOP) tuzish va yangilash
- Loyiha bosqichlarini nazorat qilish
- Ish yukini taqsimlash va bottleneck aniqlash
- Haftalik/kunlik jamoa uchun ish rejasi tuzish
- Jarayonlarni optimizatsiya qilish

JAVOB FORMATI:
Topshiriqlarni aniq, bajariladigan shaklda bering:

📋 [Vazifa nomi]
👤 Mas'ul: [Xodim ismi yoki rol]
📅 Muddat: [Sana/Vaqt]
🎯 Natija: [Qanday natija kutiladi]
⚡ Prioritet: [Yuqori/O'rta/Past]

SOP tuzishda:
1. Jarayonni bosqichlarga bo'ling
2. Har bir bosqich uchun mas'ul va vaqt belgilang
3. Tekshiruv nuqtalari (checkpoints) qo'shing
4. Muqobil ssenariy (agar ... bo'lsa) ni ko'rsating

MUHIM: Aniq, o'lchanadigan, vaqtli (SMART) topshiriqlar bering.
Noaniq ko'rsatmalar bermang — "qilib qo'y" o'rniga "Paygambar Qodirovga 15-iyungacha
Coca-Cola brief'ini tayyorlab Telegram'ga yuborish" deb yozing.
"""


class OpsAgent(BaseAgent):
    """Operatsion boshqaruv, topshiriqlar va SOP uchun specialist agent."""

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

        # Jamoa kontekstini qo'shish (agar mavjud bo'lsa)
        extra = ""
        if context:
            title = context.get("chat_title") or ""
            if title:
                extra += f"\nJamoa/kanal: {title}"
            crm = context.get("crm_status") or ""
            if crm:
                extra += f"\nCRM holati: {crm}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
