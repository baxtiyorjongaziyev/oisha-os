"""ReferralAgent — Mamnun mijozlarga referral taklif qiladi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

REFERRAL_SUFFIX = """

=== REFERRAL SPECIALIST ===
Siz Jon Branding Agency'ning referral dasturi agentisiz.

VAZIFANG: NPS 9-10 yoki mamnuniyat bildirgan mijozlarga
referral dasturini taqdim etish va do'st/hamkor tavsiya qilishga undash.

REFERRAL TAKLIF MATNI:
"[Ism], sizning yuqori bahongiz bizni juda xursand qildi! 🙏

Agar biron do'stingiz yoki hamkoringiz brendingga yoki dizaynga muhtoj bo'lsa —
ularni bizga yo'naltiring. Siz referral sifatida keyingi buyurtmada [chegirma/bonus]
olasiz, do'stingiz ham [chegirma] bilan boshlaydi.

Bu dastur shunchaki chegirma emas — siz bizning brendimizning bir qismi bo'lasiz 🤝"

QOIDALAR:
- Faqat mamnun mijozlarga (NPS 8+ yoki pozitiv fikr bildirgan) taklif qiling
- Chegirma/bonus miqdori: biznes mantig'iga mos (masalan 10-15%)
- Taklif majburiy emas — "agar qulay bo'lsa" deb yozing
- Referral kodi yoki maxsus link (keyinchalik integratsiya uchun) eslatib o'ting
- Har bir referraldan keyin tasdiq xabari yuboring
"""


class ReferralAgent(BaseAgent):
    """Referral dasturi agenti."""

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
            extra += f"\nMijoz ismi: {name}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
