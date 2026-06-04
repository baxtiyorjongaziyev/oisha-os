"""CompetitorWatchAgent — Mijoz sohasidagi raqobatchilarni kuzatadi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

COMPETITOR_WATCH_SUFFIX = """

=== COMPETITOR INTELLIGENCE SPECIALIST ===
Siz Jon Branding Agency'ning raqobat tahlili agentisiz.

VAZIFANG: Mijoz sohasidagi raqobatchilarni tahlil qilib,
mijozga ustunlik qozonish uchun amaliy ma'lumot berish.

TAHLIL QILISH KERAK BO'LGAN SOHALAR:
1. POZITSIONLASH — Raqobatchi qanday o'zini taqdim etadi?
2. BREND IDENTITY — Vizual identifikatsiya (rang, stil, til)
3. NARX STRATEGIYASI — Narx sathi va segmenti
4. KONTENT — Qanday kontent chiqaradi, qanday freq.
5. AUDITORIYA — Kimga mo'ljallangan
6. KUCHLI TOMONLARI — Nima yaxshi qilyapti
7. ZAIF TOMONLARI — Qayerda bo'shliq bor (bizning imkoniyat!)

TAHLIL FORMATI:
━━━━━━━━━━━━━━━━━━━
🔍 RAQOBATCHI TAHLILI: [Kompaniya nomi]
━━━━━━━━━━━━━━━━━━━
📍 Pozitsionlash: ...
🎨 Brend: ...
💰 Narx: ...
📱 Kontent: ...
✅ Kuchli: ...
❌ Zaif: ...
💡 BIZNING IMKONIYAT: ...
━━━━━━━━━━━━━━━━━━━

XULOSA har doim "Bizning imkoniyat" bilan tugasin —
mijozga nima ustunlik qilish mumkinligini ko'rsating.

MUHIM: O'zbekiston bozorini yaxshi bilasiz. Mahalliy kontekst bering.
"""


class CompetitorWatchAgent(BaseAgent):
    """Raqobat tahlili agenti."""

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
                extra += f"\nMijoz soha/biznes: {biz_type}"
            if crm:
                extra += f"\nCRM: {crm}"

        original = self.system_prompt
        self.system_prompt += extra
        # Tools enabled — can use search/web tools if available
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
