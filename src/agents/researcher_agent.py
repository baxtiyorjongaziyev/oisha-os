import logging
from typing import Optional, Dict, Any
from .core import BaseAgent

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Deep research va tahlil qiluvchi agent (OSINT/Search)."""

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        # Tarixni Gemini formatiga o'tkazish
        history = self.get_session_history(user_id)
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})

        # Researcher uchun qo'shimcha ko'rsatma (Oisha obrazini saqlaymiz)
        researcher_instruction = (
            "\n\n[AGENT MISSION: RESEARCHER]\n"
            "Siz hozirda Deep Research va OSINT bo'yicha mutaxassis sifatida ishlayapsiz. "
            "Sizning vazifangiz - loyihalar, bozorlar va raqobatchilarni chuqur tahlil qilish. "
            "Sizga berilgan tool lardan foydalanib, eng so'nggi ma'lumotlarni toping va tahlil qiling."
        )

        # Asosiy prompga qo'shish
        original_prompt = self.system_prompt
        self.system_prompt = (
            original_prompt
            + researcher_instruction
            + (f"\n\n[CONTEXT]: {context}" if context else "")
        )

        reply = await self.call_ai_with_fallback(contents, user_id)

        # Qayta tiklash
        self.system_prompt = original_prompt

        self.update_history(user_id, "assistant", reply)
        return reply
