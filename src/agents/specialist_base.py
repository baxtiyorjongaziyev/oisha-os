"""SpecialistAgent — prompt-suffiksli mutaxassis agentlar uchun umumiy oqim.

Yangi agent faqat prompt suffiksi va ``CONTEXT_FIELDS`` ni beradi; tarix,
kontekst va AI chaqiruvi shu yerda. Kontekst oxirgi foydalanuvchi xabariga
qoʻshiladi — ``self.system_prompt`` oʻzgartirilmaydi, shuning uchun parallel
suhbatlar bir-birining kontekstini koʻrmaydi.
"""

from typing import Any, Dict, List, Optional, Tuple

from .core import BaseAgent


class SpecialistAgent(BaseAgent):
    """Savol-javob uslubidagi mutaxassis agentlar uchun baza."""

    # (context kaliti, promptdagi yorliq)
    CONTEXT_FIELDS: Tuple[Tuple[str, str], ...] = ()

    def _context_note(self, context: Optional[Dict[str, Any]]) -> str:
        if not context:
            return ""
        lines = [
            f"{label}: {context[key]}"
            for key, label in self.CONTEXT_FIELDS
            if context.get(key)
        ]
        return "\n\n[KONTEKST]\n" + "\n".join(lines) if lines else ""

    def _build_contents(self, user_id: int, note: str) -> List[Dict[str, Any]]:
        contents = [
            {
                "role": "user" if turn["role"] == "user" else "model",
                "parts": [{"text": turn["content"]}],
            }
            for turn in self.get_session_history(user_id)
        ]
        if note and contents:
            contents[-1]["parts"][0]["text"] += note
        return contents

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        contents = self._build_contents(user_id, self._context_note(context))
        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=False)
        self.update_history(user_id, "assistant", reply)
        return reply
