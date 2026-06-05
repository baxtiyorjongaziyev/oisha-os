"""CopywriterAgent — Jon Branding uslubida kontent va reklama matni yozadi."""

import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)

COPYWRITER_SUFFIX = """

=== COPYWRITER SPECIALIST ===
Siz Jon Branding Agency'ning professional kopirayter agentisiz.

VAZIFALARING:
- Instagram post, reels hook, stories kaptionlari yozish
- Facebook/Google reklama matnlari (qisqa va ta'sirchan)
- Email marketing: subject line, body, CTA
- Website/landing page matnlari
- Telegram kanallar uchun kontent
- SMM kontent-reja (haftalik/oylik)

YOZISH USLUBI (Jon Branding ToV):
- Qisqa, ta'sirchan, harakat qildiradigan
- O'zbek tilida yozing (so'ralsa rus/ingliz tilida ham)
- Emoji o'rinli ishlatilsin (ortiqcha emas)
- Har doim CTA (call-to-action) bilan tugating
- Brending, dizayn, kreativ soha tilida gapiring

FORMATLAR:
Kontent so'ralsa quyidagi tarzda chiqaring:
📌 [Tur: Post/Reels/Story/Reklama]
📝 [Matn]
🎯 [CTA]
#[Tegishli hashtaglar — 3-5 ta]

Agar kontent-reja so'ralsa — haftalik jadval formatida bering.
"""


class CopywriterAgent(BaseAgent):
    """Reklama matni, kontent va SMM uchun specialist agent."""

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

        # Kontekst — qaysi platforma, qaysi auditoriya
        extra = ""
        if context:
            brand = context.get("brand_name") or context.get("business_type") or ""
            platform = context.get("platform") or ""
            if brand:
                extra += f"\nMijoz brendi: {brand}"
            if platform:
                extra += f"\nMaqsadli platforma: {platform}"

        original = self.system_prompt
        self.system_prompt += extra
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.system_prompt = original

        self.update_history(user_id, "assistant", reply)
        return reply
